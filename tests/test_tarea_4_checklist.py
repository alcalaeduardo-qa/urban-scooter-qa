# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from components.api.api_client import CourierApiClient, OrderApiClient
from models.test_entities import Status, ApiChecklistItem, CourierCredentials
from utils.db_connector import DatabaseConnector
from utils.decorators import screenshot_on_fail
from utils.excel_handler import ExcelHandler
from utils.logger import get_logger
from utils.screenshot_manager import ScreenshotManager
from config import settings

log = get_logger("test_t4_checklist")
_sm = ScreenshotManager("tarea4_api")

pytestmark = [pytest.mark.tarea4, pytest.mark.api]


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_item(handler: ExcelHandler, description_fragment: str) -> ApiChecklistItem | None:
    for item in handler.read_checklist_t4():
        if description_fragment.lower() in item.description.lower():
            return item
    return None


def _get_item_by_row(handler: ExcelHandler, row: int) -> ApiChecklistItem | None:
    for item in handler.read_checklist_t4():
        if item.row_index == row:
            return item
    return None


def _report(
    handler: ExcelHandler,
    item: ApiChecklistItem,
    status: Status,
    screenshot: str = "",
    error: str = "",
) -> None:
    # Auto-capturar imagen de error para API cuando falla y no hay screenshot
    if not screenshot and status == Status.NOT_APPROVED and error:
        try:
            screenshot = _sm.capture_api_failure(f"row_{item.row_index}", error)
        except Exception:
            pass
    handler.write_status(
        row_index=item.row_index,
        status=status,
        status_col=settings.excel.t4_status_col,
        jira_col=settings.excel.t4_jira_col,
        screenshot_path=screenshot,
        error_message=error,
    )


def _assert_status(resp, expected: int, context: str) -> None:
    assert resp.status_code == expected, (
        f"{context}: expected {expected}, got {resp.status_code}. Body: {resp.text[:200]}"
    )


# ─── Courier creation (rows 1–8) ──────────────────────────────────────────────

class TestCourierCreation:

    @screenshot_on_fail("tarea4_api")
    def test_row1_create_courier_valid_returns_201(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "creación de un mensajero con login, password y firstName válidos")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.create(login="t4_valid_01", password="Test@1234", first_name="Valid")
            _assert_status(resp, 201, "Create courier valid")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row2_courier_password_stored_as_hash(
        self,
        excel_t4_checklist: ExcelHandler,
        db: DatabaseConnector,
    ) -> None:
        item = _get_item(excel_t4_checklist, "inserción en BD")
        status = Status.APPROVED
        error = ""
        try:
            row = db.get_courier_by_login("t4_valid_01")
            assert row is not None, "Courier not in DB"
            assert row["login"] == "t4_valid_01", "Login mismatch in DB"
            assert db.is_password_hashed("t4_valid_01", "Test@1234"), "Password NOT hashed in DB!"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row4_create_courier_without_login_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "sin login")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.create(password="Test@1234", first_name="NoLogin")
            _assert_status(resp, 400, "Create courier without login")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row5_create_courier_without_password_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "sin password")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.create(login="t4_no_pwd", first_name="NoPwd")
            _assert_status(resp, 400, "Create courier without password")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row6_create_courier_without_firstname_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "sin firstName")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.create(login="t4_no_fn", password="Test@1234")
            _assert_status(resp, 400, "Create courier without firstName")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row7_create_courier_without_login_and_password_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "sin login ni password")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.create(first_name="OnlyName")
            _assert_status(resp, 400, "Create courier without login and password")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row8_create_courier_duplicate_login_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "login duplicado")
        status = Status.APPROVED
        error = ""
        try:
            courier_api.create(login="t4_dup_test", password="Test@1234", first_name="Dup")
            resp = courier_api.create(login="t4_dup_test", password="Other@1234", first_name="Dup2")
            _assert_status(resp, 400, "Create courier duplicate login")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)


# ─── Courier login (rows 3, 9–13) ─────────────────────────────────────────────

