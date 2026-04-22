#!/usr/bin/env python3
"""
inspect_ui_hierarchy.py
=======================
Análisis completo de la jerarquía de vistas del emulador Android.
Captura: Resource-ID, content-desc, class, text, XPath, bounds para cada elemento.

Uso:
    python scripts/inspect_ui_hierarchy.py [--state <state_name>]

Estados disponibles:
    order_list      - Lista de pedidos (todos los pedidos)
    accept_dialog   - Diálogo "¿Deseas aceptar el pedido?"
    no_internet     - Popup "Sin acceso a Internet"
    my_orders       - Pestaña Mis pedidos
    all             - Captura todos los estados automáticamente

Requisitos: adb en PATH, emulador-5554 corriendo con la app abierta.
"""

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
import json
import time

DEVICE = "emulator-5554"
PKG    = "com.yandex.samokat"
DUMP_PATH = "/sdcard/window_dump.xml"
OUTPUT_DIR = Path(__file__).parent.parent / "logs" / "ui_inspection"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── ADB Helpers ─────────────────────────────────────────────────────────────

def adb(*args: str) -> str:
    result = subprocess.run(
        ["adb", "-s", DEVICE, "shell"] + list(args),
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def adb_pull(remote: str, local: Path) -> None:
    subprocess.run(
        ["adb", "-s", DEVICE, "pull", remote, str(local)],
        capture_output=True,
    )


def dump_ui(label: str) -> Path:
    """Performs a UI dump and returns path to local XML file."""
    print(f"\n{'='*70}")
    print(f"  CAPTURANDO: {label}")
    print(f"{'='*70}")
    
    adb("uiautomator", "dump", DUMP_PATH)
    time.sleep(0.5)
    
    local_path = OUTPUT_DIR / f"{label.replace(' ', '_')}.xml"
    adb_pull(DUMP_PATH, local_path)
    print(f"  → Guardado en: {local_path}")
    return local_path


# ─── XML Analysis ─────────────────────────────────────────────────────────────

def build_xpath(node: ET.Element, path: str = "") -> str:
    """Build a simple indexed XPath for an element."""
    tag = node.tag
    return f"{path}/{tag}"


def analyze_node(node: ET.Element, depth: int = 0, xpath: str = "") -> list[dict]:
    """Recursively analyze all nodes in the hierarchy."""
    results = []
    
    index      = node.get("index", "0")
    resource_id = node.get("resource-id", "")
    cls        = node.get("class", "")
    pkg        = node.get("package", "")
    content_desc = node.get("content-desc", "")
    text       = node.get("text", "")
    bounds     = node.get("bounds", "")
    clickable  = node.get("clickable", "false")
    enabled    = node.get("enabled", "true")
    checkable  = node.get("checkable", "false")
    scrollable = node.get("scrollable", "false")
    
    # Build XPath
    cls_short = cls.split(".")[-1] if "." in cls else cls
    if resource_id and PKG in resource_id:
        rid_short = resource_id.replace(f"{PKG}:", "")
        current_xpath = f'//*[@resource-id="{resource_id}"]'
    elif text:
        current_xpath = f'//*[@text="{text}"]'
    elif content_desc:
        current_xpath = f'//*[@content-desc="{content_desc}"]'
    else:
        current_xpath = f"{xpath}/{cls_short}[{index}]"
    
    # Only record elements that are meaningful
    is_meaningful = any([
        resource_id,
        content_desc,
        text,
        clickable == "true",
        scrollable == "true",
    ])
    
    if is_meaningful:
        results.append({
            "depth": depth,
            "class": cls,
            "class_short": cls_short,
            "resource_id": resource_id,
            "rid_short": resource_id.replace(f"{PKG}:", "") if resource_id else "",
            "content_desc": content_desc,
            "text": text[:80] if text else "",
            "bounds": bounds,
            "clickable": clickable == "true",
            "enabled": enabled == "true",
            "scrollable": scrollable == "true",
            "checkable": checkable == "true",
            "xpath": current_xpath,
            "package": pkg,
        })
    
    for child in node:
        results.extend(analyze_node(child, depth + 1, current_xpath))
    
    return results


def print_analysis(elements: list[dict], title: str) -> None:
    """Print formatted analysis of UI elements."""
    
    print(f"\n{'#'*70}")
    print(f"  ANÁLISIS: {title}")
    print(f"  Total elementos significativos: {len(elements)}")
    print(f"{'#'*70}")
    
    # Group by category
    with_rid  = [e for e in elements if PKG in e.get("resource_id","")]
    clickable  = [e for e in elements if e["clickable"] and e["enabled"]]
    with_text  = [e for e in elements if e["text"]]
    scrollable = [e for e in elements if e["scrollable"]]
    
    print(f"\n{'─'*70}")
    print(f"  1️⃣  RESOURCE-IDs DEL PAQUETE {PKG}")
    print(f"      (Los más fiables para Appium By.ID)")
    print(f"{'─'*70}")
    if with_rid:
        for e in with_rid:
            print(f"  • {e['rid_short']}")
            print(f"    Class:     {e['class_short']}")
            if e['text']:
                print(f"    Text:      \"{e['text']}\"")
            if e['content_desc']:
                print(f"    Acc.ID:    \"{e['content_desc']}\"")
            print(f"    Clickable: {e['clickable']} | Enabled: {e['enabled']} | Scrollable: {e['scrollable']}")
            print(f"    Bounds:    {e['bounds']}")
            print(f"    AppiumBy.ID → \"{e['resource_id']}\"")
            print()
    else:
        print("  (ninguno encontrado)")
    
    print(f"\n{'─'*70}")
    print(f"  2️⃣  BOTONES CLICKEABLES Y ACTIVOS")
    print(f"{'─'*70}")
    for e in clickable:
        label = e['text'] or e['content_desc'] or e['rid_short'] or e['class_short']
        print(f"  • \"{label}\"")
        print(f"    Class:       {e['class_short']}")
        if e['resource_id']:
            print(f"    Resource-ID: {e['resource_id']}")
        print(f"    XPath:       {e['xpath']}")
        print()
    
    print(f"\n{'─'*70}")
    print(f"  3️⃣  ELEMENTOS CON TEXTO (para XPath con @text)")
    print(f"{'─'*70}")
    for e in with_text:
        print(f"  [{e['class_short']}] \"{e['text']}\"")
        if e['resource_id']:
            print(f"           Resource-ID: {e['resource_id']}")
        print(f"           XPath: //*[@text=\"{e['text']}\"]")
    
    print(f"\n{'─'*70}")
    print(f"  4️⃣  CONTENEDORES SCROLLABLES (listas/recyclerviews)")
    print(f"{'─'*70}")
    if scrollable:
        for e in scrollable:
            print(f"  • {e['class_short']} → {e['resource_id'] or 'sin resource-id'}")
            print(f"    Bounds: {e['bounds']}")
    else:
        print("  (ninguno)")
    
    print(f"\n{'─'*70}")
    print(f"  5️⃣  TODOS LOS RESOURCE-IDs (incluyendo sistema)")
    print(f"{'─'*70}")
    all_rids = {e['resource_id'] for e in elements if e['resource_id']}
    for rid in sorted(all_rids):
        print(f"  {rid}")


def generate_locator_recommendations(elements: list[dict], state: str) -> dict:
    """Generate recommended locators based on analysis."""
    recs = {
        "state": state,
        "order_item_candidates": [],
        "tab_all_candidates": [],
        "tab_mine_candidates": [],
        "popup_ok_candidates": [],
        "accept_btn_candidates": [],
        "confirm_yes_candidates": [],
    }
    
    for e in elements:
        text  = (e.get("text") or "").lower()
        rid   = (e.get("resource_id") or "").lower()
        desc  = (e.get("content_desc") or "").lower()
        cls   = (e.get("class_short") or "").lower()
        
        # Order item heuristic: contains address/delivery date info
        if any(k in text for k in ["dirección", "direccion", "fecha", "entrega", "main st"]):
            recs["order_item_candidates"].append({
                "resource_id": e["resource_id"],
                "class": e["class"],
                "text": e["text"],
                "xpath": e["xpath"],
                "bounds": e["bounds"],
            })
        
        # Tab "Todos los pedidos"
        if "todos" in text or "todos" in desc or "tab_all" in rid or "all" in rid:
            recs["tab_all_candidates"].append({
                "resource_id": e["resource_id"],
                "text": e["text"],
                "xpath": e["xpath"],
            })
        
        # Tab "Mis pedidos"
        if ("mis" in text and "pedidos" in text) or "mine" in rid or "tab_mine" in rid:
            recs["tab_mine_candidates"].append({
                "resource_id": e["resource_id"],
                "text": e["text"],
                "xpath": e["xpath"],
            })
        
        # PopUp OK/Aceptar — context: within a dialog
        if text in ["aceptar", "ok", "cerrar", "close"] and e["clickable"]:
            recs["popup_ok_candidates"].append({
                "resource_id": e["resource_id"],
                "text": e["text"],
                "parent_context": "need to verify if inside dialog container",
                "xpath": e["xpath"],
                "bounds": e["bounds"],
            })
        
        # Accept button on order card
        if text == "aceptar" and e["clickable"]:
            recs["accept_btn_candidates"].append({
                "resource_id": e["resource_id"],
                "text": e["text"],
                "bounds": e["bounds"],
                "xpath": e["xpath"],
            })
        
        # Confirm "Sí"
        if text in ["sí", "si", "yes"] and e["clickable"]:
            recs["confirm_yes_candidates"].append({
                "resource_id": e["resource_id"],
                "text": e["text"],
                "xpath": e["xpath"],
            })
    
    return recs


def save_json(data: dict, filename: str) -> None:
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  💾 JSON guardado: {path}")


# ─── App state setup helpers ──────────────────────────────────────────────────

def launch_app() -> None:
    print("\n  🚀 Lanzando la app...")
    subprocess.run(
        ["adb", "-s", DEVICE, "shell", "monkey", "-p", PKG,
         "-c", "android.intent.category.LAUNCHER", "1"],
        capture_output=True,
    )
    time.sleep(3)


def press_back() -> None:
    adb("input", "keyevent", "4")
    time.sleep(0.5)


def collapse_shade() -> None:
    adb("cmd", "statusbar", "collapse")
    time.sleep(0.3)


# ─── Main inspection workflow ─────────────────────────────────────────────────

def inspect_current_state(label: str) -> dict:
    """Dump and analyze the current UI state."""
    xml_path = dump_ui(label)
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"  ERROR parsing XML: {e}")
        return {}
    
    elements = analyze_node(root)
    print_analysis(elements, label)
    
    recs = generate_locator_recommendations(elements, label)
    save_json(recs, f"recs_{label.replace(' ','_')}.json")
    
    return recs


