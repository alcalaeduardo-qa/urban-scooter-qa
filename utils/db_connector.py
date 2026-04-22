"""
Database connector module using SSH interactive session via pexpect.
Executes psql commands inside a remote shell using a pipe to avoid escaping issues.
"""
from __future__ import annotations

import json
import re
import pexpect
from typing import Any, Optional, Sequence

from config.settings import database as db_cfg
from utils.decorators import log_step, retry
from utils.logger import get_logger

log = get_logger("db_connector")


class DatabaseNotConnectedError(RuntimeError):
    """Raised when attempting to use the database connector before connecting."""


class DatabaseConnector:
    """
    Manages database queries by opening an interactive SSH session,
    waiting for the shell prompt, sending psql commands via a pipe,
    and capturing output.
    """

    def __init__(self) -> None:
        self._connected = False

    def __enter__(self) -> "DatabaseConnector":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.disconnect()

    @log_step("Open database connection")
    def connect(self) -> None:
        """Test SSH connectivity."""
        try:
            self._run_ssh_command("echo OK", timeout=10)
        except Exception as e:
            log.error("[db] SSH connection test failed: %s", e)
            raise
        self._connected = True
        log.info("[db] SSH connection available")

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Execute a write operation via psql."""
        self._assert_connected()
        sql = self._interpolate_params(sql, params)
        cmd = self._build_psql_command(sql)
        stdout, stderr = self._run_ssh_command(cmd, timeout=30)

        if stderr and "ERROR" in stderr:
            log.error("[db] psql error: %s", stderr)
            return -1

        match = re.search(r"(?:INSERT|UPDATE|DELETE)\s+\d+\s+(\d+)", stdout)
        if match:
            return int(match.group(1))
        return 0

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """Execute a SELECT and return rows as dictionaries."""
        self._assert_connected()

        sql = self._interpolate_params(sql, params)
        json_sql = self._wrap_select_as_json(sql)
        cmd = self._build_psql_command(json_sql)
        stdout, stderr = self._run_ssh_command(cmd, timeout=30)

        if stderr and "ERROR" in stderr:
            log.error("[db] psql error: %s", stderr)
            return []

        if not stdout.strip():
            return []

        json_str = self._extract_json(stdout)
        if not json_str:
            log.error("[db] No JSON found in stdout")
            log.debug("[db] Raw stdout: %s", stdout)
            return []

        try:
            data = json.loads(json_str)
            if data is None:
                return []
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                log.warning("[db] Unexpected JSON structure: %s", data)
                return []
        except json.JSONDecodeError as e:
            log.error("[db] Failed to parse JSON: %s", e)
            log.debug("[db] Extracted JSON string: %s", json_str)
            return []

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def count(self, sql: str, params: Sequence[Any] = ()) -> int:
        row = self.fetch_one(sql, params)
        if row is None:
            return 0
        if "count" in row:
            return int(row["count"])
        return int(next(iter(row.values())))

    # ---------- Domain-specific methods ----------
    def count_couriers(self) -> int:
        return self.count('SELECT COUNT(*) AS count FROM "Couriers"')

    def count_orders(self) -> int:
        return self.count('SELECT COUNT(*) AS count FROM "Orders"')

    def get_courier_by_login(self, login: str) -> dict[str, Any] | None:
        return self.fetch_one(
            'SELECT * FROM "Couriers" WHERE login = %s',
            (login,)
        )

    def get_orders_by_track(self, track: str) -> list[dict[str, Any]]:
        return self.fetch_all(
            'SELECT * FROM "Orders" WHERE track = %s',
            (track,)
        )

    def has_duplicate_orders(self, track: str) -> bool:
        count = self.count(
            'SELECT COUNT(*) AS count FROM "Orders" WHERE track = %s',
            (track,)
        )
        return count > 1

    def get_order_status(self, track: str) -> str | None:
        row = self.fetch_one(
            'SELECT status FROM "Orders" WHERE track = %s',
            (track,)
        )
        return row["status"] if row else None

    def is_password_hashed(self, login: str, plain_password: str) -> bool:
        row = self.get_courier_by_login(login)
        if not row:
            return False
        stored = str(row.get("passwordHash", ""))
        return stored != plain_password and len(stored) > 30

    # ---------- Private helpers ----------
    def _interpolate_params(self, sql: str, params: Sequence[Any]) -> str:
        """Safely interpolate parameters into SQL string (for test environment only)."""
        if not params:
            return sql
        formatted = []
        for p in params:
            if isinstance(p, str):
                escaped = p.replace("'", "''")
                formatted.append(f"'{escaped}'")
            elif p is None:
                formatted.append("NULL")
            else:
                formatted.append(str(p))
        return sql % tuple(formatted)

    def _build_psql_command(self, sql: str) -> str:
        """
        Build a remote command that pipes the SQL into psql via echo.
        This avoids any escaping problems with quotes.
        """
        # Escapar solo comillas dobles para que el echo no las interprete
        sql_escaped = sql.replace('"', '\\"')
        return (
            f'echo "{sql_escaped}" | '
            f'PGPASSWORD="{db_cfg.password}" psql -U {db_cfg.user} -d {db_cfg.name} '
            f'-A -t'
        )

    def _wrap_select_as_json(self, sql: str) -> str:
        """Wrap a SELECT query to return a JSON array of objects."""
        select_sql = sql.rstrip(';').strip()
        return f"SELECT json_agg(row_to_json(t)) FROM ({select_sql}) t"

    def _run_ssh_command(self, remote_cmd: str, timeout: int = 30) -> tuple[str, str]:
        """
        Execute a command on the remote server via an interactive SSH session.
        Uses pexpect to wait for the shell prompt, send the command, and capture output.
        """
        ssh_base = [
            "ssh",
            "-q",
            "-p", str(db_cfg.ssh_port),
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            "-o", "LogLevel=QUIET",
            f"{db_cfg.ssh_user}@{db_cfg.ssh_host}",
        ]
        ssh_cmd = " ".join(ssh_base)
        log.debug("[db] Running SSH: %s", ssh_cmd)

        child = pexpect.spawn(ssh_cmd, encoding='utf-8', timeout=timeout)

        prompt_pattern = r'\$ $|# $|:\~\$ $|:\S+ \$ '
        try:
            index = child.expect([prompt_pattern, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if index != 0:
                log.error("[db] No shell prompt detected. Output: %s", child.before)
                raise RuntimeError("Failed to get shell prompt")
        except pexpect.TIMEOUT:
            log.error("[db] Timeout waiting for shell prompt")
            raise
        except pexpect.EOF:
            log.error("[db] SSH connection closed unexpectedly")
            raise

        child.sendline(remote_cmd)

        try:
            child.expect(prompt_pattern, timeout=timeout)
        except pexpect.TIMEOUT:
            log.error("[db] Timeout waiting for command to complete")
            raise
        except pexpect.EOF:
            log.error("[db] SSH connection closed during command")
            raise

        output = child.before
        lines = output.splitlines()
        if lines and remote_cmd in lines[0]:
            output = "\n".join(lines[1:])

        child.sendline("exit")
        try:
            child.expect(pexpect.EOF, timeout=5)
        except:
            pass
        child.terminate(force=True)

        return output.strip(), ""

    def _extract_json(self, text: str) -> Optional[str]:
        """
        Extracts the first valid JSON string from the text.
        """
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line[0] in '[{':
                try:
                    json.loads(line)
                    return line
                except json.JSONDecodeError:
                    continue
        return None

    def _assert_connected(self) -> None:
        if not self.is_connected:
            raise DatabaseNotConnectedError("DatabaseConnector is not connected.")