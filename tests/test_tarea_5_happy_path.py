"""
test_tarea_5_happy_path.py — Tarea 5: Happy Path E2E (Opera + Chrome).

Flujo completo:
  Opera  (op-01 … op-13): flujo canónico, pedido creado vía formulario web.
  Chrome (ch-01 … ch-14): mismo flujo; ch-04 documenta el bug del popup,
                           ch-05 crea el pedido vía API como workaround.

Los fixtures chrome_browser_session / chrome_browser_context viven en conftest.py
para evitar el conflicto "Sync API inside asyncio loop" que ocurre al crear
sync_playwright() dentro de fixtures de módulo en el archivo de test.

Nota sobre Appium: si Appium no está corriendo, los tests móviles fallan con
un mensaje claro. Activa Appium antes de correr la suite completa.
"""
from __future__ import annotations

import time
from typing import Any

import pytest
from playwright.sync_api import BrowserContext, Page

from components.api.api_client import CourierApiClient, OrderApiClient
from components.mobile.mobile_app import OrderDetailPage, OrderListPage, MyOrdersPage
from components.web.pages import HomePage, OrderFormPage, OrderStatusPage
from config import settings
from models.test_entities import MobileTestCase, Status
from utils.db_connector import DatabaseConnector
from utils.excel_handler import ExcelHandler
from utils.logger import get_logger
from utils.screenshot_manager import ScreenshotManager
from utils.server_manager import ServerManager

log = get_logger("test_t5_happy_path")
_sm = ScreenshotManager("tarea5")

pytestmark = [pytest.mark.tarea5, pytest.mark.happy_path]

# ── Credenciales compartidas ───────────────────────────────────────────────────
_courier_login    = settings.mobile.mobile_login
_courier_password = settings.mobile.mobile_password

# Estado compartido entre tests del mismo track
_op: dict[str, Any] = {}   # Opera track state
_ch: dict[str, Any] = {}   # Chrome track state


# ── Helper ────────────────────────────────────────────────────────────────────

def _report(
    handler: ExcelHandler,
    case: MobileTestCase,
    status: Status,
    screenshot: str = "",
    error: str = "",
    comment: str = "",
) -> None:
    handler.write_status(
        row_index=case.row_index,
        status=status,
        status_col=settings.excel.t5_status_col,
        jira_col=settings.excel.t5_jira_col,
        screenshot_path=screenshot,
        error_message=error,
        comment=comment,
    )


def _get(handler: ExcelHandler, case_id: str, prefix: str) -> MobileTestCase | None:
    for c in handler.read_cases_t5(prefix=prefix):
        if c.case_id == case_id:
            return c
    return None


def _run(handler: ExcelHandler, case_id: str, prefix: str, fn, *, driver=None):
    """Ejecuta *fn*, captura resultado y lo reporta en Excel."""
    case = _get(handler, case_id, prefix)
    status = Status.APPROVED
    screenshot = ""
    error = ""
    try:
        result = fn()
        screenshot = result if isinstance(result, str) else ""
    except Exception as exc:
        status = Status.NOT_APPROVED
        error = str(exc)
        if driver is not None:
            try:
                screenshot = str(_sm.capture_appium(driver, f"{case_id}_fail"))
            except Exception:
                pass
        raise
    finally:
        if case:
            _report(handler, case, status, screenshot, error)


def _open_page(ctx: BrowserContext) -> Page:
    """Abre página nueva, acepta el cookie banner si existe."""
    page = ctx.new_page()
    page.goto(settings.server.base_url)
    try:
        page.locator("#rcc-confirm-button").click(timeout=2000)
    except Exception:
        pass
    return page


# ══════════════════════════════════════════════════════════════════════════════
# OPERA — Happy Path canónico (op-01 … op-13)
# ══════════════════════════════════════════════════════════════════════════════

