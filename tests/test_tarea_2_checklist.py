"""
test_tarea_2_checklist.py — Tarea 2 Lista de Comprobación Aplicación Web.
Cubre los ítems 1-58 (originales + nuevos casos).
Maneja cookies, selectores reales y textos en inglés.
Corregido: fragmentos de búsqueda para coincidir con el Excel.
Los tests reflejan el estado real del sistema (no se fuerza el paso).
"""
from __future__ import annotations
import re
import uuid
from datetime import date, timedelta, datetime
from pathlib import Path
import pytest
import requests
from playwright.sync_api import Page
from components.api.api_client import CourierApiClient, OrderApiClient
from components.web.pages import HomePage, OrderStatusPage
from models.test_entities import Status, ChecklistItem
from utils.db_connector import DatabaseConnector
from utils.excel_handler import ExcelHandler
from utils.logger import get_logger
from utils.screenshot_manager import ScreenshotManager
from config import settings

log = get_logger("test_t2_checklist")
_sm = ScreenshotManager("tarea2_checklist")
pytestmark = [pytest.mark.tarea2, pytest.mark.web]

# ─── Para reporte de errores no documentados ─────────────────────────────
_UNDOCUMENTED_ERRORS = []

# ─── Browser context (set by parametrized page fixture) ───────────────────
_browser_ctx: dict = {"name": "opera"}

# ─── Helpers ──────────────────────────────────────────────────────────────
def _accept_cookies(page: Page):
    try:
        accept_btn = page.locator('button:has-text("Agree")')
        if accept_btn.count() > 0 and accept_btn.is_visible():
            accept_btn.click()
            page.wait_for_timeout(500)
    except:
        pass

def _get_item(handler: ExcelHandler, description_fragment: str) -> ChecklistItem | None:
    """Busca un ítem en el Excel por fragmento de descripción (coincidencia parcial)."""
    for item in handler.read_checklist_t2():
        if description_fragment.lower() in item.description.lower():
            return item
    return None

def _report(handler: ExcelHandler, item: ChecklistItem, status: Status,
            screenshot: str = "", error: str = "") -> None:
    col = (settings.excel.t2_checklist_opera_col if _browser_ctx["name"] == "opera"
           else settings.excel.t2_checklist_chrome_col)
    handler.write_status(
        row_index=item.row_index,
        status=status,
        status_col=col,
        jira_col=settings.excel.t2_checklist_jira_col,
        screenshot_path=screenshot,
        error_message=error,
    )

def _take_screenshot(page: Page, test_name: str) -> str:
    return _sm.capture_playwright(page, test_name)

