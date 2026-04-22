"""
jira_uploader.py — Sube screenshots a los issues de Jira tras importar el CSV.

Flujo de uso:
  1. Importar bugs_jira_<ts>.csv en Jira (Issues > Import CSV).
  2. Exportar el CSV resultante desde Jira (con la columna "Clave de incidencia" rellena).
  3. Ejecutar:
       python jira_uploader.py <jira_export.csv> <bug_manifest.json>

Requiere en .env:
  JIRA_BASE_URL   = https://tudominio.atlassian.net
  JIRA_USER       = tu@email.com
  JIRA_API_TOKEN  = tu_api_token
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from config import settings


def _load_env() -> tuple[str, str, str]:
    import os
    base_url   = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    user       = os.getenv("JIRA_USER", "")
    api_token  = os.getenv("JIRA_API_TOKEN", "")
    if not all([base_url, user, api_token]):
        print(
            "ERROR: Faltan variables de entorno Jira.\n"
            "Añade JIRA_BASE_URL, JIRA_USER y JIRA_API_TOKEN en tu .env"
        )
        sys.exit(1)
    return base_url, user, api_token


def _load_manifest(manifest_path: Path) -> dict[str, str]:
    """Devuelve {resumen: attachment_path}."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {entry["resumen"]: entry["attachment"] for entry in data if entry.get("attachment")}


def _load_issue_keys(jira_csv_path: Path) -> dict[str, str]:
    """
    Lee el CSV exportado de Jira y devuelve {resumen: issue_key}.
    Jira usa 'Summary' o 'Resumen' y 'Issue key' o 'Clave de incidencia'.
    """
    mapping: dict[str, str] = {}
    with open(jira_csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            summary = row.get("Summary") or row.get("Resumen") or ""
            key     = row.get("Issue key") or row.get("Clave de incidencia") or ""
            if summary and key:
                mapping[summary.strip()] = key.strip()
    return mapping


def _upload_attachment(base_url: str, auth: HTTPBasicAuth, issue_key: str, file_path: Path) -> bool:
    """Sube un archivo como adjunto al issue indicado. Devuelve True si tuvo éxito."""
    url = f"{base_url}/rest/api/2/issue/{issue_key}/attachments"
    headers = {
        "X-Atlassian-Token": "no-check",  # requerido por Jira para adjuntos
    }
    try:
        with open(file_path, "rb") as fp:
            resp = requests.post(
                url,
                headers=headers,
                auth=auth,
                files={"file": (file_path.name, fp)},
                timeout=30,
            )
        if resp.status_code in (200, 201):
            return True
        print(f"  [WARN] {issue_key}: HTTP {resp.status_code} — {resp.text[:120]}")
        return False
    except Exception as exc:
        print(f"  [ERROR] {issue_key}: {exc}")
        return False


def run(jira_csv_path: Path, manifest_path: Path) -> None:
    base_url, user, api_token = _load_env()
    auth = HTTPBasicAuth(user, api_token)

    manifest    = _load_manifest(manifest_path)
    issue_keys  = _load_issue_keys(jira_csv_path)

    ok = fail = skip = 0

    for resumen, attachment_str in manifest.items():
        issue_key = issue_keys.get(resumen)
        if not issue_key:
            print(f"[SKIP] Sin clave Jira para: {resumen[:60]}...")
            skip += 1
            continue

        attachment = Path(attachment_str)
        if not attachment.exists():
            print(f"[SKIP] Archivo no encontrado: {attachment}")
            skip += 1
            continue

        print(f"[→] {issue_key}  ←  {attachment.name}")
        if _upload_attachment(base_url, auth, issue_key, attachment):
            print(f"  [OK] Adjunto subido.")
            ok += 1
        else:
            fail += 1

    print(f"\nResumen: {ok} subidos, {fail} fallidos, {skip} omitidos.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    run(Path(sys.argv[1]), Path(sys.argv[2]))
