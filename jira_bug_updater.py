"""
jira_bug_updater.py — Actualiza issues de Jira tras revisión de datos de prueba.

Acciones:
  - PFTT-32, PFTT-42  [ID03 Nombre]     → cierra issue (era error del test, no bug real)
  - PFTT-33, PFTT-43  [ID09 Apellido]   → elimina screenshot viejo, sube nuevo, actualiza descripción
  - PFTT-34, PFTT-44  [ID12 Dirección]  → elimina screenshot viejo, sube nuevo, actualiza descripción

Uso:
    python jira_bug_updater.py [--dry-run]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
SCREENSHOTS_DIR = ROOT / "screenshots" / "tarea_2_validacion"

TRANSITION_DONE = "41"  # "Listo / Finalizada"

# ── Configuración de cambios ───────────────────────────────────────────────────

ISSUES_TO_CLOSE = {
    "PFTT-32": "[T2-Validación-Opera] [3] Nombre",
    "PFTT-42": "[T2-Validación-Chrome] [3] Nombre",
}

ISSUES_TO_UPDATE = {
    "PFTT-33": {
        "label": "[T2-Validación-Opera] [9] Apellido",
        "screenshot": "test_id_09_no_aprobado_20260420_181048.png",
        "description": (
            "BUG — Campo Apellido acepta 16 caracteres cuando el límite máximo es 15.\n\n"
            "Pasos para reproducir:\n"
            "1. Abrir el formulario de pedido en Opera.\n"
            "2. Ingresar 'Gutierrez-Vegasb' (16 chars) en el campo Apellido.\n"
            "3. Completar el resto de campos con datos válidos y hacer clic en Siguiente.\n\n"
            "Resultado actual: el formulario avanza al paso 2 (debería bloquearse).\n"
            "Resultado esperado: el sistema debe mostrar error y bloquear el avance.\n\n"
            "Límite según requisito: 2–15 caracteres.\n"
            "Límite real del sistema: acepta hasta al menos 16 caracteres."
        ),
    },
    "PFTT-43": {
        "label": "[T2-Validación-Chrome] [9] Apellido",
        "screenshot": "test_id_09_no_aprobado_20260420_181057.png",
        "description": (
            "BUG — Campo Apellido acepta 16 caracteres cuando el límite máximo es 15.\n\n"
            "Pasos para reproducir:\n"
            "1. Abrir el formulario de pedido en Chrome.\n"
            "2. Ingresar 'Gutierrez-Vegasb' (16 chars) en el campo Apellido.\n"
            "3. Completar el resto de campos con datos válidos y hacer clic en Siguiente.\n\n"
            "Resultado actual: el formulario avanza al paso 2 (debería bloquearse).\n"
            "Resultado esperado: el sistema debe mostrar error y bloquear el avance.\n\n"
            "Límite según requisito: 2–15 caracteres.\n"
            "Límite real del sistema: acepta hasta al menos 16 caracteres."
        ),
    },
    "PFTT-34": {
        "label": "[T2-Validación-Opera] [12] Dirección",
        "screenshot": "test_id_12_no_aprobado_20260420_182612.png",
        "description": (
            "BUG — Campo Dirección rechaza exactamente 50 caracteres cuando debería aceptarlos.\n\n"
            "Pasos para reproducir:\n"
            "1. Abrir el formulario de pedido en Opera.\n"
            "2. Ingresar una dirección de exactamente 50 caracteres (ej. "
            "'Avenida Principal 1234 Colonia Centro Norte Blvd 5').\n"
            "3. Completar el resto de campos y hacer clic en Siguiente.\n\n"
            "Resultado actual: el formulario NO avanza; el sistema bloquea la dirección de 50 chars.\n"
            "Resultado esperado: debe aceptarse, el requisito especifica máximo 50 caracteres.\n\n"
            "Investigación adicional: se probaron longitudes 30–50 chars. "
            "El sistema acepta hasta 49 chars y rechaza exactamente 50. "
            "El límite real implementado parece ser 49, no 50."
        ),
    },
    "PFTT-44": {
        "label": "[T2-Validación-Chrome] [12] Dirección",
        "screenshot": "test_id_12_no_aprobado_20260420_182624.png",
        "description": (
            "BUG — Campo Dirección rechaza exactamente 50 caracteres cuando debería aceptarlos.\n\n"
            "Pasos para reproducir:\n"
            "1. Abrir el formulario de pedido en Chrome.\n"
            "2. Ingresar una dirección de exactamente 50 caracteres (ej. "
            "'Avenida Principal 1234 Colonia Centro Norte Blvd 5').\n"
            "3. Completar el resto de campos y hacer clic en Siguiente.\n\n"
            "Resultado actual: el formulario NO avanza; el sistema bloquea la dirección de 50 chars.\n"
            "Resultado esperado: debe aceptarse, el requisito especifica máximo 50 caracteres.\n\n"
            "Investigación adicional: se probaron longitudes 30–50 chars. "
            "El sistema acepta hasta 49 chars y rechaza exactamente 50. "
            "El límite real implementado parece ser 49, no 50."
        ),
    },
}

# ── Helpers API ────────────────────────────────────────────────────────────────

def _auth_and_base() -> tuple[HTTPBasicAuth, str]:
    user      = os.getenv("JIRA_USER", "")
    token     = os.getenv("JIRA_API_TOKEN", "")
    base_url  = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    if not all([user, token, base_url]):
        print("ERROR: Faltan JIRA_USER, JIRA_API_TOKEN o JIRA_BASE_URL en .env")
        sys.exit(1)
    return HTTPBasicAuth(user, token), base_url


def close_issue(auth: HTTPBasicAuth, base: str, key: str, label: str, dry: bool) -> None:
    print(f"\n[CERRAR] {key} — {label}")
    if dry:
        print("  [DRY-RUN] transición → Finalizada (id=41)")
        return
    r = requests.post(
        f"{base}/rest/api/3/issue/{key}/transitions",
        json={"transition": {"id": TRANSITION_DONE}},
        auth=auth, timeout=15,
    )
    if r.status_code == 204:
        print("  [OK] Issue marcado como Finalizado.")
    else:
        print(f"  [ERROR] HTTP {r.status_code}: {r.text[:200]}")


def _get_attachments(auth: HTTPBasicAuth, base: str, key: str) -> list[dict]:
    r = requests.get(
        f"{base}/rest/api/3/issue/{key}",
        params={"fields": "attachment"},
        auth=auth, timeout=15,
    )
    return r.json().get("fields", {}).get("attachment", [])


def delete_attachment(auth: HTTPBasicAuth, base: str, att_id: str, filename: str, dry: bool) -> None:
    print(f"  [DELETE] attachment {att_id} ({filename})")
    if dry:
        print("    [DRY-RUN] no eliminado")
        return
    r = requests.delete(
        f"{base}/rest/api/3/attachment/{att_id}",
        auth=auth, timeout=15,
    )
    if r.status_code == 204:
        print("    [OK] Eliminado.")
    else:
        print(f"    [ERROR] HTTP {r.status_code}: {r.text[:200]}")


def upload_attachment(auth: HTTPBasicAuth, base: str, key: str, filepath: Path, dry: bool) -> None:
    print(f"  [UPLOAD] {filepath.name} → {key}")
    if dry:
        print("    [DRY-RUN] no subido")
        return
    with open(filepath, "rb") as fp:
        r = requests.post(
            f"{base}/rest/api/3/issue/{key}/attachments",
            headers={"X-Atlassian-Token": "no-check"},
            auth=auth,
            files={"file": (filepath.name, fp)},
            timeout=30,
        )
    if r.status_code in (200, 201):
        print("    [OK] Screenshot subido.")
    else:
        print(f"    [ERROR] HTTP {r.status_code}: {r.text[:200]}")


def update_description(auth: HTTPBasicAuth, base: str, key: str, text: str, dry: bool) -> None:
    print(f"  [DESC] Actualizando descripción de {key}")
    if dry:
        print("    [DRY-RUN] no actualizado")
        return
    # Jira API v3 usa Atlassian Document Format (ADF)
    adf_body = {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": paragraph}],
            }
            for paragraph in text.split("\n\n")
        ],
    }
    r = requests.put(
        f"{base}/rest/api/3/issue/{key}",
        json={"fields": {"description": adf_body}},
        auth=auth, timeout=15,
    )
    if r.status_code == 204:
        print("    [OK] Descripción actualizada.")
    else:
        print(f"    [ERROR] HTTP {r.status_code}: {r.text[:200]}")


def update_issue(auth: HTTPBasicAuth, base: str, key: str, cfg: dict, dry: bool) -> None:
    print(f"\n[ACTUALIZAR] {key} — {cfg['label']}")

    # 1. Eliminar attachments viejos
    attachments = _get_attachments(auth, base, key)
    for att in attachments:
        delete_attachment(auth, base, att["id"], att["filename"], dry)

    # 2. Subir nuevo screenshot
    screenshot_path = SCREENSHOTS_DIR / cfg["screenshot"]
    if screenshot_path.exists():
        upload_attachment(auth, base, key, screenshot_path, dry)
    else:
        print(f"  [WARN] Screenshot no encontrado: {screenshot_path}")

    # 3. Actualizar descripción
    update_description(auth, base, key, cfg["description"], dry)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    dry = "--dry-run" in sys.argv
    if dry:
        print("=== DRY-RUN activo — no se harán cambios reales en Jira ===\n")

    auth, base = _auth_and_base()

    for key, label in ISSUES_TO_CLOSE.items():
        close_issue(auth, base, key, label, dry)

    for key, cfg in ISSUES_TO_UPDATE.items():
        update_issue(auth, base, key, cfg, dry)

    print("\n=== Completado ===")


if __name__ == "__main__":
    main()
