from __future__ import annotations
import time
from typing import Any

from appium.webdriver.webdriver import WebDriver
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import mobile as mob_cfg
from utils.decorators import log_step
from utils.logger import get_logger
from utils.screenshot_manager import ScreenshotManager

log = get_logger("mobile_app")
_sm = ScreenshotManager("mobile")
_WAIT = 10


class MobileBasePage:
    def __init__(self, driver: WebDriver) -> None:
        self.driver = driver
        self._wait = WebDriverWait(driver, _WAIT)

    def screenshot(self, name: str) -> None:
        _sm.capture_appium(self.driver, name)

    def _find(self, by: str, value: str) -> Any:
        return self._wait.until(EC.presence_of_element_located((by, value)))

    def _find_all(self, by: str, value: str) -> list:
        return self.driver.find_elements(by, value)

    def _is_visible(self, by: str, value: str, timeout: int = 3) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
            return True
        except (NoSuchElementException, TimeoutException):
            return False

    def _tap(self, by: str, value: str) -> None:
        self._find(by, value).click()

    def _long_press(self, by: str, value: str, duration_ms: int = 2000) -> None:
        element = self._find(by, value)
        self.driver.execute_script(
            "mobile: longClickGesture",
            {"elementId": element.id, "duration": duration_ms},
        )

    def _type(self, by: str, value: str, text: str) -> None:
        el = self._find(by, value)
        el.clear()
        el.send_keys(text)


class LoginPage(MobileBasePage):
    _FLD_LOGIN    = (AppiumBy.ID, "com.yandex.samokat:id/auth_login_input")
    _FLD_PASSWORD = (AppiumBy.ID, "com.yandex.samokat:id/auth_password_input")
    _BTN_SIGNIN   = (AppiumBy.ID, "com.yandex.samokat:id/auth_login_button")
    # The '?' / debug backend-URL button in the bottom-right of the login screen
    _BTN_QUESTION = (AppiumBy.ID, "com.yandex.samokat:id/show_back")

    @log_step("Configure backend URL in mobile app")
    def configure_backend_url(self, url: str) -> None:
        try:
            self.driver.execute_script("mobile: shell", {"command": "cmd statusbar collapse"})
        except Exception:
            pass
        time.sleep(1)
        
        try:
            self._long_press(*self._BTN_QUESTION, duration_ms=2500)
        except TimeoutException:
            # Dump page source to help identify the correct locator
            try:
                src = self.driver.page_source
                log.warning("[mobile] _BTN_QUESTION not found. Page source snippet:\n%s", src[:3000])
            except Exception:
                pass
            raise
        time.sleep(1.5)
        paste_field = self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")
        if paste_field:
            paste_field[-1].clear()
            paste_field[-1].send_keys(url.strip())
            log.info(f"\n>>>> [mobile] EXACT URL BEING TYPED INTO API FIELD: '{url.strip()}' <<<<\n")
            
        ok_btn = self.driver.find_elements(AppiumBy.XPATH, '//*[@text="OK" or @text="Ok" or @text="Aceptar" or @text="Confirmar" or @text="Guardar"]')
        if not ok_btn:
             ok_btn = self.driver.find_elements(AppiumBy.ID, "android:id/button1") # Generic Android Yes/Ok button
             
        if ok_btn:
            log.info(f"[mobile] Found OK button, clicking...")
            ok_btn[0].click()
        else:
            log.warning("[mobile] OK button NOT FOUND! Sending 'done' action instead.")
            try:
                self.driver.execute_script('mobile: performEditorAction', {'action': 'done'})
            except Exception:
                pass
        time.sleep(1)

    @log_step("Login to mobile app")
    def login(self, login: str, password: str) -> "OrderListPage":
        self._type(*self._FLD_LOGIN, login)
        self._type(*self._FLD_PASSWORD, password)
        self._tap(*self._BTN_SIGNIN)
        time.sleep(2)
        return OrderListPage(self.driver)