def run_full_inspection() -> None:
    """Run all inspection states."""
    
    print("\n" + "="*70)
    print("  URBAN SCOOTER — INSPECCIÓN COMPLETA DE JERARQUÍA DE VISTAS")
    print("="*70)
    
    collapse_shade()
    launch_app()
    time.sleep(2)
    collapse_shade()
    
    # ── STATE 1: Whatever is currently on screen ──────────────────────────────
    inspect_current_state("estado_actual")
    
    input("\n  ⏸  Pon la app en 'Todos los pedidos' con al menos UN pedido visible.")
    input("     (Si no hay pedidos, créalos desde el navegador y haz swipe para refrescar)")
    input("     Cuando estés listo, presiona ENTER...")
    
    # ── STATE 2: Order list with orders ───────────────────────────────────────
    all_recs = inspect_current_state("lista_todos_pedidos")
    
    input("\n  ⏸  Ahora presiona el botón 'Aceptar' de UNO de los pedidos.")
    input("     El diálogo '¿Deseas aceptar el pedido?' debe aparecer.")
    input("     Cuando el diálogo esté ABIERTO, presiona ENTER...")
    
    # ── STATE 3: Accept confirmation dialog ────────────────────────────────────
    dialog_recs = inspect_current_state("dialogo_aceptar_pedido")
    
    print("\n  ℹ️  Cerrando el diálogo con NO...")
    adb("input", "keyevent", "4")
    time.sleep(1)
    
    input("\n  ⏸  Ahora ve a 'Mis pedidos'. Presiona ENTER cuando estés ahí...")
    
    # ── STATE 4: My Orders tab ─────────────────────────────────────────────────
    inspect_current_state("mis_pedidos")
    
    input("\n  ⏸  Ahora desactiva WiFi/datos: adb shell svc wifi disable && svc data disable")
    input("     Luego toca cualquier botón activo de la app para provocar el popup.")
    input("     Cuando el popup 'Sin acceso a Internet' esté visible, presiona ENTER...")
    
    # ── STATE 5: No internet popup ────────────────────────────────────────────
    popup_recs = inspect_current_state("popup_sin_internet")
    
    print("\n  ✅ Reactivando internet...")
    adb("svc", "wifi", "enable")
    adb("svc", "data", "enable")
    time.sleep(2)
    
    # ── FINAL SUMMARY ──────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  📋 RESUMEN DE LOCALIZADORES CLAVE")
    print(f"{'='*70}")
    
    print("\n  🎯 RECOMENDACIONES PARA mobile_app.py:")
    
    if all_recs.get("order_item_candidates"):
        print("\n  _ORDER_ITEM (tarjetas de pedido):")
        for c in all_recs["order_item_candidates"][:5]:
            if c["resource_id"]:
                print(f"    → AppiumBy.ID: \"{c['resource_id']}\"")
            else:
                print(f"    → XPath: {c['xpath']}")
                print(f"    → Text:  \"{c['text']}\"")
    
    if all_recs.get("tab_all_candidates"):
        print("\n  _BTN_ALL_ORDERS (pestaña Todos los pedidos):")
        for c in all_recs["tab_all_candidates"]:
            print(f"    → AppiumBy.ID: \"{c['resource_id']}\"  | text: \"{c['text']}\"")
    
    if all_recs.get("tab_mine_candidates"):
        print("\n  _BTN_MY_ORDERS (pestaña Mis pedidos):")
        for c in all_recs["tab_mine_candidates"]:
            print(f"    → AppiumBy.ID: \"{c['resource_id']}\"  | text: \"{c['text']}\"")
    
    if popup_recs.get("popup_ok_candidates"):
        print("\n  _POPUP_OK (botón OK del popup sin internet):")
        for c in popup_recs["popup_ok_candidates"]:
            print(f"    → AppiumBy.ID: \"{c['resource_id']}\"  | text: \"{c['text']}\"  | bounds: {c['bounds']}")
    
    if all_recs.get("accept_btn_candidates"):
        print("\n  Botones 'Aceptar' en tarjetas de pedido (NO para dismiss popup):")
        for c in all_recs["accept_btn_candidates"][:3]:
            print(f"    → AppiumBy.ID: \"{c['resource_id']}\"  | bounds: {c['bounds']}")
    
    if dialog_recs.get("confirm_yes_candidates"):
        print("\n  _CONFIRM_YES (botón Sí del diálogo de aceptar pedido):")
        for c in dialog_recs["confirm_yes_candidates"]:
            print(f"    → resource_id: \"{c['resource_id']}\"  | text: \"{c['text']}\"")
    
    print(f"\n  📁 Todos los JSON guardados en: {OUTPUT_DIR}/")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Urban Scooter UI Hierarchy Inspector")
    parser.add_argument("--state", default="interactive",
                       choices=["current", "interactive"],
                       help="'current' = solo captura el estado actual, 'interactive' = workflow completo")
    args = parser.parse_args()
    
    if args.state == "current":
        inspect_current_state("captura_actual")
    else:
        run_full_inspection()