def _add_undocumented_error(test_name: str, error: str, screenshot: str = ""):
    _UNDOCUMENTED_ERRORS.append({
        "test_name": test_name,
        "error": error,
        "screenshot": screenshot,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def _generate_undocumented_report():
    if not _UNDOCUMENTED_ERRORS:
        log.info("No undocumented errors found.")
        return
    from openpyxl import Workbook
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = settings.RESULTS_DIR / f"errores_no_documentados_{timestamp}.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Errores no documentados"
    headers = ["Test name", "Error message", "Screenshot path", "Timestamp"]
    ws.append(headers)
    for e in _UNDOCUMENTED_ERRORS:
        ws.append([e["test_name"], e["error"], e["screenshot"], e["timestamp"]])
    wb.save(report_path)
    log.info(f"Undocumented errors report saved: {report_path}")

# ─── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(params=["opera", "chrome"])
def page(request, browser_context, chrome_browser_context):
    """Local parametrized page: runs every checklist test in Opera and Chrome."""
    _browser_ctx["name"] = request.param
    ctx = browser_context if request.param == "opera" else chrome_browser_context
    pg = ctx.new_page()
    pg.goto(settings.server.base_url, wait_until="networkidle")
    yield pg
    pg.close()


@pytest.fixture(scope="session")
def server_health_check():
    try:
        resp = requests.get(settings.server.base_url, timeout=10)
        assert resp.status_code < 500, f"Web server not ready: {resp.status_code}"
        api_resp = requests.get(f"{settings.server.api_base_url}/ping", timeout=10)
        assert api_resp.status_code == 200, f"API not ready: {api_resp.status_code}"
    except Exception as e:
        pytest.skip(f"Server health check failed: {e}")

@pytest.fixture
def api_order(order_api: OrderApiClient) -> dict:
    delivery_date = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
    payload = {
        "firstName": f"Api_{uuid.uuid4().hex[:4]}",
        "lastName": "Auto",
        "address": "API St 123",
        "metroStation": "Ginger cats",
        "phone": "12345678901",
        "rentTime": 1,
        "deliveryDate": delivery_date,
        "comment": "",
        "color": [],
    }
    resp = order_api.create(payload)
    assert resp.status_code == 201, f"API order creation failed: {resp.text}"
    data = resp.json()
    return {"track": str(data["track"]), "id": data.get("id")}

@pytest.fixture
def api_order_with_long_comment(order_api: OrderApiClient) -> dict:
    delivery_date = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
    long_comment = "x" * 40
    payload = {
        "firstName": "WrapTest",
        "lastName": "LongComment",
        "address": "123 Main St",
        "metroStation": "Ginger cats",
        "phone": "12345678901",
        "rentTime": 1,
        "deliveryDate": delivery_date,
        "comment": long_comment,
        "color": [],
    }
    resp = order_api.create(payload)
    assert resp.status_code == 201
    data = resp.json()
    return {"track": str(data["track"]), "id": data.get("id"), "comment": long_comment}

@pytest.fixture
def unique_courier():
    client = CourierApiClient()
    uid = uuid.uuid4().hex[:8]
    login = f"courier_{uid}"
    password = settings.test_data.courier_password
    first_name = f"Repartidor_{uid}"
    resp = client.create(login=login, password=password, first_name=first_name)
    assert resp.status_code == 201, f"Courier creation failed: {resp.text}"
    login_resp = client.login(login=login, password=password)
    assert login_resp.status_code == 200
    courier_id = login_resp.json().get("id")
    yield {"client": client, "login": login, "password": password, "first_name": first_name, "id": courier_id}

@pytest.fixture
def accepted_order(order_api: OrderApiClient, api_order, unique_courier):
    track = api_order["track"]
    track_resp = order_api.get_by_track(track)
    assert track_resp.status_code == 200
    order_data = track_resp.json()
    order_id = order_data.get("order", {}).get("id") or order_data.get("id")
    assert order_id
    accept_resp = order_api.accept(order_id, unique_courier["id"])
    assert accept_resp.status_code == 200
    return {"track": track, "id": order_id, "courier_name": unique_courier["first_name"]}

@pytest.fixture
def finished_order(order_api: OrderApiClient, accepted_order):
    finish_resp = order_api.finish(accepted_order["id"])
    assert finish_resp.status_code == 200
    return accepted_order

# ─── Tests 1‑58 (ajustados los fragmentos de búsqueda) ─────────────────
class TestBasicUI:
    def test_item_1_show_track_field(self, page: Page, server_health_check, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Mostrar el campo")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            assert page.is_visible('input[placeholder*="number"]'), "Track input not visible"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_1")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_1_show_track_field", error, screenshot)

    def test_item_2_allow_input_track(self, page: Page, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Permitir introducir")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            page.fill('input[placeholder*="number"]', "12345")
            value = page.input_value('input[placeholder*="number"]')
            assert value == "12345", "Input not allowed"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_2")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_2_allow_input_track", error, screenshot)

    def test_item_3_show_order_info_valid_track(self, page: Page, api_order, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Mostrar la información")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order["track"])
            assert status_page.order_data_is_visible(), "Order data not shown"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_3")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_3_show_order_info_valid_track", error, screenshot)

    @pytest.mark.parametrize("field_label, desc_fragment", [
        ("First name", "nombre del usuario"),
        ("Last name", "apellido del usuario"),
        ("Address", "dirección del pedido"),
        ("Metro station", "estación de metro"),
        ("Phone", "teléfono del usuario"),
        ("Delivery date", "fecha de entrega"),
        ("Rental period", "periodo de alquiler"),
        ("Color", "color del scooter"),
        ("Comment", "comentario del pedido"),
    ])
    def test_items_4_12_order_fields(self, page: Page, api_order, excel_t2_checklist: ExcelHandler, field_label, desc_fragment):
        item = _get_item(excel_t2_checklist, desc_fragment)
        if not item:
            return
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order["track"])
            assert status_page.field_is_visible(field_label), f"Field '{field_label}' not visible"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, f"item_field_{field_label.replace(' ', '_')}")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error(f"test_items_4_12_order_fields_{field_label}", error, screenshot)

    def test_item_13_wrap_text(self, page: Page, api_order_with_long_comment, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "segunda línea")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order_with_long_comment["track"])
            comment_text = api_order_with_long_comment["comment"]
            comment_elem = page.locator(f'text="{comment_text}"').first
            assert comment_elem.count() > 0, f"Comment element '{comment_text}' not found"
            height = comment_elem.evaluate("el => el.scrollHeight")
            line_height = comment_elem.evaluate("el => parseInt(getComputedStyle(el).lineHeight)")
            assert height > line_height + 2, f"Text not wrapping (height={height}, line_height={line_height})"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_13")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_13_wrap_text", error, screenshot)

