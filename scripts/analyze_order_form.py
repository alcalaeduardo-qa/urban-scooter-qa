#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze Order Form DOM - Senior QA SDET Professional Version v2.
- Creates a new page for each test to isolate state.
- Handles application JS errors gracefully.
- Extended waits between tests.
- Continues execution even if a test fails.
"""

import json
import sys
import re
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List
from playwright.sync_api import sync_playwright, Page, Browser, Error as PlaywrightError

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import server as srv_cfg
from config.settings import browser as br_cfg

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
RESULTS_DIR = Path(__file__).parent.parent / "screenshots" / "tarea_2_formulario"
ANALYSIS_DIR = RESULTS_DIR / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
JSON_REPORT = ANALYSIS_DIR / "dom_analysis_detailed.json"

# Timeouts (ms)
TIMEOUT_NAVIGATION = 45000
TIMEOUT_ELEMENT = 15000
TIMEOUT_ACTION = 10000
WAIT_BETWEEN_TESTS = 3  # seconds

# Valid test data
VALID_FIRST_NAME = "Juan"
VALID_LAST_NAME = "Perez"
VALID_ADDRESS = "Calle Falsa 123"
VALID_PHONE = "12345678901"

# Error messages
ERROR_MSGS = {
    "first_name": "Enter a valid name",
    "last_name": "Enter a valid last name",
    "address": "Enter a valid address",
    "phone": "Enter a valid phone number",
    "period": "Select a rental period",
    "comment": "Comment too long"
}

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def take_screenshot(page: Page, name: str) -> Optional[Path]:
    try:
        path = ANALYSIS_DIR / f"{name}.png"
        page.screenshot(path=str(path))
        log(f"Screenshot: {path.name}")
        return path
    except Exception as e:
        log(f"Failed to screenshot {name}: {e}")
        return None

def safe_get_attribute(page: Page, selector: str, attr: str) -> str:
    try:
        elem = page.locator(selector).first
        if elem.count() and elem.is_visible(timeout=2000):
            return elem.get_attribute(attr) or ""
    except:
        pass
    return ""

def is_error_visible(page: Page, text: str) -> bool:
    try:
        return page.locator(f"text={text}").first.is_visible(timeout=2000)
    except:
        return False

def get_console_errors(page: Page) -> List[str]:
    """Capture JavaScript errors from the page console."""
    errors = []
    def handle_console(msg):
        if msg.type == "error":
            errors.append(f"[JS Error] {msg.text}")
    page.on("console", handle_console)
    return errors

# -----------------------------------------------------------------------------
# Page factory
# -----------------------------------------------------------------------------
def create_fresh_page(browser: Browser) -> Page:
    """Create a new page with a clean context."""
    context = browser.new_context(viewport={"width": 1280, "height": 1080})
    page = context.new_page()
    # Set default timeout
    page.set_default_timeout(TIMEOUT_NAVIGATION)
    return page

def close_page(page: Page):
    """Close the page and its context."""
    try:
        context = page.context
        page.close()
        context.close()
    except:
        pass

# -----------------------------------------------------------------------------
# Navigation helpers (per fresh page)
# -----------------------------------------------------------------------------
def navigate_to_first_form(page: Page) -> bool:
    """Navigate to home, accept cookies, click Order, wait for fields. Return success."""
    try:
        page.goto(srv_cfg.base_url, wait_until="networkidle", timeout=TIMEOUT_NAVIGATION)
        if page.locator('[aria-label="Accept cookies"]').count():
            page.click('[aria-label="Accept cookies"]', timeout=TIMEOUT_ACTION)
            time.sleep(0.5)
        page.click('button:has-text("Order")', timeout=TIMEOUT_ACTION)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT_NAVIGATION)
        # Wait for mandatory fields
        mandatory = [
            'input[placeholder="* First name"]',
            'input[placeholder="* Last name"]',
            'input[placeholder="* Address: where to bring the scooter"]',
            'input[placeholder="* Subway station"]',
            'input[placeholder="* Phone: the courier will call you"]',
        ]
        for sel in mandatory:
            page.wait_for_selector(sel, state="visible", timeout=TIMEOUT_ELEMENT)
        return True
    except Exception as e:
        log(f"Navigation failed: {e}")
        return False

def select_metro_station(page: Page) -> bool:
    try:
        page.locator('input[placeholder="* Subway station"]').click()
        time.sleep(0.5)
        page.wait_for_selector('.select-search__option, .select-search__options li', timeout=TIMEOUT_ELEMENT)
        page.locator('.select-search__option, .select-search__options li').first.click()
        time.sleep(0.5)
        return True
    except Exception as e:
        log(f"Metro selection failed: {e}")
        return False

def fill_first_form(page: Page, exclude_field: Optional[str] = None, exclude_value: str = "") -> bool:
    values = {
        "first_name": VALID_FIRST_NAME,
        "last_name": VALID_LAST_NAME,
        "address": VALID_ADDRESS,
        "phone": VALID_PHONE
    }
    if exclude_field in values:
        values[exclude_field] = exclude_value

    try:
        page.fill('input[placeholder="* First name"]', values["first_name"])
        page.fill('input[placeholder="* Last name"]', values["last_name"])
        page.fill('input[placeholder="* Address: where to bring the scooter"]', values["address"])
        page.fill('input[placeholder="* Phone: the courier will call you"]', values["phone"])

        if exclude_field != "metro":
            if not select_metro_station(page):
                return False
        else:
            metro_input = page.locator('input[placeholder="* Subway station"]')
            metro_input.fill(exclude_value)
            metro_input.press("Enter")
        return True
    except Exception as e:
        log(f"Fill form failed: {e}")
        return False

def click_next(page: Page) -> bool:
    try:
        page.click('button:has-text("Next")', timeout=TIMEOUT_ACTION)
        time.sleep(1.5)
        # Check if second form appears
        page.wait_for_selector('input[placeholder="* When to deliver the scooter"]', timeout=TIMEOUT_SHORT)
        return True
    except:
        return False

# -----------------------------------------------------------------------------
# Individual test function (creates its own page)
# -----------------------------------------------------------------------------
def test_field_validation(browser: Browser, field: str, value: str, expected_error: str, screenshot_name: str) -> Dict[str, Any]:
    """Run a single validation test on a fresh page."""
    result = {
        "field": field,
        "test_value": value,
        "expected_error": expected_error,
        "error_visible": False,
        "field_class": "",
        "js_errors": [],
        "error": None
    }
    page = None
    try:
        page = create_fresh_page(browser)
        js_errors = get_console_errors(page)
        if not navigate_to_first_form(page):
            result["error"] = "Navigation failed"
            return result
        if not fill_first_form(page, exclude_field=field, exclude_value=value):
            result["error"] = "Form fill failed"
            return result
        success = click_next(page)
        take_screenshot(page, screenshot_name)
        if success:
            result["error_visible"] = False
        else:
            result["error_visible"] = is_error_visible(page, expected_error)
        # Capture field class
        if field != "metro":
            placeholder_map = {
                "first_name": "* First name",
                "last_name": "* Last name",
                "address": "* Address: where to bring the scooter",
                "phone": "* Phone: the courier will call you"
            }
            if field in placeholder_map:
                selector = f'input[placeholder="{placeholder_map[field]}"]'
                result["field_class"] = safe_get_attribute(page, selector, "class")
        result["js_errors"] = js_errors
    except Exception as e:
        result["error"] = str(e)
    finally:
        if page:
            close_page(page)
        time.sleep(WAIT_BETWEEN_TESTS)  # Cooldown
    return result

# -----------------------------------------------------------------------------
# Main analysis
# -----------------------------------------------------------------------------
def analyze():
    log("=== PROFESSIONAL DOM ANALYSIS (ISOLATED PAGES) ===")

    opera_path = br_cfg.opera_executable
    if not opera_path or not Path(opera_path).exists():
        log(f"Opera not found, using Chromium")
        opera_path = None

    with sync_playwright() as p:
        launch_opts = {"headless": False, "slow_mo": 200}
        if opera_path:
            launch_opts["executable_path"] = opera_path
        browser = p.chromium.launch(**launch_opts)

        # ---- 1. Extract basic selectors (using a single page) ----
        page = create_fresh_page(browser)
        navigate_to_first_form(page)
        take_screenshot(page, "00_initial_form")
        selectors_info = {}
        fields_sel = {
            "first_name": 'input[placeholder="* First name"]',
            "last_name": 'input[placeholder="* Last name"]',
            "address": 'input[placeholder="* Address: where to bring the scooter"]',
            "metro": 'input[placeholder="* Subway station"]',
            "phone": 'input[placeholder="* Phone: the courier will call you"]',
        }
        for name, sel in fields_sel.items():
            elem = page.locator(sel).first
            selectors_info[name] = {
                "selector": sel,
                "visible": elem.is_visible() if elem.count() else False,
                "class": elem.get_attribute("class") or "",
                "placeholder": elem.get_attribute("placeholder") or ""
            }
        close_page(page)
        time.sleep(WAIT_BETWEEN_TESTS)

        # ---- 2. Run field validation tests (each on fresh page) ----
        validation_results = {}

        log("Testing: First name empty")
        validation_results["name_empty"] = test_field_validation(
            browser, "first_name", "", ERROR_MSGS["first_name"], "01_error_name_empty"
        )

        log("Testing: Last name empty")
        validation_results["last_empty"] = test_field_validation(
            browser, "last_name", "", ERROR_MSGS["last_name"], "02_error_last_empty"
        )

        log("Testing: Address empty")
        validation_results["address_empty"] = test_field_validation(
            browser, "address", "", ERROR_MSGS["address"], "03_error_address_empty"
        )

        log("Testing: Phone empty")
        validation_results["phone_empty"] = test_field_validation(
            browser, "phone", "", ERROR_MSGS["phone"], "04_error_phone_empty"
        )

        log("Testing: Phone 10 digits (expected bug)")
        validation_results["phone_10_digits"] = test_field_validation(
            browser, "phone", "1234567890", ERROR_MSGS["phone"], "05_phone_10_digits"
        )
        validation_results["phone_10_digits"]["note"] = "10 digits should be valid but likely fails"

        log("Testing: Invalid metro station")
        page_invalid = create_fresh_page(browser)
        try:
            navigate_to_first_form(page_invalid)
            fill_first_form(page_invalid, exclude_field="metro", exclude_value="Imaginary Station")
            success = click_next(page_invalid)
            take_screenshot(page_invalid, "06_metro_invalid")
            validation_results["metro_invalid"] = {
                "blocked_advance": not success,
                "note": "No specific error message, but blocks advance"
            }
        except Exception as e:
            validation_results["metro_invalid"] = {"error": str(e)}
        finally:
            close_page(page_invalid)
            time.sleep(WAIT_BETWEEN_TESTS)

        # ---- 3. Second form analysis (on a fresh page) ----
        page2 = create_fresh_page(browser)
        second_form_info = {}
        try:
            if not navigate_to_first_form(page2):
                second_form_info["error"] = "Navigation failed"
            else:
                if not fill_first_form(page2):
                    second_form_info["error"] = "Form fill failed"
                else:
                    if not click_next(page2):
                        second_form_info["error"] = "Could not reach second form"
                    else:
                        take_screenshot(page2, "07_second_form_loaded")
                        # Delivery date
                        date_input = page2.locator('input[placeholder="* When to deliver the scooter"]')
                        second_form_info["delivery_date_readonly"] = date_input.get_attribute("readonly") is not None
                        date_input.fill("2026-05-01")
                        page2.click('body')
                        time.sleep(0.5)
                        manual_value = date_input.input_value()
                        second_form_info["delivery_date_manual_allowed"] = (manual_value == "2026-05-01")
                        # Calendar today disabled?
                        date_input.click()
                        page2.wait_for_selector('.react-datepicker', timeout=TIMEOUT_ELEMENT)
                        take_screenshot(page2, "08_calendar")
                        today = date.today()
                        day_str = str(today.day)
                        day_selector = f'.react-datepicker__day:not(.react-datepicker__day--outside-month):has-text("{day_str}")'
                        day_elem = page2.locator(day_selector).first
                        day_classes = day_elem.get_attribute("class") or ""
                        second_form_info["calendar_today_disabled"] = "disabled" in day_classes
                        page2.keyboard.press("Escape")
                        # Rental period dropdown
                        period_control = page2.locator('.Dropdown-control')
                        period_control.click()
                        page2.wait_for_selector('.Dropdown-option', timeout=TIMEOUT_ELEMENT)
                        options = page2.locator('.Dropdown-option').all_text_contents()
                        second_form_info["rental_period_options"] = options
                        default_text = period_control.inner_text()
                        second_form_info["rental_period_default"] = default_text
                        page2.keyboard.press("Escape")
                        # Empty period
                        page2.evaluate("document.querySelector('.Dropdown-control').innerText = ''")
                        page2.click('button:has-text("Order")', timeout=TIMEOUT_ACTION)
                        time.sleep(1.5)
                        take_screenshot(page2, "09_period_empty")
                        second_form_info["rental_period_empty_error"] = is_error_visible(page2, ERROR_MSGS["period"])
                        # Long comment
                        page2.locator('.Dropdown-control').click()
                        page2.click('.Dropdown-option:has-text("a day")')
                        comment_field = page2.locator('input[placeholder="Comment"]')
                        maxlength = comment_field.get_attribute("maxlength")
                        second_form_info["comment_maxlength"] = maxlength if maxlength else "not_set"
                        comment_field.fill("a" * 25)
                        page2.click('button:has-text("Order")', timeout=TIMEOUT_ACTION)
                        time.sleep(1.5)
                        take_screenshot(page2, "10_comment_long")
                        second_form_info["comment_too_long_error"] = is_error_visible(page2, ERROR_MSGS["comment"])
                        # Successful order
                        comment_field.fill("")
                        page2.click('button:has-text("Order")', timeout=TIMEOUT_ACTION)
                        modal = page2.locator('[class*="Modal"]').first
                        try:
                            modal.wait_for(state="visible", timeout=10000)
                            modal_text = modal.inner_text()
                            track_match = re.search(r'\b\d{6,}\b', modal_text)
                            second_form_info["success_modal"] = {
                                "visible": True,
                                "track": track_match.group() if track_match else None,
                                "text_preview": modal_text[:200]
                            }
                            take_screenshot(page2, "11_success_modal")
                        except Exception as e:
                            second_form_info["success_modal"] = {"visible": False, "error": str(e)}
        except Exception as e:
            second_form_info["error"] = str(e)
        finally:
            close_page(page2)

        # ---- 4. Final report ----
        report = {
            "timestamp": datetime.now().isoformat(),
            "base_url": srv_cfg.base_url,
            "browser": "Opera" if opera_path else "Chromium",
            "selectors": selectors_info,
            "validation_results": validation_results,
            "second_form": second_form_info,
            "notes": {
                "cookie_selector": '[aria-label="Accept cookies"]',
                "known_bugs": [
                    "Phone field does not accept 10 digits (requires 11-12)",
                    "Calendar today is not disabled",
                    "Rental period empty does not show error (always has default)",
                    "React application shows 'Cannot read properties of undefined' after multiple interactions"
                ]
            }
        }

        with open(JSON_REPORT, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        log(f"=== ANALYSIS COMPLETE ===")
        log(f"Report saved to {JSON_REPORT}")
        browser.close()

if __name__ == "__main__":
    analyze()