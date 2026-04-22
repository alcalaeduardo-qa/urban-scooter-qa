from __future__ import annotations
import time
import requests
from config.settings import server as srv_cfg
from utils.decorators import log_step
from utils.logger import get_logger

log = get_logger("server_manager")


class ServerManager:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or srv_cfg.base_url

    @log_step("Wait for server to be ready")
    def wait_until_ready(self, timeout: int | None = None, interval: float | None = None) -> bool:
        deadline = time.time() + (timeout or srv_cfg.health_check_timeout)
        poll = interval or srv_cfg.health_check_interval
        while time.time() < deadline:
            if self._is_alive():
                log.info("[server] Ready at %s", self.base_url)
                return True
            log.debug("[server] Not ready yet, retrying in %.1fs…", poll)
            time.sleep(poll)
        log.error("[server] Timed out waiting for %s", self.base_url)
        return False

    def is_up(self) -> bool:
        return self._is_alive()

    def _is_alive(self) -> bool:
        try:
            resp = requests.get(self.base_url, timeout=2)
            return resp.status_code < 500
        except requests.RequestException:
            return False