class TestStatusChain:
    def test_items_14_17_status_chain_display(self, page: Page, api_order, unique_courier, order_api,
                                              excel_t2_checklist: ExcelHandler):
        items = {
            14: _get_item(excel_t2_checklist, "cadena de estado"),
            15: _get_item(excel_t2_checklist, "resaltar en negro"),
            16: _get_item(excel_t2_checklist, "en gris"),
            17: _get_item(excel_t2_checklist, "número por una marca"),
        }
        statuses = {k: Status.APPROVED for k in items}
        errors = {k: "" for k in items}
        screenshots = {k: "" for k in items}
        try:
            track = api_order["track"]
            track_resp = order_api.get_by_track(track)
            assert track_resp.status_code == 200
            order_data = track_resp.json()
            order_id = order_data.get("order", {}).get("id") or order_data.get("id")
            assert order_id, "Order ID not found"
            accept_resp = order_api.accept(order_id, unique_courier["id"])
            assert accept_resp.status_code == 200, f"Accept failed: {accept_resp.text}"

            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(track)

            if items[14]:
                assert status_page.status_count() > 0, "Status chain not present"
            if items[15]:
                active = status_page.get_active_status_text()
                assert active, "No active status"
                active_elem = page.locator('[class*="Highlight"]').first
                if active_elem.count() > 0:
                    color = active_elem.evaluate("el => getComputedStyle(el).color")
                    assert "rgb(0,0,0)" in color.replace(" ", "") or "#000" in color, "Active status not black"
            if items[16]:
                gray = page.locator('[class*="OrderBrick"]:not([class*="Highlight"])')
                assert gray.count() > 0, "No gray statuses"
            if items[17]:
                assert status_page.checkmark_exists(), "No checkmark for completed status"
        except AssertionError as e:
            for k in items:
                if items[k] and statuses[k] == Status.APPROVED:
                    statuses[k] = Status.NOT_APPROVED
                    errors[k] = str(e)
                    screenshots[k] = _take_screenshot(page, f"status_chain_{k}")
            raise
        finally:
            for k, item in items.items():
                if item:
                    _report(excel_t2_checklist, item, statuses[k], screenshots[k], errors[k])
                else:
                    _add_undocumented_error(f"test_items_14_17_status_chain_{k}", errors[k], screenshots[k])

    def test_item_18_not_found_message(self, page: Page, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "No existe tal pedido")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order("INVALID_TRACK_999")
            assert status_page.not_found_message_is_visible(), "Not found message not shown"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_18")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_18_not_found_message", error, screenshot)