class TestCourierLogin:

    @screenshot_on_fail("tarea4_api")
    def test_row3_login_validates_password_hash(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "autorización con el mismo login y password")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.login(login="t4_valid_01", password="Test@1234")
            _assert_status(resp, 200, "Login with valid credentials")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row9_login_returns_courier_id(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "login exitoso devuelve")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.login(login="t4_valid_01", password="Test@1234")
            _assert_status(resp, 200, "Login returns ID")
            body = resp.json()
            courier_id = body.get("id") or body.get("courierId")
            assert courier_id, f"No id in login response: {body}"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row10_login_without_login_field_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "login sin login")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.login(password="Test@1234")
            _assert_status(resp, 400, "Login without login field")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row11_login_without_password_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        import requests as _req
        item = _get_item(excel_t4_checklist, "login sin password")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.login(login="t4_valid_01")
            _assert_status(resp, 400, "Login without password")
        except _req.exceptions.ReadTimeout:
            # SERVER BUG: when password field is absent the server hangs the
            # connection indefinitely instead of returning 400 immediately.
            # A ReadTimeout IS the detectable evidence of this bug.
            status = Status.NOT_APPROVED
            error = ("BUG del servidor: POST /api/v1/courier/login sin campo 'password' "
                     "no devuelve 400 — el servidor cuelga la conexión hasta timeout (30 s). "
                     "Código esperado: 400. Comportamiento real: ReadTimeout.")
            pytest.fail(error)
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row12_login_without_both_fields_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        import requests as _req
        item = _get_item(excel_t4_checklist, "login sin login ni password")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.login()
            _assert_status(resp, 400, "Login without any fields")
        except _req.exceptions.ReadTimeout:
            # SERVER BUG: empty login body causes the server to hang the
            # connection instead of returning 400 immediately.
            status = Status.NOT_APPROVED
            error = ("BUG del servidor: POST /api/v1/courier/login con body vacío "
                     "no devuelve 400 — el servidor cuelga la conexión hasta timeout (30 s). "
                     "Código esperado: 400. Comportamiento real: ReadTimeout.")
            pytest.fail(error)
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row13_login_nonexistent_credentials_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "login + password no existente")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.login(login="ghost_user_xyz", password="NoExist@999")
            _assert_status(resp, 400, "Login with nonexistent credentials")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row15_login_existing_user_wrong_password_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        """New case: login registrado en el sistema + contraseña incorrecta → 400.

        Distinto a test_row13 (credenciales completamente inexistentes):
        aquí el login SÍ existe en la BD (t4_valid_01 fue creado en test_row1),
        pero la contraseña enviada es incorrecta.
        """
        item = _get_item(excel_t4_checklist, "contraseña incorrecta")
        status = Status.APPROVED
        error = ""
        try:
            # Ensure the courier exists (idempotent — if already created, server returns 409)
            courier_api.create(login="t4_wrong_pwd", password="Correct@1234", first_name="WrongPwd")
            # Now login with the correct login but an INCORRECT password
            resp = courier_api.login(login="t4_wrong_pwd", password="WRONG_PASSWORD_999")
            _assert_status(resp, 400, "Login with existing user but wrong password")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)


# ─── Order creation (rows 14–15, 23) ──────────────────────────────────────────

class TestOrderCreation:

    @screenshot_on_fail("tarea4_api")
    def test_row14_create_order_valid_returns_201(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "creación de un pedido con todos los campos obligatorios")
        status = Status.APPROVED
        error = ""
        try:
            result = order_api.create_valid_order()
            assert result.track, "Track not returned"
            TestOrderCreation._last_track = result.track
            TestOrderCreation._last_order_id = result.order_id
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row15_create_order_response_has_track(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "respuesta de creación de pedido devuelve el campo track")
        status = Status.APPROVED
        error = ""
        try:
            from datetime import date, timedelta
            payload = {
                "firstName": "Test", "lastName": "Track",
                "address": "Main St 123", "metroStation": "Ginger cats",
                "phone": "1234567890", "rentTime": 1,
                "deliveryDate": (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "comment": "", "color": [],
            }
            resp = order_api.create(payload)
            _assert_status(resp, 201, "Create order for track check")
            body = resp.json()
            assert "track" in body, f"'track' field missing from response: {body}"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row23_get_orders_list_returns_200(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "obtención de la lista de pedidos")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.list_all()
            _assert_status(resp, 200, "GET /api/v1/orders")
            body = resp.json()
            orders = body if isinstance(body, list) else body.get("orders", [])
            assert isinstance(orders, list), "Response does not contain a list of orders"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)


