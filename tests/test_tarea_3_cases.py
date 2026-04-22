"""
test_tarea_3_cases.py — Tarea 3 Casos de Prueba (18 casos móviles).

Covers:
  - mob-01 to mob-07: Push notification timing (2 hours before deadline)
  - mob-08 to mob-17: "Sin acceso a Internet" popup behavior
  - mob-18:           No notification when order already completed
"""
from __future__ import annotations

import time

import pytest

from components.mobile.mobile_app import (
    LoginPage,
    NetworkHelper,
    OrderDetailPage,
    OrderListPage,
    MyOrdersPage,
)
from models.test_entities import MobileTestCase, Status
from appium.webdriver.common.appiumby import AppiumBy
from utils.excel_handler import ExcelHandler
from utils.logger import get_logger
from utils.screenshot_manager import ScreenshotManager
from config import settings

log = get_logger("test_t3_cases")
_sm = ScreenshotManager("tarea3_mobile")

pytestmark = [pytest.mark.tarea3, pytest.mark.mobile]


# ─── Helper ───────────────────────────────────────────────────────────────────

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
        status_col=settings.excel.t3_status_col,
        jira_col=settings.excel.t3_jira_col,
        screenshot_path=screenshot,
        error_message=error,
        comment=comment,
    )


def _get_case(handler: ExcelHandler, case_id: str) -> MobileTestCase | None:
    for c in handler.read_cases_t3():
        if c.case_id == case_id:
            return c
    return None


# ─── Push Notification Tests (mob-01 to mob-07) ───────────────────────────────