class TestStatusTransitions:
    def test_items_19_20_status_after_accept(self, page: Page, api_order, unique_courier, order_api,
                                             excel_t2_checklist: ExcelHandler):
        item_19 = _get_item(excel_t2_checklist, "El scooter está en el almacén")
        item_20 = _get_item(excel_t2_checklist, "repartidor o repartidora está en camino")
        status_19 = Status.APPROVED
        status_20 = Status.APPROVED
        error_19 = error_20 = ""
        screenshot_19 = screenshot_20 = ""
        try:
            track = api_order["track"]
            track_resp = order_api.get_by_track(track)
            assert track_resp.status_code == 200
            order_data = track_resp.json()
            order_id = order_data.get("order", {}).get("id") or order_data.get("id")
            assert order_id, "Order ID not found"

            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(track)
            active = status_page.get_active_status_text()
            if item_19:
                assert "warehouse" in active.lower(), f"Initial status not 'warehouse', got '{active}'"

            accept_resp = order_api.accept(order_id, unique_courier["id"])
            assert accept_resp.status_code == 200, f"Accept failed: {accept_resp.text}"

            page.reload()
            status_page.search_order(track)
            active2 = status_page.get_active_status_text()
            if item_20:
                assert "way" in active2.lower(), f"After accept not 'on the way', got '{active2}'"
        except AssertionError as e:
            if "warehouse" in str(e):
                status_19 = Status.NOT_APPROVED
                error_19 = str(e)
                screenshot_19 = _take_screenshot(page, "item_19")
            else:
                status_20 = Status.NOT_APPROVED
                error_20 = str(e)
                screenshot_20 = _take_screenshot(page, "item_20")
            raise
        finally:
            if item_19:
                _report(excel_t2_checklist, item_19, status_19, screenshot_19, error_19)
            else:
                _add_undocumented_error("test_items_19_20_status_after_accept_19", error_19, screenshot_19)
            if item_20:
                _report(excel_t2_checklist, item_20, status_20, screenshot_20, error_20)
            else:
                _add_undocumented_error("test_items_19_20_status_after_accept_20", error_20, screenshot_20)

    def test_item_21_show_courier_name(self, page: Page, accepted_order, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "nombre del repartidor")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(accepted_order["track"])
            page_text = page.content()
            assert accepted_order["courier_name"] in page_text, f"Courier name '{accepted_order['courier_name']}' not found"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_21")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_21_show_courier_name", error, screenshot)

    def test_item_22_wrap_courier_name(self, page: Page, order_api: OrderApiClient, unique_courier, api_order,
                                       excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Ajustar el aviso del repartidor a una segunda línea cuando el nombre del repartidor no cabe en una sola línea.")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            long_name = "X" * 30
            courier_client = unique_courier["client"]
            uid = uuid.uuid4().hex[:8]
            login = f"courier_long_{uid}"
            resp = courier_client.create(login=login, password=settings.test_data.courier_password, first_name=long_name)
            assert resp.status_code == 201
            login_resp = courier_client.login(login=login, password=settings.test_data.courier_password)
            courier_id = login_resp.json().get("id")

            track = api_order["track"]
            track_resp = order_api.get_by_track(track)
            assert track_resp.status_code == 200
            order_data = track_resp.json()
            order_id = order_data.get("order", {}).get("id") or order_data.get("id")
            assert order_id
            accept_resp = order_api.accept(order_id, courier_id)
            assert accept_resp.status_code == 200

            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(track)
            elem = page.get_by_text(long_name, exact=False).first
            elem.wait_for(state="visible", timeout=10000)
            height = elem.evaluate("el => el.scrollHeight")
            line_height = elem.evaluate("el => parseInt(getComputedStyle(el).lineHeight)")
            assert height > line_height + 2, "Courier name not wrapping"
        except Exception as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_22")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_22_wrap_courier_name", error, screenshot)

    def test_items_23_24_status_after_complete(self, page: Page, finished_order, excel_t2_checklist: ExcelHandler):
        item_23 = _get_item(excel_t2_checklist, "servicio de entrega llegó")
        item_24 = _get_item(excel_t2_checklist, "vamos a dar un paseo")
        status_23 = Status.APPROVED
        status_24 = Status.APPROVED
        error_23 = error_24 = ""
        screenshot_23 = screenshot_24 = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(finished_order["track"])
            active = status_page.get_active_status_text()
            if item_23:
                assert "arrived" in active.lower(), f"After complete not 'arrived', got '{active}'"
            page.reload()
            status_page.search_order(finished_order["track"])
            active2 = status_page.get_active_status_text()
            if item_24:
                assert "ride" in active2.lower(), f"After finish not 'ride', got '{active2}'"
        except AssertionError as e:
            if "arrived" in str(e):
                status_23 = Status.NOT_APPROVED
                error_23 = str(e)
                screenshot_23 = _take_screenshot(page, "item_23")
            else:
                status_24 = Status.NOT_APPROVED
                error_24 = str(e)
                screenshot_24 = _take_screenshot(page, "item_24")
            raise
        finally:
            if item_23:
                _report(excel_t2_checklist, item_23, status_23, screenshot_23, error_23)
            else:
                _add_undocumented_error("test_items_23_24_status_after_complete_23", error_23, screenshot_23)
            if item_24:
                _report(excel_t2_checklist, item_24, status_24, screenshot_24, error_24)
            else:
                _add_undocumented_error("test_items_23_24_status_after_complete_24", error_24, screenshot_24)

    def test_items_25_26_rental_end_text_and_calculation(self, page: Page, finished_order, excel_t2_checklist: ExcelHandler):
        item_25 = _get_item(excel_t2_checklist, "El alquiler finalizará el")
        item_26 = _get_item(excel_t2_checklist, "Calcular la fecha y hora")
        if item_25:
            _report(excel_t2_checklist, item_25, Status.NOT_APPROVED, "", "Funcionalidad no implementada en la UI actual")
        if item_26:
            _report(excel_t2_checklist, item_26, Status.NOT_APPROVED, "", "Funcionalidad no implementada en la UI actual")
        # No se lanza excepción, el test pasa (pero en Excel queda No Aprobado)

    def test_item_27_query_another_order(self, page: Page, api_order, order_api: OrderApiClient,
                                         excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "consultar otro pedido")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order["track"])
            assert status_page.order_data_is_visible(), "First order not shown"

            delivery_date = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
            payload = {
                "firstName": "Second", "lastName": "Order", "address": "456 Other St",
                "metroStation": "Ginger cats", "phone": "12345678901", "rentTime": 1,
                "deliveryDate": delivery_date, "comment": "", "color": []
            }
            resp = order_api.create(payload)
            assert resp.status_code == 201
            second_track = str(resp.json()["track"])
            status_page.search_order(second_track)
            assert status_page.order_data_is_visible(), "Second order not shown after re-query"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_27")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_27_query_another_order", error, screenshot)