# ─── Track lookup (rows 16–19) ────────────────────────────────────────────────

class TestOrderTrack:

    @screenshot_on_fail("tarea4_api")
    def test_row16_get_order_by_valid_track_returns_200(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_order,
    ) -> None:
        item = _get_item(excel_t4_checklist, "número de seguimiento válido")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.get_by_track(valid_order.track)
            _assert_status(resp, 200, "Get order by valid track")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row17_track_response_includes_required_fields(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_order,
    ) -> None:
        item = _get_item(excel_t4_checklist, "incluye los datos del pedido encontrado")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.get_by_track(valid_order.track)
            _assert_status(resp, 200, "Get order fields")
            body = resp.json()
            for field in ("id", "firstName", "lastName", "address", "track", "status"):
                assert field in body or field in str(body), \
                    f"Field '{field}' missing from track response: {list(body.keys())}"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row18_get_order_without_track_param_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "sin enviar el parámetro t")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.get_by_track(None)
            _assert_status(resp, 400, "Get order without track param")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row19_get_order_with_nonexistent_track_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "número de seguimiento inexistente")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.get_by_track("99999999")
            _assert_status(resp, 400, "Get order with fake track")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)


# ─── Order cancel (rows 20–22, 24–25) ─────────────────────────────────────────

class TestOrderCancel:

    @screenshot_on_fail("tarea4_api")
    def test_row20_cancel_unprocessed_order_returns_200(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "cancelación de un pedido existente enviando un track válido de un pedido no procesado")
        status = Status.APPROVED
        error = ""
        try:
            fresh_order = order_api.create_valid_order()
            resp = order_api.cancel(fresh_order.track)
            _assert_status(resp, 200, "Cancel unprocessed order")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row21_cancel_without_track_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "cancelación sin enviar el campo track")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.cancel(None)
            _assert_status(resp, 400, "Cancel without track")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row22_cancel_nonexistent_track_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "cancelación con un track inexistente")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.cancel("FAKEFAKETRACK999")
            _assert_status(resp, 400, "Cancel nonexistent track")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row28_cancel_already_cancelled_order_returns_400(
        self,
        order_api: OrderApiClient,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        """New case: intentar cancelar un pedido que ya está en estado cancelado → 400.

        El docx indica que 'en caso de una cancelación sin éxito, se debe devolver un error'.
        Setup: el servidor sólo permite cancelar pedidos 'en proceso' (aceptados por un mensajero),
        no pedidos sin procesar. Por eso primero se acepta el pedido (igual que row24_25) y LUEGO
        se cancela — confirmando que queda cancelado — y se intenta cancelar de nuevo.
        """
        item = _get_item(excel_t4_checklist, "ya fue cancelado previamente")
        status = Status.APPROVED
        error = ""
        try:
            # Set up: create isolated courier + order, accept the order
            # (the server only allows cancelling orders currently 'in processing')
            courier_api.create(login="t4_row28_cancel", password="Row28Cancel@1", first_name="Row28")
            login_resp = courier_api.login(login="t4_row28_cancel", password="Row28Cancel@1")
            courier_id = int(login_resp.json().get("id") or login_resp.json().get("courierId") or 0)
            assert courier_id, "Could not login t4_row28_cancel courier"

            fresh_order = order_api.create_valid_order()

            # Find the order_id needed for accept
            all_resp = order_api.list_all()
            order_id = None
            orders_list = all_resp.json()
            for o in (orders_list if isinstance(orders_list, list) else orders_list.get("orders", [])):
                if str(o.get("track", "")) == str(fresh_order.track):
                    order_id = o.get("id")
                    break
            if not order_id and fresh_order.order_id:
                order_id = fresh_order.order_id
            assert order_id, "Could not resolve order_id for row28 setup"

            accept_resp = order_api.accept(order_id, courier_id)
            _assert_status(accept_resp, 200, "Accept order — setup for row28")

            # First cancel: order is now 'in processing', cancel must succeed
            first_cancel = order_api.cancel(fresh_order.track)
            _assert_status(first_cancel, 200, "First cancel — must succeed to set up the scenario")

            # Second cancel: order is now cancelled → must return 400
            resp = order_api.cancel(fresh_order.track)
            _assert_status(resp, 400, "Cancel already-cancelled order")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row24_25_cancel_processing_order_returns_400(
        self,
        order_api: OrderApiClient,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item_24 = _get_item(excel_t4_checklist, "aceptación de un pedido existente con un courierId válido para preparar")
        item_25 = _get_item(excel_t4_checklist, "cancelación de un pedido que ya se está procesando")
        status_24 = Status.APPROVED
        status_25 = Status.APPROVED
        error_24 = ""
        error_25 = ""
        try:
            # Create an ISOLATED courier for this test, separate from the
            # module-scoped 'valid_courier' fixture (login='edu').
            # This prevents contamination of the shared fixtures by this test's setup.
            courier_api.create(login="t4_cancel_prep", password="CancelPrep@1", first_name="CancelPrep")
            prep_login = courier_api.login(login="t4_cancel_prep", password="CancelPrep@1")
            courier_id = int(prep_login.json().get("id") or prep_login.json().get("courierId") or 0)
            assert courier_id, "Could not login t4_cancel_prep courier"
            order = order_api.create_valid_order()

            all_orders_resp = order_api.list_all()
            orders_data = all_orders_resp.json()
            order_id = None
            for o in (orders_data if isinstance(orders_data, list) else orders_data.get("orders", [])):
                if str(o.get("track", "")) == order.track:
                    order_id = o.get("id")
                    break

            if not order_id and order.order_id:
                order_id = order.order_id

            if order_id:
                accept_resp = order_api.accept(order_id, courier_id)
                _assert_status(accept_resp, 200, "Accept order for cancel test")
                status_24 = Status.APPROVED
            else:
                status_24 = Status.NOT_APPROVED
                error_24 = "Could not determine order_id from list"

            resp = order_api.cancel(order.track)
            _assert_status(resp, 400, "Cancel processing order")

        except AssertionError as exc:
            if "Accept" in str(exc):
                status_24 = Status.NOT_APPROVED
                error_24 = str(exc)
            else:
                status_25 = Status.NOT_APPROVED
                error_25 = str(exc)
            raise
        finally:
            if item_24:
                _report(excel_t4_checklist, item_24, status_24, "", error_24)
            if item_25:
                _report(excel_t4_checklist, item_25, status_25, "", error_25)


# ─── Courier delete + cascade (rows 26–32) ────────────────────────────────────

class TestCourierDelete:

    @pytest.fixture()
    def temp_courier(self, courier_api: CourierApiClient) -> CourierCredentials:
        creds = courier_api.create_valid_courier()
        courier_api.login_and_get_id(creds)
        return creds

    @screenshot_on_fail("tarea4_api")
    def test_row26_delete_existing_courier_returns_200(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
        temp_courier: CourierCredentials,
    ) -> None:
        item = _get_item(excel_t4_checklist, "eliminación de un mensajero existente usando un id válido")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.delete(temp_courier.courier_id)
            _assert_status(resp, 200, "Delete existing courier")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row27_delete_without_id_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "eliminación del mensajero sin enviar id")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.delete(None)
            _assert_status(resp, 400, "Delete courier without id")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row28_delete_nonexistent_courier_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "eliminación con un id de mensajero inexistente")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.delete(999999999)
            _assert_status(resp, 400, "Delete nonexistent courier")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_rows29_31_32_delete_courier_with_linked_orders_cascade(
        self,
        courier_api: CourierApiClient,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        items = {
            29: _get_item(excel_t4_checklist, "pedido adicional para vincularlo manualmente"),
            30: _get_item(excel_t4_checklist, "vinculación de un pedido al mensajero"),
            31: _get_item(excel_t4_checklist, "eliminación del mensajero que tiene pedidos vinculados"),
            32: _get_item(excel_t4_checklist, "pedido vinculado ya no puede recuperarse por track"),
        }
        statuses: dict[int, Status] = {k: Status.APPROVED for k in items}
        errors: dict[int, str] = {k: "" for k in items}

        try:
            # Create an ISOLATED courier for the cascade test so we don't delete
            # the shared 'edu' courier that other tests depend on.
            courier_api.create(login="t4_cascade_test", password="Cascade@1234", first_name="CascadeTest")
            casc_login = courier_api.login(login="t4_cascade_test", password="Cascade@1234")
            courier_id = int(casc_login.json().get("id") or casc_login.json().get("courierId") or 0)
            assert courier_id, "Could not login t4_cascade_test courier"
            order = order_api.create_valid_order()

            all_resp = order_api.list_all()
            order_id = None
            orders_list = all_resp.json()
            for o in (orders_list if isinstance(orders_list, list) else orders_list.get("orders", [])):
                if str(o.get("track", "")) == order.track:
                    order_id = o.get("id")
                    break
            if not order_id and order.order_id:
                order_id = order.order_id

            assert order_id, "Could not find order_id for cascade test"

            accept_resp = order_api.accept(order_id, courier_id)
            _assert_status(accept_resp, 200, "Accept order for cascade test")

            del_resp = courier_api.delete(courier_id)
            _assert_status(del_resp, 200, "Delete courier with linked order")

            track_resp = order_api.get_by_track(order.track)
            _assert_status(track_resp, 400, "Get deleted-courier's order by track")

        except AssertionError as exc:
            msg = str(exc)
            for row_id in [29, 30, 31, 32]:
                if statuses[row_id] == Status.APPROVED:
                    statuses[row_id] = Status.NOT_APPROVED
                    errors[row_id] = msg
                    break
            raise
        finally:
            for row_id, item in items.items():
                if item:
                    _report(excel_t4_checklist, item, statuses[row_id], "", errors[row_id])


# ─── ordersCount (rows 33–36) ─────────────────────────────────────────────────

class TestCourierOrdersCount:

    @screenshot_on_fail("tarea4_api")
    def test_row33_orders_count_existing_courier_returns_200(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_courier: CourierCredentials,
    ) -> None:
        item = _get_item(excel_t4_checklist, "número de pedidos de un mensajero existente")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.get_orders_count(valid_courier.courier_id)
            _assert_status(resp, 200, "ordersCount existing courier")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row34_orders_count_response_has_required_fields(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_courier: CourierCredentials,
    ) -> None:
        item = _get_item(excel_t4_checklist, "respuesta contiene id y ordersCount")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.get_orders_count(valid_courier.courier_id)
            _assert_status(resp, 200, "ordersCount fields")
            body = resp.json()
            assert "id" in body or "courierId" in body, f"No 'id' in response: {body}"
            assert "ordersCount" in body, f"No 'ordersCount' in response: {body}"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row35_orders_count_without_id_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "número de pedidos sin id")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.get_orders_count(None)
            _assert_status(resp, 400, "ordersCount without id")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row36_orders_count_nonexistent_courier_returns_400(
        self,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "número de pedidos con un id inexistente")
        status = Status.APPROVED
        error = ""
        try:
            resp = courier_api.get_orders_count(999999999)
            _assert_status(resp, 400, "ordersCount nonexistent id")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)


