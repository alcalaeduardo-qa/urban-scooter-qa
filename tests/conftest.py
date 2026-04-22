from __future__ import annotations
from typing import Any, Generator

import pytest
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from components.api.api_client import CourierApiClient, OrderApiClient
from components.web.pages import HomePage, OrderFormPage, OrderStatusPage
from config import settings
from models.test_entities import CourierCredentials, OrderResult
from utils.db_connector import DatabaseConnector
from utils.excel_handler import ExcelHandler
from utils.logger import get_logger
from utils.server_manager import ServerManager

log = get_logger("conftest")


# ── Server ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def server_manager() -> Generator[ServerManager, None, None]:
    sm = ServerManager()
    if not sm.wait_until_ready(timeout=15):
        pytest.skip(
            f"Server at {settings.server.base_url} is not reachable. "
            "Start the server and update SERVER_BASE_URL in .env"
        )
    log.info("[fixture] Server is up at %s", settings.server.base_url)
    yield sm


# ── Database ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db(server_manager: ServerManager) -> Generator[DatabaseConnector, None, None]:  # noqa: ARG001
    connector = DatabaseConnector()
    connector.connect()
    yield connector
    connector.disconnect()


# ── API Clients ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def courier_api() -> Generator[CourierApiClient, None, None]:
    client = CourierApiClient()
    yield client
    client.close()


@pytest.fixture(scope="module")
def order_api() -> Generator[OrderApiClient, None, None]:
    client = OrderApiClient()
    yield client
    client.close()


# ── Courier / Order helpers ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def valid_courier(courier_api: CourierApiClient) -> CourierCredentials:
    credentials = courier_api.create_valid_courier()
    courier_api.login_and_get_id(credentials)
    return credentials


@pytest.fixture()
def valid_order(browser_context: BrowserContext, server_manager: ServerManager) -> OrderResult:
    from components.web.pages import HomePage, OrderFormPage
    from config.settings import test_data, server as srv_cfg
    
    page = browser_context.new_page()
    page.goto(srv_cfg.base_url)
    
    home = HomePage(page)
    # Handle the cookie banner if it exists before clicking
    try:
        page.locator('#rcc-confirm-button').click(timeout=1000)
    except Exception:
        pass
        
    home.click_order_button()
    
    order_page = OrderFormPage(page)
    track = order_page.create_order_via_ui(
        first_name=test_data.order_first_name,
        last_name=test_data.order_last_name,
        address=test_data.order_address,
        metro_station=test_data.order_metro_station,
        phone=test_data.order_phone,
        delivery_days=test_data.order_rental_days,
        rent_days=test_data.order_rental_days,
        comment=test_data.order_comment
    )
    page.close()
    return OrderResult(track=track, order_id=None)


# ── Playwright (instancia compartida Opera + Chrome) ──────────────────────────
# Solo se crea UN sync_playwright() por sesión para evitar el error
# "Sync API inside asyncio loop" que ocurre cuando Appium arranca su event loop
# antes de que Chrome intente crear una segunda instancia playwright.

@pytest.fixture(scope="session")
def _playwright_instance():
    """Instancia playwright única compartida por Opera y Chrome."""
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser_session(_playwright_instance) -> Generator[Browser, None, None]:
    """Navegador Opera (o Chromium si opera_executable no está configurado)."""
    launch_opts: dict = {
        "headless": settings.browser.headless,
        "slow_mo": settings.browser.slow_mo,
        "args": ["--start-maximized"],
    }
    if settings.browser.opera_executable:
        launch_opts["executable_path"] = settings.browser.opera_executable
    browser = _playwright_instance.chromium.launch(**launch_opts)
    log.info("[fixture] Browser launched")
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def chrome_browser_session(_playwright_instance) -> Generator[Browser, None, None]:
    """Chromium estándar. En sistemas donde el Chromium de Playwright no está disponible
    (ej. Fedora 43) se usa Opera como fallback — ambos son Chromium-based.
    ch-04 documenta el bug del popup de Chrome independientemente del binario usado.
    """
    import shutil

    # Intentar Chrome/Chromium del sistema primero
    system_chrome = (
        shutil.which("google-chrome") or
        shutil.which("chromium") or
        shutil.which("chromium-browser")
    )

    launch_opts: dict = {
        "headless": settings.browser.headless,
        "slow_mo": settings.browser.slow_mo,
        "args": ["--start-maximized"],
    }

    if system_chrome:
        launch_opts["executable_path"] = system_chrome
        log.info("[fixture] Chrome browser launched (system: %s)", system_chrome)
    elif settings.browser.opera_executable:
        # Fallback: Opera es Chromium-based y funciona en este sistema
        launch_opts["executable_path"] = settings.browser.opera_executable
        log.info("[fixture] Chrome browser launched (Opera fallback: %s)", settings.browser.opera_executable)
    else:
        log.info("[fixture] Chrome browser launched (Playwright bundled Chromium)")

    browser = _playwright_instance.chromium.launch(**launch_opts)
    yield browser
    browser.close()


@pytest.fixture()
def chrome_browser_context(chrome_browser_session: Browser) -> Generator[BrowserContext, None, None]:
    """Contexto Chromium fresco para cada test Chrome."""
    context = chrome_browser_session.new_context(
        viewport={"width": settings.browser.viewport_width,
                  "height": settings.browser.viewport_height},
    )
    context.set_default_timeout(settings.browser.default_timeout)
    yield context
    context.close()