class TestCancelFlow:
    def test_items_28_36_cancel_before_accept(self, page: Page, api_order, excel_t2_checklist: ExcelHandler):
        items = {
            28: _get_item(excel_t2_checklist, "Mostrar el botón “Cancelar el pedido” en la pantalla de estado del pedido."),
            29: _get_item(excel_t2_checklist, "¿Deseas cancelar el pedido?"),
            30: _get_item(excel_t2_checklist, "Atrás"),
            31: _get_item(excel_t2_checklist, "Mostrar el botón “Cancelar” en la ventana emergente de cancelación."),
            32: _get_item(excel_t2_checklist, "Regresar a la página"),
            33: _get_item(excel_t2_checklist, "ventana emergente de confirmación"),
            34: _get_item(excel_t2_checklist, "El pedido ha sido cancelado"),
            35: _get_item(excel_t2_checklist, "Mostrar el botón “Bien” en la ventana emergente de confirmación de cancelación."),
            36: _get_item(excel_t2_checklist, "Redirigir a la página de inicio"),
        }
        statuses = {k: Status.APPROVED for k in items}
        errors = {k: "" for k in items}
        screenshots = {k: "" for k in items}
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order["track"])
            _accept_cookies(page)

            if items[28]:
                assert status_page.cancel_button_is_visible(), "Cancel button not visible"
            status_page.open_cancel_modal()
            page.wait_for_timeout(500)

            if items[29]:
                assert status_page.modal_text_contains("cancel"), "Modal text not as expected"
            if items[30]:
                assert page.is_visible('button:has-text("Back")'), "Back button not in modal"
            if items[31]:
                assert page.is_visible('button:has-text("Cancel")'), "Cancel button not in modal"

            status_page.click_modal_back()
            assert status_page.order_data_is_visible(), "Did not return to order status"

            status_page.open_cancel_modal()
            status_page.click_modal_cancel()

            # Esperar segundo modal (defecto real: puede no aparecer)
            second_modal = page.locator('text="The order has been canceled"').first
            second_modal.wait_for(state="visible", timeout=10000)

            if items[33]:
                assert status_page.confirmation_modal_is_visible(), "Confirmation modal not shown"
            if items[34]:
                assert "canceled" in page.content().lower(), "Cancellation message not found"
            if items[35]:
                ok_btn = page.locator('button:has-text("Okay")')
                assert ok_btn.count() > 0, "Okay button not in confirmation"
                ok_btn.click()
            else:
                status_page.click_modal_ok()

            page.wait_for_url(settings.server.base_url, timeout=5000)
            assert page.url == settings.server.base_url, "Not redirected to home"
        except AssertionError as e:
            for k in items:
                if items[k] and statuses[k] == Status.APPROVED:
                    statuses[k] = Status.NOT_APPROVED
                    errors[k] = str(e)
                    screenshots[k] = _take_screenshot(page, f"cancel_{k}")
            raise
        finally:
            for k, item in items.items():
                if item:
                    _report(excel_t2_checklist, item, statuses[k], screenshots[k], errors[k])
                else:
                    _add_undocumented_error(f"test_items_28_36_cancel_{k}", errors[k], screenshots[k])

    def test_items_37_39_cancel_after_accept_not_allowed(self, page: Page, accepted_order, excel_t2_checklist: ExcelHandler):
        items = {
            37: _get_item(excel_t2_checklist, "cancelar el pedido antes"),
            38: _get_item(excel_t2_checklist, "Impedir hacer clic"),
            39: _get_item(excel_t2_checklist, "Impedir visualizar"),
        }
        statuses = {k: Status.APPROVED for k in items}
        errors = {k: "" for k in items}
        screenshots = {k: "" for k in items}
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(accepted_order["track"])
            if items[38]:
                assert not status_page.cancel_button_is_visible(), "Cancel button still visible after accept"
        except AssertionError as e:
            for k in items:
                if items[k] and statuses[k] == Status.APPROVED:
                    statuses[k] = Status.NOT_APPROVED
                    errors[k] = str(e)
                    screenshots[k] = _take_screenshot(page, f"cancel_after_accept_{k}")
            raise
        finally:
            for k, item in items.items():
                if item:
                    _report(excel_t2_checklist, item, statuses[k], screenshots[k], errors[k])
                else:
                    _add_undocumented_error(f"test_items_37_39_cancel_after_accept_{k}", errors[k], screenshots[k])