# ─── Accept order (rows 37–41) ────────────────────────────────────────────────

class TestOrderAccept:

    @screenshot_on_fail("tarea4_api")
    def test_row37_accept_without_order_id_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_courier: CourierCredentials,
    ) -> None:
        item = _get_item(excel_t4_checklist, "aceptación del pedido sin id del pedido")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.accept(None, valid_courier.courier_id)
            _assert_status(resp, 400, "Accept without order id")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row38_accept_without_courier_id_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_order,
    ) -> None:
        item = _get_item(excel_t4_checklist, "sin courierId")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.accept(valid_order.order_id or 1, None)
            _assert_status(resp, 400, "Accept without courierId")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row39_accept_nonexistent_order_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_courier: CourierCredentials,
    ) -> None:
        item = _get_item(excel_t4_checklist, "id de pedido inexistente")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.accept(999999999, valid_courier.courier_id)
            _assert_status(resp, 400, "Accept nonexistent order")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row40_accept_with_nonexistent_courier_id_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
        valid_order,
    ) -> None:
        item = _get_item(excel_t4_checklist, "courierId inexistente")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.accept(valid_order.order_id or 1, 999999999)
            _assert_status(resp, 400, "Accept with nonexistent courierId")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row41_accept_already_accepted_order_returns_400(
        self,
        order_api: OrderApiClient,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "pedido ya procesado")
        status = Status.APPROVED
        error = ""
        try:
            creds = courier_api.create_valid_courier()
            courier_id = courier_api.login_and_get_id(creds)
            order = order_api.create_valid_order()

            all_resp = order_api.list_all()
            orders = all_resp.json()
            order_id = None
            for o in (orders if isinstance(orders, list) else orders.get("orders", [])):
                if str(o.get("track", "")) == order.track:
                    order_id = o.get("id")
                    break
            if not order_id and order.order_id:
                order_id = order.order_id

            assert order_id, "order_id not found"
            order_api.accept(order_id, courier_id)

            resp = order_api.accept(order_id, courier_id)
            _assert_status(resp, 400, "Accept already-accepted order")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)


