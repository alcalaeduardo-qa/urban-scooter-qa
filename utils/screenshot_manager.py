"""
screenshot_manager.py – Gestor de capturas de pantalla para pruebas.
Soporta Playwright, Appium y API (generando imágenes de texto).
"""
from __future__ import annotations

import time
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from appium.webdriver.webdriver import WebDriver

from config import settings
from utils.logger import get_logger

log = get_logger("screenshot_manager")
_SANITIZE = re.compile(r"[^\w\-_\. ]")


class ScreenshotManager:
    """Gestiona la captura de evidencias para pruebas fallidas."""

    def __init__(self, category: str = "general") -> None:
        self._base_dir = settings.SCREENSHOTS_DIR / _SANITIZE.sub("_", category).strip("_")
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def capture_playwright(self, page: Page, test_name: str) -> str:
        """
        Captura una screenshot del navegador con Playwright.
        Retorna la ruta del archivo generado.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{test_name}_{timestamp}.png"
        filepath = self._base_dir / filename
        page.screenshot(path=str(filepath))
        log.info("Playwright screenshot saved: %s", filepath)
        return str(filepath)

    def capture_appium(self, driver: WebDriver, test_name: str) -> str:
        """
        Captura una screenshot del dispositivo móvil con Appium.
        Retorna la ruta del archivo generado.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{test_name}_{timestamp}.png"
        filepath = self._base_dir / filename
        driver.save_screenshot(str(filepath))
        log.info("Appium screenshot saved: %s", filepath)
        return str(filepath)

    def capture_api_failure(self, test_name: str, error_message: str) -> str:
        """
        Genera una imagen PNG con el texto del error para pruebas de API.
        Si Pillow no está disponible, guarda un archivo .txt.
        Retorna la ruta del archivo generado.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{test_name}_{timestamp}"
        txt_path = self._base_dir / f"{filename}.txt"

        # Fallback si no hay Pillow
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap
        except ImportError:
            txt_path.write_text(f"Test: {test_name}\nError: {error_message}", encoding="utf-8")
            log.warning("Pillow not installed, saved error as text file: %s", txt_path)
            return str(txt_path)

        # Crear imagen con el error
        try:
            img = Image.new('RGB', (900, 500), color='white')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 16)
            except IOError:
                font = ImageFont.load_default()

            header = f"TEST FAILED: {test_name}"
            body = f"Error: {error_message}"
            wrapped_header = textwrap.fill(header, width=80)
            wrapped_body = textwrap.fill(body, width=80)
            full_text = wrapped_header + "\n\n" + wrapped_body

            y = 20
            for line in full_text.splitlines():
                draw.text((20, y), line, fill='red', font=font)
                y += 20

            png_path = self._base_dir / f"{filename}.png"
            img.save(str(png_path))
            log.info("API failure screenshot saved: %s", png_path)
            return str(png_path)

        except Exception as e:
            log.error("Failed to create API failure image: %s", e)
            txt_path.write_text(f"Test: {test_name}\nError: {error_message}", encoding="utf-8")
            return str(txt_path)