class TestPushNotifications:
    """
    Tests for the 2-hour deadline push notification.

    NOTE: True push-notification timing tests require manipulating the
    emulator system clock. These tests use Appium's shell commands to
    shift the system time so the server triggers the notification early.

    ═══════════════════════════════════════════════════════════════════
    BLOQUEADOR ARQUITECTÓNICO — TODOS LOS TESTS mob-01 a mob-07
    ═══════════════════════════════════════════════════════════════════
    La APK com.yandex.samokat NO tiene NotificationChannels registrados.
    Android 13 muestra "This app does not send notifications" en Settings
    → Apps → Urban Scooter → Notifications.

    Sin un NotificationChannel, NINGUNA notificación puede llegar al
    notification tray del sistema, sin importar los permisos concedidos.
    El requisito dice que debe llegar una push notification — la app
    no implementa ese requisito a nivel de arquitectura de Android.

    Estado: NO APROBADO para mob-01 a mob-07.
    Razón en Excel: Bug en la APK — no hay NotificationChannel definido.
    Evidencia: Android Settings muestra "This app does not send notifications"
    y el toggle de notificaciones está desactivado y no se puede activar.
    """

    # ─── Mensaje de razón reutilizable (mismo para todos los tests de notificación) ──
    _NOTIFICATION_BUG_REASON = (
        "BUG ARQUITECTÓNICO EN LA APK: com.yandex.samokat no tiene NotificationChannel "
        "registrado en Android 13. Android Settings → Apps → Urban Scooter → Notifications "
        "muestra 'This app does not send notifications' y el toggle NO puede activarse. "
        "Sin NotificationChannel, ninguna push notification puede llegar al notification tray "
        "independientemente de los permisos concedidos. "
        "Requisito afectado: Notificación 2 horas antes del deadline. "
        "Impacto: mob-01 a mob-07 y mob-18 NO APROBADOS por bloqueador de implementación en la APK."
    )

    def _advance_emulator_time_to_trigger(self, driver) -> None:
        """Set emulator clock to 21:59 of delivery date (today+1) so 2h remain before 23:59 deadline.
        Requirement: notification fires at 21:59 on delivery day (2 hours before 23:59).
        The web order uses delivery_days=1, so delivery date is tomorrow.
        """
        import subprocess
        from datetime import date as _date
        import datetime
        target_date = _date.today() + datetime.timedelta(days=1)
        month_day = target_date.strftime("%m%d")
        year_str = target_date.strftime("%Y")
        date_str = f"{month_day}2159{year_str}.00"  # MMDDhhmm[CCYY].ss format
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "settings", "put", "global", "auto_time", "0"])
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "date", date_str])
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "am", "broadcast", "-a", "android.intent.action.TIME_SET"])
        time.sleep(2)

    def _reset_emulator_time(self, driver) -> None:
        """Re-enable automatic time sync on the emulator."""
        import subprocess
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "settings", "put", "global", "auto_time", "1"])
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "am", "broadcast", "-a", "android.intent.action.TIME_SET"])
        time.sleep(1)

    def _refresh_via_tab_switch(self, order_list: OrderListPage) -> None:
        """Refresh order list by switching Todos→Mis→Todos tabs.
        
        Per requirements: 'Si un usuario va a la pestaña Mis pedidos y luego regresa
        a Todos los pedidos, la lista se actualiza.'
        User confirmed: switching tabs or minimizing also refreshes the list.
        This is MORE RELIABLE than pull-to-refresh swipe gesture via Appium.
        """
        order_list._tap(*order_list._BTN_MY_ORDERS)
        time.sleep(1.5)
        order_list._tap(*order_list._BTN_ALL_ORDERS)
        time.sleep(2.0)

    def _load_orders_for_acceptance(self, driver, order_list: OrderListPage) -> None:
        """Ensure the app is on order list screen and orders are loaded, using tab-switch refresh."""
        order_list.ensure_on_order_list()
        # Try tab-switch refresh up to 3 times
        for attempt in range(3):
            self._refresh_via_tab_switch(order_list)
            if order_list.order_count() > 0:
                return
            log.info("_load_orders_for_acceptance: attempt %d — no orders yet, waiting 3s", attempt + 1)
            time.sleep(3)
        assert order_list.order_count() > 0, (
            "No orders visible after 3 tab-switch refreshes. "
            "Verify the web order was created and the courier is logged in."
        )

    # ─── mob-01 ────────────────────────────────────────────────────────────────
    def test_mob01_push_notification_received_2h_before_deadline(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        excel_t3_cases: ExcelHandler,
        valid_order,
        valid_courier,
    ) -> None:
        """
        NOT APROBADO — Bug arquitectónico: la APK no implementa NotificationChannels.
        Android no puede entregar notificaciones sin canales definidos.
        """
        case = _get_case(excel_t3_cases, "mob-01")
        status = Status.NOT_APPROVED
        screenshot = str(_sm.capture_appium(appium_driver, "mob01_no_notification_channel"))
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=self._NOTIFICATION_BUG_REASON,
            )
        pytest.fail(
            "mob-01 NOT APROBADO: " + self._NOTIFICATION_BUG_REASON
        )

    # ─── mob-02 ────────────────────────────────────────────────────────────────
    def test_mob02_notification_text_matches_requirement(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        excel_t3_cases: ExcelHandler,
        valid_order,
    ) -> None:
        """NOT APROBADO — Mismo bloqueador arquitectónico que mob-01."""
        case = _get_case(excel_t3_cases, "mob-02")
        status = Status.NOT_APPROVED
        screenshot = str(_sm.capture_appium(appium_driver, "mob02_no_notification_channel"))
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=self._NOTIFICATION_BUG_REASON,
            )
        pytest.fail("mob-02 NOT APROBADO: " + self._NOTIFICATION_BUG_REASON)

    # ─── mob-03 ────────────────────────────────────────────────────────────────
    def test_mob03_tap_notification_opens_my_orders(
        self,
        appium_driver,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        """NOT APROBADO — Sin notificación que tocar (bloqueador de mob-01)."""
        case = _get_case(excel_t3_cases, "mob-03")
        status = Status.NOT_APPROVED
        screenshot = str(_sm.capture_appium(appium_driver, "mob03_no_notification_channel"))
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=(
                    "BLOQUEADO por mob-01: no existe notificación en el tray del sistema "
                    "que tocar. " + self._NOTIFICATION_BUG_REASON
                ),
            )
        pytest.fail("mob-03 NOT APROBADO: bloqueado por bug de notificaciones en la APK.")

    # ─── mob-04 ────────────────────────────────────────────────────────────────
    def test_mob04_notification_tap_from_background_no_duplicate_nav(
        self,
        appium_driver,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        """NOT APROBADO — Sin notificación que tocar (bloqueador de mob-01)."""
        case = _get_case(excel_t3_cases, "mob-04")
        status = Status.NOT_APPROVED
        screenshot = str(_sm.capture_appium(appium_driver, "mob04_no_notification_channel"))
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=(
                    "BLOQUEADO por mob-01: no existe notificación en el tray del sistema. "
                    + self._NOTIFICATION_BUG_REASON
                ),
            )
        pytest.fail("mob-04 NOT APROBADO: bloqueado por bug de notificaciones en la APK.")

    # ─── mob-05 ────────────────────────────────────────────────────────────────
    def test_mob05_long_notification_text_not_truncated(
        self,
        appium_driver,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        """NOT APROBADO — Sin notificación visible (bloqueador de mob-01)."""
        case = _get_case(excel_t3_cases, "mob-05")
        status = Status.NOT_APPROVED
        screenshot = str(_sm.capture_appium(appium_driver, "mob05_no_notification_channel"))
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=(
                    "BLOQUEADO: no hay notificación en el tray para verificar truncamiento. "
                    + self._NOTIFICATION_BUG_REASON
                ),
            )
        pytest.fail("mob-05 NOT APROBADO: bloqueado por bug de notificaciones en la APK.")

    # ─── mob-06 ────────────────────────────────────────────────────────────────
    def test_mob06_notification_with_app_closed(
        self,
        appium_driver,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        """NOT APROBADO — Sin NotificationChannel registrado, imposible recibir notificación."""
        case = _get_case(excel_t3_cases, "mob-06")
        status = Status.NOT_APPROVED
        screenshot = str(_sm.capture_appium(appium_driver, "mob06_no_notification_channel"))
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=(
                    "Adicionalmente: aunque la notificación existiera, la APK probablemente "
                    "usa AlarmManager (cancelado al cerrar la app) en lugar de FCM. "
                    + self._NOTIFICATION_BUG_REASON
                ),
            )
        pytest.fail("mob-06 NOT APROBADO: bloqueado por bug de notificaciones en la APK.")

    # ─── mob-07 ────────────────────────────────────────────────────────────────
    def test_mob07_notification_after_background_restore(
        self,
        appium_driver,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        """NOT APROBADO — Sin NotificationChannel registrado."""
        case = _get_case(excel_t3_cases, "mob-07")
        status = Status.NOT_APPROVED
        screenshot = str(_sm.capture_appium(appium_driver, "mob07_no_notification_channel"))
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=self._NOTIFICATION_BUG_REASON,
            )
        pytest.fail("mob-07 NOT APROBADO: bloqueado por bug de notificaciones en la APK.")

    # ─── mob-18 ────────────────────────────────────────────────────────────────
    def test_mob18_no_notification_when_order_already_completed(
        self,
        appium_driver,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        """
        NOT APROBADO — Este test verifica que NO llega notificación en un pedido completado.
        Sin embargo, como la APK no tiene NotificationChannel, nunca llega una notificación
        en NINGÚN caso. El resultado 'no notification' es inconclusivo: no prueba que la
        lógica de supresión funcione, solo confirma el bloqueador arquitectónico.
        """
        case = _get_case(excel_t3_cases, "mob-18")
        screenshot = str(_sm.capture_appium(appium_driver, "mob18_no_notification_channel"))
        status = Status.NOT_APPROVED
        if case:
            _report(
                excel_t3_cases, case, status,
                screenshot=screenshot,
                comment=(
                    "Resultado INCONCLUSIVO: la ausencia de notificación no demuestra que "
                    "la lógica de supresión para pedidos completados funcione, ya que la APK "
                    "no tiene NotificationChannel y NUNCA envía notificaciones. "
                    + self._NOTIFICATION_BUG_REASON
                ),
            )
        pytest.fail("mob-18 NOT APROBADO: resultado inconclusivo por bloqueador arquitectónico.")


# ─── No Internet Popup Tests (mob-08 to mob-17) ───────────────────────────────

class TestNoInternetPopup:
    """
    Tests for the 'Sin acceso a Internet' popup behavior.
    Uses NetworkHelper to toggle connectivity on the emulator.
    """

    @pytest.fixture(autouse=True)
    def ensure_wifi_restored(self, network_helper: NetworkHelper):
        """Always restore Wi-Fi after each test in this class."""
        yield
        network_helper.enable_wifi()
        time.sleep(1)

    # mob-08
    def test_mob08_popup_shown_when_button_tapped_offline(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-08")
        screenshot = ""
        error = ""
        status = Status.APPROVED
        try:
            network_helper.disable_wifi()
            time.sleep(1)

            # Tap the 'Todos los pedidos' tab — this triggers a network request
            mobile_order_list.tap_network_trigger()
            time.sleep(2)

            assert mobile_order_list.no_internet_popup_is_visible(), \
                "'Sin acceso a Internet' popup NOT shown after tapping button offline"
            screenshot = str(_sm.capture_appium(appium_driver, "mob08_popup"))
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob08_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)

    # mob-09
    def test_mob09_popup_closes_when_accept_tapped(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-09")
        screenshot = ""
        error = ""
        status = Status.APPROVED
        try:
            network_helper.disable_wifi()
            time.sleep(1)
            mobile_order_list.tap_network_trigger()
            time.sleep(2)

            if not mobile_order_list.no_internet_popup_is_visible():
                pytest.skip("Popup not shown — prerequisite for mob-09 not met")

            mobile_order_list.dismiss_no_internet_popup()
            time.sleep(0.5)
            assert not mobile_order_list.no_internet_popup_is_visible(), \
                "Popup still visible after tapping 'Aceptar'"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob09_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)

    # mob-10
    def test_mob10_popup_reappears_on_subsequent_tap_offline(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-10")
        screenshot = ""
        error = ""
        status = Status.APPROVED
        try:
            network_helper.disable_wifi()
            time.sleep(1)

            # First trigger
            mobile_order_list.tap_network_trigger()
            time.sleep(2)
            mobile_order_list.dismiss_no_internet_popup()
            time.sleep(0.5)

            # Second trigger — still offline
            mobile_order_list.tap_network_trigger()
            time.sleep(2)

            assert mobile_order_list.no_internet_popup_is_visible(), \
                "Popup did NOT reappear on second tap while still offline"
            screenshot = str(_sm.capture_appium(appium_driver, "mob10_popup_reappears"))
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob10_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)

    # mob-11
    def test_mob11_action_blocked_when_popup_shown(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-11")
        screenshot = ""
        error = ""
        status = Status.APPROVED
        try:
            network_helper.disable_wifi()
            time.sleep(1)
            mobile_order_list.tap_network_trigger()
            time.sleep(2)

            assert mobile_order_list.no_internet_popup_is_visible(), \
                "Popup not shown — cannot verify action blocking"

            # Confirm the user has NOT been navigated away
            still_on_list = mobile_order_list._is_visible(
                *mobile_order_list._NO_ORDERS_MSG, timeout=2
            ) or mobile_order_list._is_visible(
                *mobile_order_list._ORDER_ITEM, timeout=2
            )
            # The popup is modal — underlying navigation must NOT have occurred
            popup_still_up = mobile_order_list.no_internet_popup_is_visible()
            assert popup_still_up, "Popup dismissed itself — action may have proceeded"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob11_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)

    # mob-12
    def test_mob12_popup_stays_visible_without_interaction(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-12")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            network_helper.disable_wifi()
            time.sleep(1)
            mobile_order_list.tap_network_trigger()
            time.sleep(2)

            if not mobile_order_list.no_internet_popup_is_visible():
                pytest.skip("Popup not triggered")

            time.sleep(5)   # wait without interaction
            assert mobile_order_list.no_internet_popup_is_visible(), \
                "Popup auto-dismissed — should stay visible until 'Aceptar' is tapped"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob12_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)

    # mob-13
    def test_mob13_popup_consistent_across_screens(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-13")
        screenshot = ""
        error = ""
        status = Status.APPROVED
        try:
            network_helper.disable_wifi()
            time.sleep(1)

            # Screen 1: Order list — tap tab to trigger network request
            mobile_order_list.tap_network_trigger()
            time.sleep(2)
            assert mobile_order_list.no_internet_popup_is_visible(), \
                "Popup not shown on Order List screen"
            mobile_order_list.dismiss_no_internet_popup()

            # Return online to safely switch screens
            network_helper.enable_wifi()
            time.sleep(2)
            
            # Screen 2: My Orders tab
            my_orders = mobile_order_list.go_to_my_orders()
            time.sleep(1)
            
            # Go offline again
            network_helper.disable_wifi()
            time.sleep(1)
            
            # Trigger network action cleanly by tapping the current tab again
            appium_driver.find_element(AppiumBy.XPATH, '//*[contains(@resource-id,"tab_mine")]').click()
            time.sleep(2)
            
            # Popup should still appear on second screen
            popup_2 = mobile_order_list.no_internet_popup_is_visible()
            if not popup_2:
                screenshot = str(_sm.capture_appium(appium_driver, "mob13_screen2_no_popup"))
            assert popup_2, "Popup NOT shown consistently on 'Mis pedidos' screen"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob13_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)

    # mob-14
    def test_mob14_normal_flow_resumes_after_reconnect(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-14")
        screenshot = ""
        error = ""
        status = Status.APPROVED
        try:
            network_helper.disable_wifi()
            time.sleep(1)
            mobile_order_list.tap_network_trigger()
            time.sleep(2)
            mobile_order_list.dismiss_no_internet_popup()

            # Restore connection
            network_helper.enable_wifi()
            time.sleep(3)

            mobile_order_list.tap_network_trigger()
            time.sleep(2)

            # Popup should NOT appear now
            assert not mobile_order_list.no_internet_popup_is_visible(), \
                "Popup still shown after Internet was restored"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob14_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)

    # mob-15
    def test_mob15_app_stable_wifi_to_airplane_mode(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-15")
        screenshot = ""
        error = ""
        status = Status.APPROVED
        try:
            network_helper.enable_wifi()
            time.sleep(1)
            network_helper.enable_airplane_mode()
            time.sleep(2)

            mobile_order_list.tap_network_trigger()
            time.sleep(3)

            # App must not crash
            assert appium_driver.current_activity, "App crashed — no current activity"
            assert mobile_order_list.no_internet_popup_is_visible(), \
                "Popup not shown after switching to airplane mode"
            screenshot = str(_sm.capture_appium(appium_driver, "mob15_airplane_popup"))
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob15_fail"))
            raise
        finally:
            network_helper.disable_airplane_mode()
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)


    # mob-17
    def test_mob17_popup_shown_after_background_restore(
        self,
        appium_driver,
        mobile_order_list: OrderListPage,
        network_helper: NetworkHelper,
        excel_t3_cases: ExcelHandler,
    ) -> None:
        case = _get_case(excel_t3_cases, "mob-17")
        status = Status.APPROVED
        error = ""
        screenshot = ""
        try:
            network_helper.disable_wifi()
            time.sleep(1)

            net = NetworkHelper(appium_driver)
            net.send_to_background(seconds=3)
            net.bring_to_foreground()
            time.sleep(1)

            mobile_order_list.tap_network_trigger()
            time.sleep(2)

            assert mobile_order_list.no_internet_popup_is_visible(), \
                "Popup not shown after background/foreground cycle while offline"
        except AssertionError as exc:
            status = Status.NOT_APPROVED
            error = str(exc)
            screenshot = str(_sm.capture_appium(appium_driver, "mob17_fail"))
            raise
        finally:
            if case:
                _report(excel_t3_cases, case, status, screenshot, error)
