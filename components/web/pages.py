"""
Page Object Model para la aplicación web Urban Scooter.
Selectores basados en el DOM real (inglés).
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from playwright.sync_api import Page, expect
from config.settings import browser as br_cfg, server as srv_cfg
from utils.decorators import log_step, screenshot_on_fail
from utils.logger import get_logger
from utils.screenshot_manager import ScreenshotManager

log = get_logger("web_pages")
_sm = ScreenshotManager("web")

class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.page.set_default_timeout(br_cfg.default_timeout)

    def screenshot(self, name: str) -> None:
        _sm.capture_playwright(self.page, name)

    def navigate_to(self, url: str) -> None:
        self.page.goto(url, wait_until="networkidle")

    def navigate_home(self) -> None:
        self.navigate_to(srv_cfg.base_url)

    def goto(self) -> None:
        self.navigate_home()

class HomePage(BasePage):
    _BTN_ORDER = 'button:has-text("Order")'
    _BTN_STATUS = 'button:has-text("Order status")'

    @log_step("Click 'Order' button")
    def click_order_button(self) -> "OrderFormPage":
        self.page.click(self._BTN_ORDER)
        self.page.wait_for_load_state("networkidle")
        return OrderFormPage(self.page)

    @log_step("Click 'Order status' button")
    def click_order_status_button(self) -> "OrderStatusPage":
        self.page.click(self._BTN_STATUS)
        self.page.wait_for_load_state("networkidle")
        return OrderStatusPage(self.page)

    def order_status_button_is_visible(self) -> bool:
        return self.page.is_visible(self._BTN_STATUS)

class OrderFormPage(BasePage):
    # Primer formulario
    _FIRST_NAME = 'input[placeholder="* First name"]'
    _LAST_NAME = 'input[placeholder="* Last name"]'
    _ADDRESS = 'input[placeholder="* Address: where to bring the scooter"]'
    _METRO = 'input[placeholder="* Subway station"]'
    _PHONE = 'input[placeholder="* Phone: the courier will call you"]'
    _COMMENT = 'input[placeholder="Comment"]'
    _NEXT = 'button:has-text("Next")'
    _SUBMIT = 'button:has-text("Order")'
    _ORDER_NUMBER = '[class*="track"], [class*="order-number"]'
    _METRO_DROPDOWN = '.select-search__options li'

    # Segundo formulario
    _DELIVERY_DATE = 'input[placeholder="* When to deliver the scooter"]'
    _RENTAL_PERIOD_CONTROL = '.Dropdown-control'
    _RENTAL_PERIOD_OPTION = '.Dropdown-option'

    def fill_first_name(self, value: str) -> None:
        self.page.fill(self._FIRST_NAME, value)

    def fill_last_name(self, value: str) -> None:
        self.page.fill(self._LAST_NAME, value)

    def fill_address(self, value: str) -> None:
        self.page.fill(self._ADDRESS, value)

    def fill_metro_station(self, value: str) -> None:
        # Instead of fill(), which doesn't reliably trigger the dropdown, we click it.
        # Since this is an automated flow for mobile prep, we just pick the first option
        # perfectly mimicking T2 test 40.
        self.page.locator(self._METRO).click()
        self.page.wait_for_timeout(900)
        self.page.locator('.select-search__option').first.click()
        self.page.wait_for_timeout(400)

    def fill_phone(self, value: str) -> None:
        self.page.fill(self._PHONE, value)

    def fill_comment(self, value: str) -> None:
        self.page.fill(self._COMMENT, value)

    def select_delivery_date(self, days_from_today: int = 1) -> str:
        from datetime import date, timedelta
        target = date.today() + timedelta(days=days_from_today)
        day_str = str(target.day)
        self.page.click(self._DELIVERY_DATE)
        self.page.wait_for_selector('.react-datepicker', timeout=5000)
        for _ in range(3):
            month_text = self.page.text_content('.react-datepicker__current-month')
            if target.strftime("%B %Y").lower() in (month_text or "").lower():
                break
            self.page.click('.react-datepicker__navigation--next')
        self.page.click(
            f'.react-datepicker__day:not(.react-datepicker__day--outside-month):has-text("{day_str}")'
        )
        self.page.click('body')
        self.page.wait_for_timeout(300)
        return target.strftime("%Y-%m-%d")

    def select_rental_period(self, days: int = 1) -> None:
        day_text = {1: "a day", 2: "two days", 3: "three days", 4: "four days",
                    5: "five days", 6: "six days", 7: "seven days"}.get(days, "a day")
        control = self.page.locator(self._RENTAL_PERIOD_CONTROL).first
        if control.is_visible():
            control.click()
            self.page.wait_for_selector(f'{self._RENTAL_PERIOD_OPTION}:has-text("{day_text}")', timeout=5000)
            self.page.click(f'{self._RENTAL_PERIOD_OPTION}:has-text("{day_text}")')
            self.page.wait_for_timeout(200)

    def click_next(self) -> None:
        self.page.click(self._NEXT)
        self.page.wait_for_load_state("networkidle")

    @log_step("Create order via UI and return track")
    def create_order_via_ui(self, first_name="Test", last_name="UI", address="123 Main St",
                            metro_station="1st Street", phone="12345678901",
                            delivery_days=1, rent_days=1, color=None, comment="") -> str:
        self.fill_first_name(first_name)
        self.fill_last_name(last_name)
        self.fill_address(address)
        self.fill_metro_station(metro_station)
        self.fill_phone(phone)
        self.click_next()
        self.select_delivery_date(delivery_days)
        self.select_rental_period(rent_days)
        if color:
            checkbox_id = "black" if color.upper() == "BLACK" else "grey"
            self.page.check(f"#{checkbox_id}")
        if comment:
            self.fill_comment(comment)
        self.page.locator(self._SUBMIT).last.click()
        self.page.wait_for_timeout(1500)
        
        # Intermediate confirmation modal
        try:
            self.page.locator('button:has-text("Yes")').click(timeout=3000)
        except Exception:
            pass
            
        modal = self.page.locator('[class*="Modal"], .Order_Modal__YZ-d3, [role="dialog"]').first
        modal.wait_for(state="visible", timeout=15000)
        
        import time
        import re
        track_match = None
        modal_text = ""
        
        for _ in range(7):
            for el in self.page.locator('[class*="Modal"]').all():
                try:
                    txt = el.inner_text()
                    if "Order number" in txt or "order has been made" in txt.lower():
                        modal_text = txt
                        track_match = re.search(r'Order number[:\s]+(\d+)', modal_text)
                        if not track_match:
                            track_match = re.search(r'\b\d{6,}\b', modal_text)
                        if track_match:
                            break
                except Exception:
                    pass
            if track_match:
                break
            time.sleep(1)
            
        if not track_match:
            raise Exception(f"No track found in modal: {modal_text}")
        
        track = track_match.group(1) if len(track_match.groups()) > 0 else track_match.group()
        try:
            modal.locator('button:has-text("View")').click()
        except Exception:
            pass
            
        log.info(f"Order created via UI. Track: {track}")
        return track

class OrderStatusPage(BasePage):
    _FLD_TRACK = 'input[placeholder="Enter the number of the order"]'
    _BTN_GO = 'button:has-text("Go!")'
    _ORDER_DATA = '[class*="OrderInfo"], [class*="track-order"]'
    _STATUS_BLOCK = '[class*="OrderBrick"]'
    _ACTIVE_STATUS = '[class*="Highlight"]'
    _BTN_CANCEL = 'button:has-text("Cancel the order")'
    _MODAL = '[class*="Modal"], .Order_Modal__YZ-d3'
    _MODAL_BTN_BACK = 'button:has-text("Back")'
    _MODAL_BTN_CANCEL = 'button:has-text("Cancel")'
    _MODAL_BTN_OK = 'button:has-text("OK")'
    _ERR_NOT_FOUND = 'h1:has-text("There\'s no such order")'
    _CHECKMARK = '[class*="OrderCircle"]:has-text("✓")'

    @log_step("Search order by track number")
    def search_order(self, track: str) -> None:
        self.page.fill(self._FLD_TRACK, str(track))
        try:
            self.page.click(self._BTN_GO, timeout=5000)
        except Exception:
            self.page.evaluate('''
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Go!'));
                if (btn) btn.click();
            ''')
        self.page.wait_for_timeout(1500)

    def order_data_is_visible(self) -> bool:
        return self.page.is_visible(self._ORDER_DATA, timeout=5000)

    def field_is_visible(self, field_label: str) -> bool:
        return self.page.is_visible(f"text={field_label}", timeout=3000)

    def not_found_message_is_visible(self) -> bool:
        return self.page.is_visible(self._ERR_NOT_FOUND, timeout=5000)

    def get_active_status_text(self) -> str:
        try:
            elem = self.page.locator(self._ACTIVE_STATUS).first
            if elem.count() == 0:
                return ""
            return elem.inner_text().strip()
        except Exception:
            return ""

    def status_count(self) -> int:
        return self.page.locator(self._STATUS_BLOCK).count()

    def get_status_blocks_texts(self) -> list[str]:
        blocks = self.page.locator(self._STATUS_BLOCK).all()
        return [block.inner_text().strip() for block in blocks]

    def cancel_button_is_visible(self) -> bool:
        return self.page.is_visible(self._BTN_CANCEL, timeout=3000)

    def cancel_button_is_disabled(self) -> bool:
        return self.page.is_disabled(self._BTN_CANCEL)

    def open_cancel_modal(self) -> None:
        try:
            self.page.click(self._BTN_CANCEL, timeout=5000)
        except Exception:
            self.page.evaluate('''
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Cancel the order'));
                if (btn) btn.click();
            ''')
        self.page.wait_for_selector(self._MODAL, timeout=5000)

    def modal_is_visible(self) -> bool:
        return self.page.is_visible(self._MODAL, timeout=3000)

    def modal_text_contains(self, text: str) -> bool:
        modal_text = self.page.text_content(self._MODAL) or ""
        return text.lower() in modal_text.lower()

    def click_modal_back(self) -> None:
        self.page.click(self._MODAL_BTN_BACK)
        self.page.wait_for_timeout(500)

    def click_modal_cancel(self) -> None:
        try:
            self.page.click(self._MODAL_BTN_CANCEL, timeout=5000)
        except Exception:
            self.page.evaluate('''
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Cancel'));
                if (btn) btn.click();
            ''')
        self.page.wait_for_timeout(500)

    def click_modal_ok(self) -> None:
        self.page.click(self._MODAL_BTN_OK)
        self.page.wait_for_timeout(500)

    def confirmation_modal_is_visible(self) -> bool:
        return self.modal_is_visible() and self.modal_text_contains("canceled")

    def checkmark_exists(self) -> bool:
        return self.page.locator(self._CHECKMARK).count() > 0