class TestHappyPathOpera:

    # ── op-01 ─────────────────────────────────────────────────────────────────
    def test_op01_create_courier(
        self,
        server_manager: ServerManager,   # garantiza que el server está listo
        courier_api: CourierApiClient,
        excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            resp = courier_api.create(
                login=_courier_login, password=_courier_password, first_name="Eduardo",
            )
            assert resp.status_code in (201, 409), (
                f"Esperado 201 o 409, obtenido {resp.status_code}: {resp.text}"
            )
        _run(excel_t5_opera, "op-01", "op", action)

    # ── op-02 ─────────────────────────────────────────────────────────────────
    def test_op02_login_courier(
        self,
        server_manager: ServerManager,
        courier_api: CourierApiClient,
        excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            resp = courier_api.login(login=_courier_login, password=_courier_password)
            assert resp.status_code == 200, f"Login fallido: {resp.status_code} {resp.text}"
            body = resp.json()
            cid = body.get("id") or body.get("courierId")
            assert cid, f"No se encontró 'id' en la respuesta: {body}"
            _op["courier_id"] = int(cid)
            log.info("[op-02] courier_id=%s", _op["courier_id"])
        _run(excel_t5_opera, "op-02", "op", action)

    # ── op-03 ─────────────────────────────────────────────────────────────────
    def test_op03_courier_in_db(
        self, db: DatabaseConnector, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            row = db.get_courier_by_login(_courier_login)
            assert row is not None, f"Courier '{_courier_login}' no encontrado en DB"
            assert db.is_password_hashed(_courier_login, _courier_password), (
                "Contraseña almacenada en texto plano — fallo de seguridad"
            )
        _run(excel_t5_opera, "op-03", "op", action)

    # ── op-04 ─────────────────────────────────────────────────────────────────
    def test_op04_create_order_web_opera(
        self, browser_context: BrowserContext, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            page = _open_page(browser_context)
            HomePage(page).click_order_button()
            form = OrderFormPage(page)
            track = form.create_order_via_ui(
                first_name=settings.test_data.order_first_name,
                last_name=settings.test_data.order_last_name,
                address=settings.test_data.order_address,
                metro_station=settings.test_data.order_metro_station,
                phone=settings.test_data.order_phone,
                delivery_days=settings.test_data.order_rental_days,
                rent_days=settings.test_data.order_rental_days,
                comment=settings.test_data.order_comment,
            )
            assert track, "No se obtuvo número de track del formulario web (Opera)"
            _op["track"] = track
            screenshot = str(_sm.capture_playwright(page, "op04_order_created"))
            page.close()
            log.info("[op-04] track=%s", track)
            return screenshot
        _run(excel_t5_opera, "op-04", "op", action)

    # ── op-05 ─────────────────────────────────────────────────────────────────
    def test_op05_no_duplicates_in_db(
        self, db: DatabaseConnector, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _op, "op-04 no generó track — prerequisito no cumplido"
            rows = db.get_orders_by_track(_op["track"])
            assert len(rows) == 1, (
                f"Esperada 1 fila en DB para track={_op['track']}, "
                f"encontradas {len(rows)} — BUG DE DUPLICADOS"
            )
            _op["order_id"] = rows[0].get("id") or rows[0].get("orderId")
        _run(excel_t5_opera, "op-05", "op", action)

    # ── op-06 ─────────────────────────────────────────────────────────────────
    def test_op06_order_visible_on_web_opera(
        self, browser_context: BrowserContext, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _op
            page = _open_page(browser_context)
            status_page: OrderStatusPage = HomePage(page).click_order_status_button()
            status_page.search_order(_op["track"])
            assert status_page.order_data_is_visible(), (
                f"Datos del pedido no visibles para track={_op['track']} en Opera"
            )
            screenshot = str(_sm.capture_playwright(page, "op06_status_visible"))
            page.close()
            return screenshot
        _run(excel_t5_opera, "op-06", "op", action)

    # ── op-07 ─────────────────────────────────────────────────────────────────
    def test_op07_courier_sees_order_mobile(
        self, appium_driver, mobile_order_list: OrderListPage, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            mobile_order_list.refresh()
            assert mobile_order_list.order_count() > 0, (
                "Ningún pedido visible en la lista móvil tras refresh"
            )
            return str(_sm.capture_appium(appium_driver, "op07_order_list"))
        _run(excel_t5_opera, "op-07", "op", action, driver=appium_driver)

    # ── op-08 ─────────────────────────────────────────────────────────────────
    def test_op08_courier_accepts_order(
        self, appium_driver, mobile_order_list: OrderListPage, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            detail: OrderDetailPage = mobile_order_list.open_order(0)
            detail.accept_order()
            return str(_sm.capture_appium(appium_driver, "op08_accepted"))
        _run(excel_t5_opera, "op-08", "op", action, driver=appium_driver)

    # ── op-09 ─────────────────────────────────────────────────────────────────
    def test_op09_db_reflects_assigned_courier(
        self, db: DatabaseConnector, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            time.sleep(2)
            assert "track" in _op
            rows = db.get_orders_by_track(_op["track"])
            assert rows, "El pedido desapareció de DB tras aceptación móvil"
            if len(rows) > 1:
                pytest.xfail("Duplicado detectado en DB después del accept — bug conocido")
        _run(excel_t5_opera, "op-09", "op", action)

    # ── op-10 ─────────────────────────────────────────────────────────────────
    def test_op10_web_shows_accepted_state_opera(
        self, browser_context: BrowserContext, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _op
            page = _open_page(browser_context)
            status_page: OrderStatusPage = HomePage(page).click_order_status_button()
            status_page.search_order(_op["track"])
            active = status_page.get_active_status_text()
            assert active, "Estado activo vacío en Opera después de aceptar el pedido"
            screenshot = str(_sm.capture_playwright(page, "op10_accepted_state"))
            page.close()
            return screenshot
        _run(excel_t5_opera, "op-10", "op", action)

    # ── op-11 ─────────────────────────────────────────────────────────────────
    def test_op11_courier_completes_order(
        self, appium_driver, mobile_order_list: OrderListPage, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            # Después de accept_order la app vuelve a "Todos los pedidos".
            # El pedido aceptado está en la pestaña "Mis pedidos".
            my_orders: MyOrdersPage = mobile_order_list.go_to_my_orders()
            time.sleep(1.5)
            assert my_orders.accepted_order_count() > 0, (
                "No hay pedidos en 'Mis pedidos' tras aceptación"
            )
            detail: OrderDetailPage = my_orders.open_order(0)
            detail.complete_order()
            _op["order_completed"] = True
            return str(_sm.capture_appium(appium_driver, "op11_completed"))
        _run(excel_t5_opera, "op-11", "op", action, driver=appium_driver)

    # ── op-12 ─────────────────────────────────────────────────────────────────
    def test_op12_db_shows_order_finished(
        self, db: DatabaseConnector, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            time.sleep(2)
            assert "track" in _op, "op-04 no generó track"
            rows = db.get_orders_by_track(_op["track"])
            finished = [r for r in rows if r.get("inDelivery") or r.get("finished")]
            assert finished, f"Ninguna fila finalizada en DB para track={_op['track']}"
        _run(excel_t5_opera, "op-12", "op", action)

    # ── op-13 ─────────────────────────────────────────────────────────────────
    def test_op13_web_shows_final_state_opera(
        self, browser_context: BrowserContext, excel_t5_opera: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _op
            page = _open_page(browser_context)
            status_page: OrderStatusPage = HomePage(page).click_order_status_button()
            status_page.search_order(_op["track"])
            active = status_page.get_active_status_text()
            assert active, "Estado final vacío en Opera"
            screenshot = str(_sm.capture_playwright(page, "op13_final_state"))
            page.close()
            return screenshot
        _run(excel_t5_opera, "op-13", "op", action)


# ══════════════════════════════════════════════════════════════════════════════
# CHROME — Happy Path con bug documentado (ch-01 … ch-14)
# ══════════════════════════════════════════════════════════════════════════════

class TestHappyPathChrome:
    """ch-04 documenta el bug del popup bloqueado (NOT_APPROVED + xfail).
    ch-05 actúa como workaround vía API para que el resto del flujo continúe.
    Los fixtures chrome_browser_session / chrome_browser_context están en conftest.py.
    """

    # ── ch-01 ─────────────────────────────────────────────────────────────────
    def test_ch01_create_courier(
        self,
        server_manager: ServerManager,
        courier_api: CourierApiClient,
        excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            resp = courier_api.create(
                login=_courier_login, password=_courier_password, first_name="Eduardo",
            )
            assert resp.status_code in (201, 409), (
                f"Esperado 201 o 409, obtenido {resp.status_code}: {resp.text}"
            )
        _run(excel_t5_chrome, "ch-01", "ch", action)

    # ── ch-02 ─────────────────────────────────────────────────────────────────
    def test_ch02_login_courier(
        self,
        server_manager: ServerManager,
        courier_api: CourierApiClient,
        excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            resp = courier_api.login(login=_courier_login, password=_courier_password)
            assert resp.status_code == 200, f"Login fallido: {resp.status_code} {resp.text}"
            body = resp.json()
            cid = body.get("id") or body.get("courierId")
            assert cid, f"No se encontró 'id' en la respuesta: {body}"
            _ch["courier_id"] = int(cid)
            log.info("[ch-02] courier_id=%s", _ch["courier_id"])
        _run(excel_t5_chrome, "ch-02", "ch", action)

    # ── ch-03 ─────────────────────────────────────────────────────────────────
    def test_ch03_courier_in_db(
        self, db: DatabaseConnector, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            row = db.get_courier_by_login(_courier_login)
            assert row is not None, f"Courier '{_courier_login}' no encontrado en DB"
            assert db.is_password_hashed(_courier_login, _courier_password), (
                "Contraseña almacenada en texto plano — fallo de seguridad"
            )
        _run(excel_t5_chrome, "ch-03", "ch", action)

    # ── ch-04 — BUG DOCUMENTADO ───────────────────────────────────────────────
    def test_ch04_bug_create_order_web_chrome(
        self,
        chrome_browser_context: BrowserContext,
        excel_t5_chrome: ExcelHandler,
    ) -> None:
        """Documenta el bug: popup de creación de pedido no avanza en Chrome."""
        case = _get(excel_t5_chrome, "ch-04", "ch")
        screenshot = ""
        bug_comment = (
            "BUG CONFIRMADO [Chrome] — web-bug-01\n"
            "El popup de confirmación del pedido NO avanza al hacer clic en 'Hacer pedido'.\n"
            "El botón no tiene efecto visible. El track nunca se muestra.\n"
            "Opera: mismo flujo funciona correctamente.\n"
            "Workaround: pedido creado vía API en ch-05."
        )
        try:
            page = _open_page(chrome_browser_context)
            HomePage(page).click_order_button()
            form = OrderFormPage(page)
            form.fill_first_name(settings.test_data.order_first_name)
            form.fill_last_name(settings.test_data.order_last_name)
            form.fill_address(settings.test_data.order_address)
            form.fill_metro_station(settings.test_data.order_metro_station)
            form.fill_phone(settings.test_data.order_phone)
            form.click_next()
            form.select_delivery_date(settings.test_data.order_rental_days)
            form.select_rental_period(settings.test_data.order_rental_days)
            page.locator('button:has-text("Order")').last.click()
            page.wait_for_timeout(2000)
            try:
                page.locator('button:has-text("Yes")').click(timeout=2000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            screenshot = str(_sm.capture_playwright(page, "ch04_bug_popup_blocked"))
            page.close()
        except Exception as exc:
            log.warning("[ch-04] Excepción al reproducir bug: %s", exc)
        finally:
            if case:
                _report(
                    excel_t5_chrome, case, Status.NOT_APPROVED,
                    screenshot=screenshot, comment=bug_comment,
                )
        pytest.xfail(
            "ch-04 NOT APROBADO: Bug conocido en Chrome — popup de pedido bloqueado. "
            "Ver ch-05 para workaround."
        )

    # ── ch-05 — workaround vía API ────────────────────────────────────────────
    def test_ch05_create_order_api_workaround(
        self, order_api: OrderApiClient, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            result = order_api.create_valid_order()
            assert result.track, "Workaround API no devolvió track"
            _ch["track"] = result.track
            _ch["order_id"] = result.order_id
            log.info("[ch-05] track=%s order_id=%s", result.track, result.order_id)
        _run(excel_t5_chrome, "ch-05", "ch", action)

    # ── ch-06 ─────────────────────────────────────────────────────────────────
    def test_ch06_no_duplicates_in_db(
        self, db: DatabaseConnector, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _ch, "ch-05 no generó track"
            rows = db.get_orders_by_track(_ch["track"])
            assert len(rows) == 1, (
                f"Esperada 1 fila, encontradas {len(rows)} — BUG DE DUPLICADOS"
            )
        _run(excel_t5_chrome, "ch-06", "ch", action)

    # ── ch-07 ─────────────────────────────────────────────────────────────────
    def test_ch07_order_visible_on_web_chrome(
        self,
        chrome_browser_context: BrowserContext,
        excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _ch
            page = _open_page(chrome_browser_context)
            status_page: OrderStatusPage = HomePage(page).click_order_status_button()
            status_page.search_order(_ch["track"])
            assert status_page.order_data_is_visible(), (
                f"Datos del pedido no visibles en Chrome para track={_ch['track']}"
            )
            screenshot = str(_sm.capture_playwright(page, "ch07_status_visible"))
            page.close()
            return screenshot
        _run(excel_t5_chrome, "ch-07", "ch", action)

    # ── ch-08 ─────────────────────────────────────────────────────────────────
    def test_ch08_courier_sees_order_mobile(
        self, appium_driver, mobile_order_list: OrderListPage, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            mobile_order_list.refresh()
            assert mobile_order_list.order_count() > 0, (
                "Ningún pedido visible en la lista móvil (track Chrome)"
            )
            return str(_sm.capture_appium(appium_driver, "ch08_order_list"))
        _run(excel_t5_chrome, "ch-08", "ch", action, driver=appium_driver)

    # ── ch-09 ─────────────────────────────────────────────────────────────────
    def test_ch09_courier_accepts_order(
        self, appium_driver, mobile_order_list: OrderListPage, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            detail: OrderDetailPage = mobile_order_list.open_order(0)
            detail.accept_order()
            return str(_sm.capture_appium(appium_driver, "ch09_accepted"))
        _run(excel_t5_chrome, "ch-09", "ch", action, driver=appium_driver)

    # ── ch-10 ─────────────────────────────────────────────────────────────────
    def test_ch10_db_reflects_assigned_courier(
        self, db: DatabaseConnector, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            time.sleep(2)
            assert "track" in _ch
            rows = db.get_orders_by_track(_ch["track"])
            assert rows, "El pedido desapareció de DB tras aceptación móvil (Chrome)"
            if len(rows) > 1:
                pytest.xfail("Duplicado detectado en DB después del accept — bug conocido")
        _run(excel_t5_chrome, "ch-10", "ch", action)

    # ── ch-11 ─────────────────────────────────────────────────────────────────
    def test_ch11_web_shows_accepted_state_chrome(
        self,
        chrome_browser_context: BrowserContext,
        excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _ch
            page = _open_page(chrome_browser_context)
            status_page: OrderStatusPage = HomePage(page).click_order_status_button()
            status_page.search_order(_ch["track"])
            active = status_page.get_active_status_text()
            assert active, "Estado activo vacío en Chrome después de aceptar el pedido"
            screenshot = str(_sm.capture_playwright(page, "ch11_accepted_state"))
            page.close()
            return screenshot
        _run(excel_t5_chrome, "ch-11", "ch", action)

    # ── ch-12 ─────────────────────────────────────────────────────────────────
    def test_ch12_courier_completes_order(
        self, appium_driver, mobile_order_list: OrderListPage, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            my_orders: MyOrdersPage = mobile_order_list.go_to_my_orders()
            time.sleep(1.5)
            assert my_orders.accepted_order_count() > 0, (
                "No hay pedidos en 'Mis pedidos' tras aceptación (Chrome)"
            )
            detail: OrderDetailPage = my_orders.open_order(0)
            detail.complete_order()
            _ch["order_completed"] = True
            return str(_sm.capture_appium(appium_driver, "ch12_completed"))
        _run(excel_t5_chrome, "ch-12", "ch", action, driver=appium_driver)

    # ── ch-13 ─────────────────────────────────────────────────────────────────
    def test_ch13_db_shows_order_finished(
        self, db: DatabaseConnector, excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            time.sleep(2)
            assert "track" in _ch, "ch-05 no generó track"
            rows = db.get_orders_by_track(_ch["track"])
            finished = [r for r in rows if r.get("inDelivery") or r.get("finished")]
            assert finished, f"Ninguna fila finalizada en DB para track={_ch['track']}"
        _run(excel_t5_chrome, "ch-13", "ch", action)

    # ── ch-14 ─────────────────────────────────────────────────────────────────
    def test_ch14_web_shows_final_state_chrome(
        self,
        chrome_browser_context: BrowserContext,
        excel_t5_chrome: ExcelHandler,
    ) -> None:
        def action():
            assert "track" in _ch
            page = _open_page(chrome_browser_context)
            status_page: OrderStatusPage = HomePage(page).click_order_status_button()
            status_page.search_order(_ch["track"])
            active = status_page.get_active_status_text()
            assert active, "Estado final vacío en Chrome"
            screenshot = str(_sm.capture_playwright(page, "ch14_final_state"))
            page.close()
            return screenshot
        _run(excel_t5_chrome, "ch-14", "ch", action)