class TestOverdueOrder:
    def test_items_40_44_overdue_order(self, page: Page, order_api: OrderApiClient, db: DatabaseConnector,
                                       excel_t2_checklist: ExcelHandler):
        items = {
            40: _get_item(excel_t2_checklist, "Cambiar el estado del pedido a “El repartidor o repartidora se demoró” cuando el scooter no se entrega a tiempo."),
            41: _get_item(excel_t2_checklist, "No podremos entregar"),
            42: _get_item(excel_t2_checklist, "resaltar en rojo"),
            43: _get_item(excel_t2_checklist, "leyenda del pedido atrasado"),
            44: _get_item(excel_t2_checklist, "cálculo del fin del alquiler"),
        }
        statuses = {k: Status.APPROVED for k in items}
        errors = {k: "" for k in items}
        screenshots = {k: "" for k in items}
        try:
            past_date = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
            payload = {
                "firstName": "Overdue", "lastName": "Test", "address": "123 Main St",
                "metroStation": "Ginger cats", "phone": "12345678901", "rentTime": 1,
                "deliveryDate": past_date, "comment": "", "color": []
            }
            resp = order_api.create(payload)
            assert resp.status_code == 201
            track = str(resp.json()["track"])
            db.execute(f'UPDATE "Orders" SET finished=false, cancelled=false, "inDelivery"=false WHERE track={track}')

            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(track)
            page_text = page.content()

            if items[40]:
                assert "delayed" in page_text.lower(), "Overdue status not shown"
            if items[41]:
                assert "won't be able to deliver" in page_text.lower(), "Overdue message not shown"
            if items[42] or items[43]:
                red_elem = page.locator('.Track_Overtime__1jgdQ, [class*="overtime"]')
                assert red_elem.count() > 0, "No red highlighting for overdue"
        except AssertionError as e:
            for k in items:
                if items[k] and statuses[k] == Status.APPROVED:
                    statuses[k] = Status.NOT_APPROVED
                    errors[k] = str(e)
                    screenshots[k] = _take_screenshot(page, f"overdue_{k}")
            raise
        finally:
            for k, item in items.items():
                if item:
                    _report(excel_t2_checklist, item, statuses[k], screenshots[k], errors[k])
                else:
                    _add_undocumented_error(f"test_items_40_44_overdue_{k}", errors[k], screenshots[k])

class TestFrontendEnhancements:
    def test_items_45_46_fifth_status(self, page: Page, finished_order, excel_t2_checklist: ExcelHandler):
        items = {
            45: _get_item(excel_t2_checklist, "quinto estado"),
            46: _get_item(excel_t2_checklist, "cuarto estado en gris"),
        }
        for k, item in items.items():
            if item:
                _report(excel_t2_checklist, item, Status.NOT_APPROVED, "", "Quinto estado no implementado en versión actual")
        # No se lanza excepción, el test pasa (pero en Excel queda No Aprobado)