class OrderListPage(MobileBasePage):
    # ── Localizadores verificados con uiautomator dump (2026-04-14) ──────────────
    # Cada tarjeta de pedido es un ViewGroup con resource-id 'order_container'
    # La lista completa está en un RecyclerView con resource-id 'item_rv'
    _ORDER_ITEM        = (AppiumBy.ID, "com.yandex.samokat:id/order_container")
    _ORDER_LIST_RV     = (AppiumBy.ID, "com.yandex.samokat:id/item_rv")
    _BTN_ALL_ORDERS    = (AppiumBy.ID, "com.yandex.samokat:id/tab_all")
    _BTN_MY_ORDERS     = (AppiumBy.ID, "com.yandex.samokat:id/tab_mine")
    _NO_ORDERS_MSG     = (AppiumBy.XPATH, '//*[@text="No hay pedidos" or @text="No orders"]')
    
    # ── Popup "Sin acceso a Internet" ─────────────────────────────────────────────
    # resource-id EXACTO: com.yandex.samokat:id/dialog_button_ok  text="OK"
    # IMPORTANTE: NO usar @text="Aceptar" — ese texto es del botón de las tarjetas
    # de pedido (id/accept). El popup usa un botón con texto "OK" e id propio.
    _POPUP_NO_INTERNET = (AppiumBy.ID, "com.yandex.samokat:id/dialog_title")
    _POPUP_OK          = (AppiumBy.ID, "com.yandex.samokat:id/dialog_button_ok")
    
    # ── Diálogo de confirmación "¿Deseas aceptar el pedido?" ─────────────────────
    _CONFIRM_DIALOG    = (AppiumBy.ID, "com.yandex.samokat:id/dialog_title")
    _CONFIRM_YES       = (AppiumBy.ID, "com.yandex.samokat:id/dialog_button_yes")
    _CONFIRM_NO        = (AppiumBy.ID, "com.yandex.samokat:id/dialog_button_no")
    
    # ── Botón "Aceptar" dentro de las tarjetas de pedido ─────────────────────────
    # SOLO se usa para aceptar un pedido, NUNCA para dismiss de popups
    _ORDER_ACCEPT_BTN  = (AppiumBy.ID, "com.yandex.samokat:id/accept")

    def refresh(self) -> None:
        """Refresh the order list by switching Todos→Mis→Todos tabs.

        Confirmed behavior (user + requirements doc):
        - Switching from 'Mis pedidos' back to 'Todos los pedidos' triggers a reload.
        - Minimizing and restoring the app also refreshes the list.
        - This is MORE RELIABLE than pull-to-refresh swipe via Appium because:
            1. Swipe can accidentally open the Android quick-settings panel if too high.
            2. Swipe speed and distance must be exact; tab-switch always works.
        
        Requisito: 'Si un usuario o usuaria va a la pestaña Mis pedidos y luego regresa
        a Todos los pedidos, la lista de pedidos se actualiza.'
        """
        self._tap(*self._BTN_MY_ORDERS)
        time.sleep(1.5)
        self._tap(*self._BTN_ALL_ORDERS)
        time.sleep(2.0)  # Wait for the server response and list to re-render

    def ensure_on_order_list(self) -> None:
        """Recover app to the order-list screen before running popup tests.
        Closes any overlay (notification shade, dialog) and brings app to foreground.
        
        IMPORTANT: only uses specific resource-IDs for dismissing dialogs to avoid
        accidentally clicking order card buttons (like id/accept on order cards).
        """
        # Collapse notification shade explicitly
        try:
            self.driver.execute_script("mobile: shell", {"command": "cmd statusbar collapse"})
        except Exception:
            pass
        time.sleep(0.5)

        # Close any dialog or overlay with BACK key
        self.driver.execute_script("mobile: pressKey", {"keycode": 4})  # BACK
        time.sleep(0.5)
        self.driver.execute_script("mobile: pressKey", {"keycode": 4})  # BACK again
        time.sleep(0.5)

        # Ensure app is in foreground
        self.driver.execute_script(
            "mobile: activateApp", {"appId": mob_cfg.app_package}
        )
        time.sleep(2)
        
        # Dismiss "Sin acceso a Internet" popup using its SPECIFIC button id/dialog_button_ok
        # (text='OK'). We do NOT search for generic @text='Aceptar' because that matches
        # the order card accept buttons (id/accept) and would trigger an order acceptance.
        try:
            ok_btns = self.driver.find_elements(*self._POPUP_OK)  # id/dialog_button_ok text='OK'
            if ok_btns:
                ok_btns[0].click()
                log.info("[ensure_on_order_list] Dismissed no-internet popup via id/dialog_button_ok")
                time.sleep(1)
        except Exception:
            pass
        
        # Dismiss "¿Deseas aceptar el pedido?" confirmation dialog if open (press No)
        try:
            no_btns = self.driver.find_elements(*self._CONFIRM_NO)  # id/dialog_button_no text='No'
            if no_btns:
                no_btns[0].click()
                log.info("[ensure_on_order_list] Dismissed accept-confirmation dialog via id/dialog_button_no")
                time.sleep(1)
        except Exception:
            pass

        # Handle the custom red crash screen ('¡Ups! Algo salió mal :(') by clicking RECARGAR
        try:
            reload_btns = self.driver.find_elements(AppiumBy.XPATH, '//*[@text="RECARGAR" or @text="RELOAD"]')
            if reload_btns:
                reload_btns[0].click()
                time.sleep(3)
        except Exception:
            pass

        # Wait for the order list tab to be visible (with fallback)
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(self._BTN_ALL_ORDERS)
            )
        except TimeoutException:
            log.warning("Order list tab not visible — attempting one more BACK press")
            self.driver.execute_script("mobile: pressKey", {"keycode": 4})
            time.sleep(1.5)
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(self._BTN_ALL_ORDERS)
            )

    def tap_network_trigger(self) -> None:
        """Ensure we're on the order list, then tap 'Todos los pedidos' tab
        to trigger a network request (provokes the no-internet popup when offline).
        """
        self.ensure_on_order_list()
        self._tap(*self._BTN_ALL_ORDERS)
        time.sleep(1.5)

    def order_count(self) -> int:
        return len(self._find_all(*self._ORDER_ITEM))

    def open_order(self, index: int = 0) -> "OrderDetailPage":
        items = self._find_all(*self._ORDER_ITEM)
        assert items, "No orders visible in list"
        items[index].click()
        time.sleep(1)
        return OrderDetailPage(self.driver)

    def go_to_my_orders(self) -> "MyOrdersPage":
        self._tap(*self._BTN_MY_ORDERS)
        time.sleep(1)
        return MyOrdersPage(self.driver)

    def no_internet_popup_is_visible(self) -> bool:
        return self._is_visible(*self._POPUP_NO_INTERNET)

    def dismiss_no_internet_popup(self) -> None:
        self._tap(*self._POPUP_OK)
        time.sleep(0.5)


