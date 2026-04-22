#!/usr/bin/env python3
"""
Script para analizar automáticamente la página de estado del pedido
y sugerir localizadores para las pruebas web.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright
from config import settings
from components.api.api_client import OrderApiClient


def wait_for_results(page):
    """Espera hasta que aparezca el contenedor de resultados o un mensaje de error."""
    print("⏳ Esperando resultados...")
    # Posibles selectores para el contenedor de datos del pedido
    data_selectors = [
        '[class*="OrderInfo"]',
        '[class*="order-info"]',
        '[class*="TrackInfo"]',
        '[class*="Result"]',
        'div:has-text("Nombre")',
        'div:has-text("Dirección")',
        'div:has-text("Teléfono")',
    ]
    error_selectors = [
        'text="No encontrado"',
        'text="Not found"',
        '[class*="error"]',
        '[class*="not-found"]',
    ]

    start = time.time()
    while time.time() - start < 10:
        for sel in data_selectors + error_selectors:
            if page.locator(sel).count() > 0:
                print(f"✅ Elemento encontrado: {sel}")
                return sel
        time.sleep(0.5)
    print("❌ No se encontró ningún contenedor de datos después de 10 segundos.")
    return None


def analyze_page(page):
    """Extrae información clave de la página de estado del pedido."""
    print("\n📄 ANALIZANDO PÁGINA DE ESTADO DEL PEDIDO")
    print("=" * 50)

    # Imprimir todo el texto visible en la página (para depuración)
    print("\n📝 Texto visible completo de la página:")
    print("---")
    print(page.inner_text('body'))
    print("---")

    # Buscar contenedor específico (el que devolvió wait_for_results o intentar de nuevo)
    container_sel = wait_for_results(page)
    if not container_sel:
        print("No se pudo encontrar el contenedor de datos. Abortando análisis.")
        return

    container = page.locator(container_sel).first
    print(f"\n✅ Contenedor de datos encontrado: {container_sel}")

    # Extraer textos dentro del contenedor
    full_text = container.inner_text()
    print("\n📝 Texto dentro del contenedor:")
    print("---")
    print(full_text)
    print("---")

    # Buscar campos específicos y sugerir localizadores
    fields = [
        ("Nombre", "firstName"),
        ("Apellido", "lastName"),
        ("Dirección", "address"),
        ("Estación de metro", "metroStation"),
        ("Teléfono", "phone"),
        ("Fecha de entrega", "deliveryDate"),
        ("Período de alquiler", "rentTime"),
        ("Color", "color"),
        ("Comentario", "comment"),
        ("Estado", "status"),
    ]

    print("\n🎯 LOCALIZADORES SUGERIDOS:")
    for label, _ in fields:
        # Buscar elemento que contenga exactamente el texto de la etiqueta
        locator = container.locator(f'text="{label}"')
        if locator.count() > 0:
            # El valor suele estar en un elemento hermano o hijo
            # Sugerencia genérica: buscar el padre y luego un span/div sin hijos
            print(f"- {label}: container.locator('text=\"{label}\"').locator('..').locator('span, div:not(:has(*))')")
        else:
            print(f"- {label}: No se encontró etiqueta dentro del contenedor.")

    # Estado activo
    status_locator = container.locator(
        '[class*="status"], [class*="Status"], text=~"En camino|Procesando|Entregado"').first
    if status_locator.count() > 0:
        active_status = status_locator.inner_text()
        print(f"\n🚦 Estado activo detectado: '{active_status}'")
    else:
        print("\n⚠️  No se detectó estado activo.")


def print_all_buttons(page):
    """Imprime todos los botones visibles en la página para depuración."""
    buttons = page.locator('button').all()
    print("\n🔘 Botones encontrados en la página:")
    for i, btn in enumerate(buttons):
        try:
            text = btn.inner_text().strip()
            if text:
                print(f"  {i + 1}. '{text}'")
        except:
            pass


def main():
    print("🔧 Creando pedido de prueba...")
    api = OrderApiClient()
    order = api.create_valid_order()
    track = order.track
    print(f"✅ Pedido creado. Track: {track}")

    with sync_playwright() as p:
        launch_args = {"headless": False, "slow_mo": 300}
        if settings.browser.opera_executable:
            launch_args["executable_path"] = settings.browser.opera_executable
        browser = p.chromium.launch(**launch_args)

        page = browser.new_page()
        page.goto(f"{settings.server.base_url}/?lng=es")

        # Hacer clic en "Estado del pedido"
        page.click('button:has-text("Order status"), button:has-text("Estado del pedido")')
        page.wait_for_load_state("networkidle")

        print_all_buttons(page)

        # Localizar el campo de entrada de track
        track_input = page.locator(
            'input[placeholder*="número del pedido"], input[placeholder*="track"], input[type="text"]').first
        track_input.wait_for(state="visible", timeout=5000)
        track_input.fill(track)

        # Presionar Enter para buscar
        track_input.press("Enter")
        page.wait_for_load_state("networkidle")

        # Ejecutar análisis
        analyze_page(page)

        input("\nPresiona Enter para cerrar el navegador...")
        browser.close()


if __name__ == "__main__":
    main()