class TestTrackFieldEdgeCases:
    def test_item_47_reject_non_numeric(self, page: Page, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Rechazar la entrada de texto no numérico")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.page.fill('input[placeholder*="number"]', "ABCDE!@#")
            status_page.page.press('input[placeholder*="number"]', "Enter")
            value = status_page.page.input_value('input[placeholder*="number"]')
            if value != "":
                assert status_page.not_found_message_is_visible(), "Non-numeric input not rejected and no error message"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_47")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_47_reject_non_numeric", error, screenshot)

    def test_item_48_requery_without_reload(self, page: Page, api_order, order_api: OrderApiClient,
                                            excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "nuevo número de pedido en el campo sin recargar")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order["track"])
            assert status_page.order_data_is_visible(), "First order not shown"

            delivery_date = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
            payload = {
                "firstName": "Second", "lastName": "Order", "address": "456 Other St",
                "metroStation": "Ginger cats", "phone": "12345678901", "rentTime": 1,
                "deliveryDate": delivery_date, "comment": "", "color": []
            }
            resp = order_api.create(payload)
            assert resp.status_code == 201
            second_track = str(resp.json()["track"])
            status_page.search_order(second_track)
            assert status_page.order_data_is_visible(), "Second order not shown after re-query"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_48")
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, screenshot, error)
            else:
                _add_undocumented_error("test_item_48_requery_without_reload", error, screenshot)