class MyOrdersPage(MobileBasePage):
    # Orders in 'Mis pedidos' use the same order_container ViewGroup as in 'Todos los pedidos'
    _MY_ORDER_ITEM = (AppiumBy.ID, "com.yandex.samokat:id/order_container")

    def accepted_order_count(self) -> int:
        return len(self._find_all(*self._MY_ORDER_ITEM))

    def open_order(self, index: int = 0) -> "OrderDetailPage":
        items = self._find_all(*self._MY_ORDER_ITEM)
        assert items, "No accepted orders visible in 'Mis pedidos'"
        items[index].click()
        time.sleep(1)
        return OrderDetailPage(self.driver)


class OrderDetailPage(MobileBasePage):
    # Verified resource-IDs from uiautomator dump (2026-04-14)
    # id/accept      → Button text='Aceptar'  (on order card, opens confirm dialog)
    # id/dialog_button_yes → Button text='Sí' (confirm acceptance)
    # id/dialog_button_no  → Button text='No' (cancel acceptance)
    # id/dialog_title      → TextView with dialog title text
    _BTN_ACCEPT     = (AppiumBy.ID, "com.yandex.samokat:id/accept")
    _BTN_COMPLETE   = (AppiumBy.XPATH, '//*[@text="Completar" or @text="Complete"]')
    _CONFIRM_YES    = (AppiumBy.ID, "com.yandex.samokat:id/dialog_button_yes")
    _CONFIRM_NO     = (AppiumBy.ID, "com.yandex.samokat:id/dialog_button_no")
    _CONFIRM_DIALOG = (AppiumBy.ID, "com.yandex.samokat:id/dialog_title")

    @log_step("Accept order in mobile app")
    def accept_order(self) -> None:
        self._tap(*self._BTN_ACCEPT)
        if self._is_visible(*self._CONFIRM_DIALOG, timeout=3):
            self._tap(*self._CONFIRM_YES)
        time.sleep(1.5)

    @log_step("Complete order in mobile app")
    def complete_order(self) -> None:
        self._tap(*self._BTN_COMPLETE)
        if self._is_visible(*self._CONFIRM_DIALOG, timeout=3):
            self._tap(*self._CONFIRM_YES)
        time.sleep(1.5)


class NetworkHelper:
    def __init__(self, driver: WebDriver) -> None:
        self.driver = driver

    def disable_wifi(self) -> None:
        import subprocess
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "svc", "wifi", "disable"])
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "svc", "data", "disable"])
        time.sleep(1)

    def enable_wifi(self) -> None:
        import subprocess
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "svc", "wifi", "enable"])
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "svc", "data", "enable"])
        time.sleep(2)

    def enable_airplane_mode(self) -> None:
        import subprocess
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "settings", "put", "global", "airplane_mode_on", "1"])
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true"])
        self.disable_wifi()
        time.sleep(1)

    def disable_airplane_mode(self) -> None:
        import subprocess
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "settings", "put", "global", "airplane_mode_on", "0"])
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"])
        self.enable_wifi()
        time.sleep(2)

    def rotate_portrait(self) -> None:
        self.driver.orientation = "PORTRAIT"

    def rotate_landscape(self) -> None:
        self.driver.orientation = "LANDSCAPE"

    def send_to_background(self, seconds: int = 2) -> None:
        self.driver.execute_script("mobile: pressKey", {"keycode": 3})
        time.sleep(seconds)

    def bring_to_foreground(self) -> None:
        package = mob_cfg.app_package
        self.driver.execute_script(
            "mobile: shell",
            {"command": f"monkey -p {package} -c android.intent.category.LAUNCHER 1"},
        )
        time.sleep(1.5)

    def close_from_app_switcher(self) -> None:
        """Open app switcher and swipe the app card up to close it."""
        self.driver.execute_script("mobile: pressKey", {"keycode": 187})
        time.sleep(0.8)
        size = self.driver.get_window_size()
        w, h = size["width"], size["height"]
        # Swipe upward from center of screen to dismiss the app card
        self.driver.execute_script(
            "mobile: swipeGesture",
            {"left": 0, "top": int(h * 0.3), "width": w, "height": int(h * 0.5),
             "direction": "up", "percent": 0.8, "speed": 800},
        )
        time.sleep(0.5)