@pytest.fixture()
def browser_context(browser_session: Browser) -> Generator[BrowserContext, None, None]:
    context = browser_session.new_context(
        viewport={"width": settings.browser.viewport_width,
                  "height": settings.browser.viewport_height},
    )
    context.set_default_timeout(settings.browser.default_timeout)
    yield context
    context.close()


@pytest.fixture()
def page(browser_context: BrowserContext, server_manager: ServerManager) -> Generator[Page, None, None]:  # noqa: ARG001
    pg = browser_context.new_page()
    pg.goto(settings.server.base_url, wait_until="networkidle")
    yield pg
    pg.close()


@pytest.fixture()
def chrome_page(chrome_browser_context: BrowserContext, server_manager: ServerManager) -> Generator[Page, None, None]:  # noqa: ARG001
    """Página Chrome fresca para cada test."""
    pg = chrome_browser_context.new_page()
    pg.goto(settings.server.base_url, wait_until="networkidle")
    yield pg
    pg.close()


@pytest.fixture()
def home_page(page: Page) -> HomePage:
    return HomePage(page)


@pytest.fixture()
def order_form_page(page: Page) -> OrderFormPage:
    hp = HomePage(page)
    return hp.click_order_button()


@pytest.fixture()
def order_status_page(page: Page) -> OrderStatusPage:
    hp = HomePage(page)
    return hp.click_order_status_button()


# ── Appium ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def appium_driver() -> Generator[Any, None, None]:
    try:
        import appium.webdriver as _aw
        from appium.options.android import UiAutomator2Options
    except ImportError:
        pytest.skip("appium-python-client not installed")
        return

    mob = settings.mobile
    try:
        options = UiAutomator2Options()
        options.platform_version  = mob.platform_version
        options.device_name       = mob.device_name
        options.app_package       = mob.app_package
        options.app_activity      = mob.app_activity
        options.new_command_timeout = mob.new_command_timeout
        options.no_reset          = False
        options.auto_grant_permissions = True
        if mob.apk_path:
            options.app = mob.apk_path
        driver = _aw.Remote(mob.appium_server, options=options)
    except Exception as exc:
        pytest.fail(f"Appium no disponible — activa Appium antes de correr los tests móviles: {exc}")
        return

    driver.implicitly_wait(mob.implicit_wait)
    log.info("[fixture] Appium session started on %s", mob.device_name)
    
    # ── Grant notification permission ────────────────────────────────────────────
    # KNOWN BUG: com.yandex.samokat does NOT request POST_NOTIFICATIONS permission
    # at startup, so Android 13 blocks all push notifications by default.
    # The app should show a permission dialog on first launch — it does not (UX bug).
    # Workaround: grant via AppOps (required because the app has not declared
    # POST_NOTIFICATIONS in its manifest, so 'pm grant' fails with SecurityException).
    import subprocess as _sp
    _sp.run(
        ["adb", "-s", mob.device_name, "shell",
         "cmd", "appops", "set", mob.app_package, "POST_NOTIFICATION", "allow"],
        capture_output=True,
    )
    log.info("[fixture] POST_NOTIFICATION permission granted via appops for %s", mob.app_package)
    # ─────────────────────────────────────────────────────────────────────────────
    
    yield driver
    driver.quit()


@pytest.fixture(scope="module")
def mobile_login_page(appium_driver: Any, server_manager: ServerManager) -> Any:  # noqa: ARG001
    from components.mobile.mobile_app import LoginPage
    lp = LoginPage(appium_driver)
    lp.configure_backend_url(settings.server.base_url)
    return lp


@pytest.fixture(scope="module")
def mobile_order_list(mobile_login_page: Any) -> Any:
    return mobile_login_page.login(settings.mobile.mobile_login, settings.mobile.mobile_password)


@pytest.fixture()
def network_helper(appium_driver: Any) -> Any:
    from components.mobile.mobile_app import NetworkHelper
    return NetworkHelper(appium_driver)


# ── Excel Handlers ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def excel_t2_checklist() -> Generator[ExcelHandler, None, None]:
    handler = ExcelHandler.for_tarea2_checklist()
    yield handler
    handler.save()


@pytest.fixture(scope="session")
def excel_t2_validation() -> Generator[ExcelHandler, None, None]:
    handler = ExcelHandler.for_tarea2_validation()
    yield handler
    handler.save()


@pytest.fixture(scope="session")
def excel_t3_cases() -> Generator[ExcelHandler, None, None]:
    handler = ExcelHandler.for_tarea3_cases()
    yield handler
    handler.save()


@pytest.fixture(scope="session")
def excel_t4_checklist() -> Generator[ExcelHandler, None, None]:
    handler = ExcelHandler.for_tarea4_checklist()
    yield handler
    handler.save()


@pytest.fixture(scope="session")
def excel_t5_opera() -> Generator[ExcelHandler, None, None]:
    handler = ExcelHandler.for_tarea5_opera()
    yield handler
    handler.save()


@pytest.fixture(scope="session")
def excel_t5_chrome() -> Generator[ExcelHandler, None, None]:
    handler = ExcelHandler.for_tarea5_chrome()
    yield handler
    handler.save()


# ── Hook ──────────────────────────────────────────────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