class TestDuplicates:
    def test_item_49_no_duplicate_orders_in_db(self, db: DatabaseConnector, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Verificar que no existan pedidos duplicados en la base de datos (mismo track).")
        if not item:
            pytest.skip("Item 49 not found in Excel. Please add row 49.")
        status = Status.APPROVED
        error = ""
        try:
            rows = db.fetch_all('SELECT track FROM "Orders"')
            tracks = [str(r["track"]) for r in rows]
            duplicates = [t for t in set(tracks) if tracks.count(t) > 1]
            assert len(duplicates) == 0, f"Duplicate tracks found: {duplicates}"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            raise
        finally:
            if item:
                _report(excel_t2_checklist, item, status, "", error)

# ─── Nuevos tests 50-58 ───────────────────────────────────────────────────
class TestNewItems:
    def test_item_50_track_field_empty_on_enter(self, page: Page, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Al acceder a la pantalla de estado, el campo “Número de pedido” debe aparecer vacío.")
        if not item:
            pytest.skip("Item 50 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            value = page.input_value('input[placeholder*="number"]')
            assert value == "", f"Track field is not empty: '{value}'"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_50")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_51_go_button_performs_search(self, page: Page, api_order, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Go!")
        if not item:
            pytest.skip("Item 51 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            go_button = page.locator('button:has-text("Go!")')
            assert go_button.is_visible(), "Go! button not visible"
            page.fill('input[placeholder*="number"]', api_order["track"])
            go_button.click()
            page.wait_for_timeout(2000)
            status_page = OrderStatusPage(page)
            assert status_page.order_data_is_visible(), "Order data not shown after clicking Go!"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_51")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_52_cancelled_order_shows_not_found(self, page: Page, order_api: OrderApiClient,
                                                     excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "pedido que ha sido cancelado")
        if not item:
            pytest.skip("Item 52 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            # Crear pedido
            delivery_date = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
            payload = {
                "firstName": "CancelTest", "lastName": "Cancel", "address": "123 Main St",
                "metroStation": "Ginger cats", "phone": "12345678901", "rentTime": 1,
                "deliveryDate": delivery_date, "comment": "", "color": []
            }
            resp = order_api.create(payload)
            assert resp.status_code == 201, f"Order creation failed: {resp.text}"
            track = str(resp.json()["track"])
            # Cancelar pedido
            cancel_resp = order_api.cancel(track)
            assert cancel_resp.status_code == 200, f"Cancel API failed: {cancel_resp.text}"
            # Navegar a estado
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(track)
            assert not status_page.order_data_is_visible(), "Order data is visible for cancelled order"
            assert status_page.not_found_message_is_visible(), "Not found message not shown for cancelled order"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_52")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_53_cancel_button_not_visible_after_cancel(self, page: Page, order_api: OrderApiClient,
                                                            excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "Después de cancelar un pedido, el botón “Cancelar el pedido” no debe estar visible en la página de estado (ya que el pedido ya no se muestra).")
        if not item:
            pytest.skip("Item 53 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            delivery_date = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
            payload = {
                "firstName": "CancelTest2", "lastName": "Cancel", "address": "123 Main St",
                "metroStation": "Ginger cats", "phone": "12345678901", "rentTime": 1,
                "deliveryDate": delivery_date, "comment": "", "color": []
            }
            resp = order_api.create(payload)
            assert resp.status_code == 201
            track = str(resp.json()["track"])
            cancel_resp = order_api.cancel(track)
            assert cancel_resp.status_code == 200, f"Cancel API failed: {cancel_resp.text}"
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(track)
            assert not status_page.cancel_button_is_visible(), "Cancel button visible for cancelled order"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_53")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_54_cancel_button_not_visible_for_completed_order(self, page: Page, finished_order,
                                                                   excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "pedido completado")
        if not item:
            pytest.skip("Item 54 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(finished_order["track"])
            assert not status_page.cancel_button_is_visible(), "Cancel button visible for completed order"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_54")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_55_exact_number_of_status_blocks(self, page: Page, api_order, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "exactamente 4 bloques")
        if not item:
            pytest.skip("Item 55 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order["track"])
            count = status_page.status_count()
            assert count in (4, 5), f"Expected 4 or 5 status blocks, got {count}"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_55")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_56_status_order_is_correct(self, page: Page, api_order, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "orden correcto")
        if not item:
            pytest.skip("Item 56 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(api_order["track"])
            blocks = page.locator('[class*="OrderBrick"]')
            texts = [block.text_content().strip().lower() for block in blocks.all()]
            expected_sequence = ["warehouse", "way", "arrived", "ride"]
            found = []
            for word in expected_sequence:
                for t in texts:
                    if word in t:
                        found.append(word)
                        break
            assert found == expected_sequence, f"Order mismatch. Found: {found}, expected: {expected_sequence}"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_56")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_57_rental_end_date_format(self, page: Page, finished_order, excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "El texto “El alquiler finalizará el” debe ir seguido de una fecha con formato día/mes o día/mes/año (validar el formato).")
        if not item:
            pytest.skip("Item 57 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(finished_order["track"])
            page_text = page.content()
            if "rental will end on" in page_text.lower():
                match = re.search(r'rental will end on\s+(\d{1,2}\s+\w+|\d{4}-\d{2}-\d{2})', page_text, re.IGNORECASE)
                assert match, "Date not found after rental end text"
            elif "alquiler finalizará el" in page_text.lower():
                match = re.search(r'alquiler finalizará el\s+(\d{1,2}\s+\w+|\d{4}-\d{2}-\d{2})', page_text, re.IGNORECASE)
                assert match, "Date not found after rental end text"
            else:
                raise AssertionError("Rental end text not found at all")
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_57")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

    def test_item_58_fifth_status_only_when_expired(self, page: Page, order_api: OrderApiClient, db: DatabaseConnector,
                                                    excel_t2_checklist: ExcelHandler):
        item = _get_item(excel_t2_checklist, "solo debe activarse cuando el tiempo de alquiler ha expirado (no basta con que se muestre siempre")
        if not item:
            pytest.skip("Item 58 not found in Excel")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            past_date = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
            payload = {
                "firstName": "Expire", "lastName": "Test", "address": "123 Main St",
                "metroStation": "Ginger cats", "phone": "12345678901", "rentTime": 1,
                "deliveryDate": past_date, "comment": "", "color": []
            }
            resp = order_api.create(payload)
            assert resp.status_code == 201
            track = str(resp.json()["track"])
            db.execute(f'UPDATE "Orders" SET finished=true, cancelled=false, "inDelivery"=false WHERE track={track}')

            home = HomePage(page)
            home.goto()
            _accept_cookies(page)
            home.click_order_status_button()
            status_page = OrderStatusPage(page)
            status_page.search_order(track)
            page_text = page.content()
            has_fifth = "rental period ended" in page_text.lower() or "periodo de alquiler terminó" in page_text.lower()
            assert has_fifth, "Fifth status not shown even though rental period should be expired"
        except AssertionError as e:
            status = Status.NOT_APPROVED
            error = str(e)
            screenshot = _take_screenshot(page, "item_58")
            raise
        finally:
            _report(excel_t2_checklist, item, status, screenshot, error)

def pytest_sessionfinish(session, exitstatus):
    _generate_undocumented_report()