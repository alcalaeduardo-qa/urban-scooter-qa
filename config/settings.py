"""
Centralized configuration. All values come from environment variables.
The .env file is loaded automatically at import time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ROOT_DIR = Path(__file__).resolve().parent.parent
EXCEL_TEMPLATES_DIR = ROOT_DIR / "excel_templates"
RESULTS_DIR = ROOT_DIR / "results"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
LOGS_DIR = ROOT_DIR / "logs"


for _dir in (RESULTS_DIR, SCREENSHOTS_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ServerConfig:
    base_url: str = os.getenv("SERVER_BASE_URL", "http://localhost:3000").rstrip("/")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:3000/api/v1").rstrip("/")
    health_check_timeout: int = 30
    health_check_interval: float = 1.0


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    name: str = os.getenv("DB_NAME", "scooter_rent")
    user: str = os.getenv("DB_USER", "morty")
    password: str = os.getenv("DB_PASSWORD", "")
    ssh_host: str = os.getenv("SSH_HOST", "")
    ssh_port: int = int(os.getenv("SSH_PORT", "4554"))
    ssh_user: str = os.getenv("SSH_USER", "")
    ssh_key_path: str = os.getenv("SSH_KEY_PATH", "").strip()

    @property
    def uses_ssh_tunnel(self) -> bool:
        return bool(self.ssh_host and self.ssh_user)


@dataclass(frozen=True)
class BrowserConfig:
    opera_executable: str = os.getenv("OPERA_EXECUTABLE_PATH", "")
    headless: bool = os.getenv("HEADLESS", "false").lower() == "true"
    slow_mo: int = int(os.getenv("SLOW_MO", "0"))
    default_timeout: int = int(os.getenv("BROWSER_TIMEOUT", "15000"))
    viewport_width: int = 1280
    viewport_height: int = 720


@dataclass(frozen=True)
class MobileConfig:
    appium_server: str = os.getenv("APPIUM_SERVER", "http://127.0.0.1:4723")
    platform_name: str = "Android"
    platform_version: str = os.getenv("ANDROID_VERSION", "13")
    device_name: str = os.getenv("DEVICE_NAME", "emulator-5554")
    app_package: str = os.getenv("APP_PACKAGE", "com.yandex.samokat")
    app_activity: str = os.getenv("APP_ACTIVITY", "com.yandex.scooter.app.ui.main.MainActivity")
    apk_path: str = os.getenv("APK_PATH", "")
    implicit_wait: int = int(os.getenv("APPIUM_IMPLICIT_WAIT", "10"))
    new_command_timeout: int = 300
    mobile_login: str = os.getenv("MOBILE_LOGIN", "")
    mobile_password: str = os.getenv("MOBILE_PASSWORD", "")


@dataclass(frozen=True)
class RetryConfig:
    api_max_attempts: int = 3
    api_delay_seconds: float = 1.0
    web_max_attempts: int = 2
    web_delay_seconds: float = 2.0
    mobile_max_attempts: int = 2
    mobile_delay_seconds: float = 2.0
    db_max_attempts: int = 3
    db_delay_seconds: float = 1.5


@dataclass(frozen=True)
class TestDataConfig:
    courier_login_prefix: str = "test_courier_"
    courier_password: str = "Test@1234"
    courier_first_name: str = "AutoTest"
    order_first_name: str = "Diana"
    order_last_name: str = "Islas"
    order_address: str = "Main St. 123"
    order_metro_station: str = "Ginger cats"
    order_phone: str = "12345678901"
    order_rental_days: int = 1
    order_comment: str = "Auto test order"


@dataclass(frozen=True)
class ExcelConfig:
    tarea_2_checklist: str = "Tarea_2_lista_de_comprobación.xlsx"
    tarea_2_validation: str = "Tarea_2_validación_de_datos.xlsx"
    tarea_3_cases: str = "Tarea_3_casos_de_prueba.xlsx"
    tarea_4_checklist: str = "Tarea_4_lista_de_comprobación.xlsx"
    tarea_5_happy_path: str = "Tarea_5_happy_path.xlsx"
    t2_checklist_opera_col: int = 2   # col C — Opera
    t2_checklist_chrome_col: int = 3  # col D — Chrome
    t2_checklist_jira_col: int = 4    # col E — Jira (shifted)
    t2_checklist_status_col: int = 2  # backwards compat alias → opera col
    t2_validation_opera_col: int = 7  # col H — Opera
    t2_validation_chrome_col: int = 8 # col I — Chrome
    t2_validation_jira_col: int = 9   # col J — Jira (shifted)
    t2_validation_status_col: int = 7 # backwards compat alias → opera col
    t3_status_col: int = 8       # Col I (0-based index 8) — "Estado (Aprobado/No Aprobado)"
    t3_jira_col: int = 9          # Col J (0-based index 9) — "Enlace al informe de errores"
    t3_comment_col: int = 10      # Col K (0-based index 10) — "Comentarios" (añadida para doc de bugs)
    t4_status_col: int = 4   # col E — "Estado (Aprobado/No Aprobado)"
    t4_jira_col: int = 5    # col F — "Enlace al informe de errores"
    t5_status_col: int = 8   # Col I — "Estado"
    t5_jira_col: int = 9     # Col J — "Enlace Jira"
    t5_comment_col: int = 10  # Col K — "Comentarios"
    header_row: int = 1


server = ServerConfig()
database = DatabaseConfig()
browser = BrowserConfig()
mobile = MobileConfig()
retry = RetryConfig()
test_data = TestDataConfig()
excel = ExcelConfig()