# ─── Finish order (rows 42–45) ────────────────────────────────────────────────

class TestOrderFinish:

    @screenshot_on_fail("tarea4_api")
    def test_row42_finish_accepted_order_returns_200(
        self,
        order_api: OrderApiClient,
        courier_api: CourierApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "finalización exitosa de un pedido en proceso")
        status = Status.APPROVED
        error = ""
        try:
            creds = courier_api.create_valid_courier()
            courier_id = courier_api.login_and_get_id(creds)
            order = order_api.create_valid_order()

            all_resp = order_api.list_all()
            orders = all_resp.json()
            order_id = None
            for o in (orders if isinstance(orders, list) else orders.get("orders", [])):
                if str(o.get("track", "")) == order.track:
                    order_id = o.get("id")
                    break
            if not order_id and order.order_id:
                order_id = order.order_id
            assert order_id

            order_api.accept(order_id, courier_id)
            resp = order_api.finish(order_id)
            _assert_status(resp, 200, "Finish accepted order")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row43_finish_without_id_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "finalización sin enviar el parámetro id")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.finish(None)
            _assert_status(resp, 400, "Finish without id")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row44_finish_nonexistent_order_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "id de pedido que no existe")
        status = Status.APPROVED
        error = ""
        try:
            resp = order_api.finish(999999999)
            _assert_status(resp, 400, "Finish nonexistent order")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)

    @screenshot_on_fail("tarea4_api")
    def test_row45_finish_non_processing_order_returns_400(
        self,
        order_api: OrderApiClient,
        excel_t4_checklist: ExcelHandler,
    ) -> None:
        item = _get_item(excel_t4_checklist, "pedido que no está en estado de procesamiento")
        status = Status.APPROVED
        error = ""
        try:
            fresh = order_api.create_valid_order()
            order_api.cancel(fresh.track)
            resp = order_api.finish(fresh.order_id or 1)
            _assert_status(resp, 400, "Finish cancelled/non-processing order")
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            raise
        finally:
            if item:
                _report(excel_t4_checklist, item, status, "", error)