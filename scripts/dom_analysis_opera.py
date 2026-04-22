#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis completo del DOM de los dos formularios de pedido en Opera.
Genera un JSON detallado con todos los localizadores, clases, errores y comportamientos.
"""
import json
import sys
import time
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_URL = "https://cnt-55898848-8e8e-4565-9924-ac6ab4bd4b0b.containerhub.tripleten-services.com"
OPERA_PATH = "/usr/bin/opera"
OUT_DIR = Path(__file__).parent.parent / "screenshots" / "tarea_2_formulario" / "analysis2"
OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = OUT_DIR / "dom_full_analysis.json"

report = {}

def ss(page, name):
    path = OUT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"  📸 {name}.png")
    return str(path)

def attr(page, selector, attribute):
    try:
        el = page.locator(selector).first
        if el.count():
            return el.get_attribute(attribute)
    except:
        pass
    return None

def classes(page, selector):
    return attr(page, selector, "class") or ""

def inner_text(page, selector):
    try:
        el = page.locator(selector).first
        if el.count() and el.is_visible(timeout=2000):
            return el.inner_text().strip()
    except:
        pass
    return ""

def is_visible(page, selector, timeout=2000):
    try:
        return page.locator(selector).first.is_visible(timeout=timeout)
    except:
        return False

def fresh_page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    return pg

def go_to_form1(page):
    page.goto(BASE_URL, wait_until="networkidle")
    page.wait_for_timeout(1000)
    # Click Order button
    page.locator('button:has-text("Order")').first.click()
    page.wait_for_selector('input[placeholder="* First name"]', state="visible", timeout=10000)
    page.wait_for_timeout(500)

def select_metro(page):
    metro = page.locator('input[placeholder="* Subway station"]')
    metro.click()
    page.wait_for_timeout(800)
    # Try to get dropdown options
    opts = page.locator('.select-search__option, .select-search__options li, [class*="select-search"] li')
    if opts.count() > 0:
        first_opt = opts.first
        opt_text = first_opt.inner_text().strip()
        opt_class = first_opt.get_attribute("class") or ""
        first_opt.click()
        page.wait_for_timeout(500)
        return opt_text, opt_class
    return "NO OPTIONS FOUND", ""

def fill_form1_valid(page, overrides=None):
    data = {
        "first_name": "Juan",
        "last_name": "Perez",
        "address": "Calle Falsa 123",
        "phone": "12345678901",
    }
    if overrides:
        data.update(overrides)

    if data.get("first_name") is not None:
        page.fill('input[placeholder="* First name"]', data["first_name"])
    if data.get("last_name") is not None:
        page.fill('input[placeholder="* Last name"]', data["last_name"])
    if data.get("address") is not None:
        page.fill('input[placeholder="* Address: where to bring the scooter"]', data["address"])
    if data.get("phone") is not None:
        page.fill('input[placeholder="* Phone: the courier will call you"]', data["phone"])

    if data.get("metro", "__default__") != "__skip__":
        metro_text, metro_opt_class = select_metro(page)
        data["_metro_selected"] = metro_text
        data["_metro_opt_class"] = metro_opt_class
    return data

def click_next(page):
    page.locator('button:has-text("Next")').click()
    page.wait_for_timeout(1500)
    return is_visible(page, 'input[placeholder="* When to deliver the scooter"]', timeout=3000)

# ─── MAIN ──────────────────────────────────────────────────────────────────────
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=OPERA_PATH,
        headless=True,
        slow_mo=100,
        args=["--start-maximized"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 1: Estructura básica del formulario 1
    # ══════════════════════════════════════════════════════════════════════════
    print("\n=== BLOQUE 1: Estructura básica formulario 1 ===")
    pg = fresh_page(browser)
    go_to_form1(pg)
    ss(pg, "B1_form1_initial")

    # Input fields attributes
    inputs = {
        "first_name": 'input[placeholder="* First name"]',
        "last_name":  'input[placeholder="* Last name"]',
        "address":    'input[placeholder="* Address: where to bring the scooter"]',
        "metro":      'input[placeholder="* Subway station"]',
        "phone":      'input[placeholder="* Phone: the courier will call you"]',
    }
    form1_selectors = {}
    for name, sel in inputs.items():
        el = pg.locator(sel).first
        form1_selectors[name] = {
            "selector": sel,
            "class":       el.get_attribute("class"),
            "id":          el.get_attribute("id"),
            "type":        el.get_attribute("type"),
            "maxlength":   el.get_attribute("maxlength"),
            "readonly":    el.get_attribute("readonly"),
            "placeholder": el.get_attribute("placeholder"),
        }
        # Also grab the wrapper div class
        wrapper_class = pg.evaluate(f"""
            (function() {{
                const inp = document.querySelector('{sel.replace("'", "\\'")}');
                if (!inp) return null;
                const wrapper = inp.parentElement;
                return wrapper ? wrapper.className : null;
            }})()
        """)
        form1_selectors[name]["wrapper_class"] = wrapper_class

    # Button classes
    next_btn = pg.locator('button:has-text("Next")').first
    form1_selectors["next_button"] = {
        "selector": 'button:has-text("Next")',
        "class": next_btn.get_attribute("class"),
        "text": next_btn.inner_text().strip(),
    }
    report["form1_selectors"] = form1_selectors
    print(json.dumps(form1_selectors, indent=2, ensure_ascii=False))
    pg.close()

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 2: Errores al hacer clic en Next sin llenar nada
    # ══════════════════════════════════════════════════════════════════════════
    print("\n=== BLOQUE 2: Errores sin llenar campos ===")
    pg = fresh_page(browser)
    go_to_form1(pg)
    pg.locator('button:has-text("Next")').click()
    pg.wait_for_timeout(1500)
    ss(pg, "B2_all_empty_errors")

    # Find all error messages
    error_texts = pg.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('*').forEach(el => {
                const txt = el.innerText ? el.innerText.trim() : '';
                if (txt && txt.length < 100 && el.children.length === 0) {
                    const cls = el.className || '';
                    if (cls.toLowerCase().includes('error') || cls.toLowerCase().includes('warning')) {
                        results.push({ tag: el.tagName, class: cls, text: txt });
                    }
                }
            });
            return results;
        }
    """)
    # Also check field classes after error
    field_classes_after_error = {}
    for name, sel in inputs.items():
        if name != "metro":
            field_classes_after_error[name] = pg.locator(sel).first.get_attribute("class")
    # Check for any visible text that looks like an error
    all_visible_p = pg.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('p, span, div, label').forEach(el => {
                const txt = el.innerText ? el.innerText.trim() : '';
                if (txt && !el.querySelector('*') && txt.length < 120) {
                    results.push({ tag: el.tagName, class: el.className, text: txt });
                }
            });
            return results;
        }
    """)
    report["form1_errors_all_empty"] = {
        "error_elements": error_texts,
        "field_classes_after_next": field_classes_after_error,
        "all_leaf_texts": all_visible_p[:60],  # first 60
    }
    print("Error elements:", json.dumps(error_texts, indent=2, ensure_ascii=False))
    print("Field classes after Next:", json.dumps(field_classes_after_error, indent=2, ensure_ascii=False))
    pg.close()

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 3: Metro dropdown selector details
    # ══════════════════════════════════════════════════════════════════════════
    print("\n=== BLOQUE 3: Metro dropdown ===")
    pg = fresh_page(browser)
    go_to_form1(pg)
    metro_inp = pg.locator('input[placeholder="* Subway station"]')
    metro_inp.click()
    pg.wait_for_timeout(1000)
    ss(pg, "B3_metro_dropdown_open")
    metro_info = pg.evaluate("""
        () => {
            const results = { container: null, options: [] };
            // Find dropdown container
            const containers = [
                '.select-search__options',
                '.select-search',
                '[class*="select-search"]',
                'ul[class*="select"]',
            ];
            for (const sel of containers) {
                const el = document.querySelector(sel);
                if (el) { results.container = { selector: sel, class: el.className }; break; }
            }
            // Find options
            const optSelectors = [
                '.select-search__option',
                '.select-search__options li',
                '[class*="select-search"] li',
                '[class*="select-search"] button',
            ];
            for (const sel of optSelectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    els.forEach((el, i) => {
                        if (i < 10) results.options.push({
                            selector: sel,
                            class: el.className,
                            text: el.innerText.trim(),
                            tag: el.tagName
                        });
                    });
                    break;
                }
            }
            return results;
        }
    """)
    report["metro_dropdown"] = metro_info
    print(json.dumps(metro_info, indent=2, ensure_ascii=False))
    # Select first option
    first_opt = pg.locator('.select-search__option, .select-search__options li').first
    metro_selected_text = first_opt.inner_text().strip()
    first_opt.click()
    pg.wait_for_timeout(500)
    metro_value_after = metro_inp.input_value()
    report["metro_dropdown"]["selected_text"] = metro_selected_text
    report["metro_dropdown"]["value_after_select"] = metro_value_after
    print(f"Metro selected: '{metro_selected_text}', input value: '{metro_value_after}'")
    pg.close()

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 4: Validación campo por campo (errores individuales)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n=== BLOQUE 4: Validaciones individuales ===")
    field_validations = {}

    test_cases = [
        ("name_empty",       {"first_name": ""}),
        ("name_1char",       {"first_name": "A"}),
        ("name_2chars",      {"first_name": "Al"}),
        ("name_15chars",     {"first_name": "Maria-Jose-Lopez"}),
        ("name_16chars",     {"first_name": "Maria-Jose-LopezX"}),
        ("lastname_empty",   {"last_name": ""}),
        ("lastname_1char",   {"last_name": "L"}),
        ("lastname_2chars",  {"last_name": "Li"}),
        ("address_empty",    {"address": ""}),
        ("address_4chars",   {"address": "Ab 1"}),
        ("address_5chars",   {"address": "Calle"}),
        ("phone_empty",      {"phone": ""}),
        ("phone_9digits",    {"phone": "123456789"}),
        ("phone_10digits",   {"phone": "1234567890"}),
        ("phone_11digits",   {"phone": "12345678901"}),
        ("phone_12digits",   {"phone": "123456789012"}),
        ("phone_13digits",   {"phone": "1234567890123"}),
        ("phone_plus_valid", {"phone": "+12345678901"}),
        ("phone_dashes",     {"phone": "123-456-7890"}),
    ]

    for case_name, override in test_cases:
        print(f"  Testing: {case_name}")
        pg = fresh_page(browser)
        try:
            go_to_form1(pg)
            defaults = {"first_name": "Juan", "last_name": "Perez",
                        "address": "Calle Falsa 123", "phone": "12345678901"}
            defaults.update(override)

            if defaults.get("first_name") is not None:
                pg.fill('input[placeholder="* First name"]', defaults["first_name"])
            if defaults.get("last_name") is not None:
                pg.fill('input[placeholder="* Last name"]', defaults["last_name"])
            if defaults.get("address") is not None:
                pg.fill('input[placeholder="* Address: where to bring the scooter"]', defaults["address"])
            if defaults.get("phone") is not None:
                pg.fill('input[placeholder="* Phone: the courier will call you"]', defaults["phone"])

            # Select metro
            metro_inp2 = pg.locator('input[placeholder="* Subway station"]')
            metro_inp2.click()
            pg.wait_for_timeout(800)
            opts2 = pg.locator('.select-search__option, .select-search__options li')
            if opts2.count() > 0:
                opts2.first.click()
                pg.wait_for_timeout(500)

            pg.locator('button:has-text("Next")').click()
            pg.wait_for_timeout(1500)

            advanced = is_visible(pg, 'input[placeholder="* When to deliver the scooter"]', timeout=2000)

            # Collect error info
            error_info = pg.evaluate("""
                () => {
                    const errors = [];
                    document.querySelectorAll('*').forEach(el => {
                        if (!el.querySelector('*')) {
                            const txt = el.innerText ? el.innerText.trim() : '';
                            const cls = el.className || '';
                            if (txt && (cls.toLowerCase().includes('error') ||
                                txt.toLowerCase().includes('valid') ||
                                txt.toLowerCase().includes('enter') ||
                                txt.toLowerCase().includes('introduce'))) {
                                errors.push({ tag: el.tagName, class: cls, text: txt });
                            }
                        }
                    });
                    return errors;
                }
            """)

            # Get field class for the tested field  
            field_map = {
                "first_name": 'input[placeholder="* First name"]',
                "last_name": 'input[placeholder="* Last name"]',
                "address": 'input[placeholder="* Address: where to bring the scooter"]',
                "phone": 'input[placeholder="* Phone: the courier will call you"]',
            }
            tested_field = list(override.keys())[0]
            field_class = ""
            if tested_field in field_map:
                field_class = pg.locator(field_map[tested_field]).first.get_attribute("class") or ""

            ss(pg, f"B4_{case_name}")
            field_validations[case_name] = {
                "override": override,
                "advanced_to_form2": advanced,
                "error_elements": error_info,
                "tested_field_class": field_class,
            }
            print(f"    advanced={advanced}, errors={len(error_info)}, field_class='{field_class}'")
        except Exception as e:
            field_validations[case_name] = {"error": str(e)}
            print(f"    ERROR: {e}")
        finally:
            pg.close()
            time.sleep(1)

    report["field_validations"] = field_validations

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 5: Formulario 2 - estructura completa
    # ══════════════════════════════════════════════════════════════════════════
    print("\n=== BLOQUE 5: Estructura formulario 2 ===")
    pg = fresh_page(browser)
    go_to_form1(pg)
    pg.fill('input[placeholder="* First name"]', "Juan")
    pg.fill('input[placeholder="* Last name"]', "Perez")
    pg.fill('input[placeholder="* Address: where to bring the scooter"]', "Calle Falsa 123")
    pg.fill('input[placeholder="* Phone: the courier will call you"]', "12345678901")
    metro_inp3 = pg.locator('input[placeholder="* Subway station"]')
    metro_inp3.click()
    pg.wait_for_timeout(800)
    pg.locator('.select-search__option, .select-search__options li').first.click()
    pg.wait_for_timeout(500)
    pg.locator('button:has-text("Next")').click()
    pg.wait_for_selector('input[placeholder="* When to deliver the scooter"]', state="visible", timeout=10000)
    pg.wait_for_timeout(500)
    ss(pg, "B5_form2_initial")

    form2 = {}

    # Date input
    date_inp = pg.locator('input[placeholder="* When to deliver the scooter"]').first
    form2["delivery_date"] = {
        "selector": 'input[placeholder="* When to deliver the scooter"]',
        "class": date_inp.get_attribute("class"),
        "readonly": date_inp.get_attribute("readonly"),
        "type": date_inp.get_attribute("type"),
        "placeholder": date_inp.get_attribute("placeholder"),
    }
    # Try manual input
    date_inp.fill("2026-12-01")
    pg.locator("body").click()
    pg.wait_for_timeout(500)
    manual_val = date_inp.input_value()
    form2["delivery_date"]["manual_input_value"] = manual_val
    form2["delivery_date"]["manual_input_accepted"] = (manual_val == "2026-12-01")

    # Open calendar
    date_inp.click()
    pg.wait_for_timeout(800)
    ss(pg, "B5_calendar_open")

    calendar_info = pg.evaluate("""
        () => {
            const info = {};
            // Container
            const cal = document.querySelector('.react-datepicker');
            info.container_class = cal ? cal.className : null;
            // Month header
            const month = document.querySelector('.react-datepicker__current-month');
            info.month_header_class = month ? month.className : null;
            info.month_text = month ? month.innerText : null;
            // Nav buttons
            const prev = document.querySelector('.react-datepicker__navigation--previous');
            const next = document.querySelector('.react-datepicker__navigation--next');
            info.nav_prev_class = prev ? prev.className : null;
            info.nav_next_class = next ? next.className : null;
            // Day cells - sample different types
            const allDays = document.querySelectorAll('.react-datepicker__day');
            const daySamples = [];
            allDays.forEach((d, i) => {
                if (i < 35) daySamples.push({ class: d.className, text: d.innerText });
            });
            info.day_samples = daySamples;
            // Today cell
            const today = document.querySelector('.react-datepicker__day--today');
            info.today_class = today ? today.className : null;
            info.today_text = today ? today.innerText : null;
            // Disabled days
            const disabled = document.querySelector('.react-datepicker__day--disabled');
            info.disabled_day_class = disabled ? disabled.className : null;
            // Outside month
            const outside = document.querySelector('.react-datepicker__day--outside-month');
            info.outside_month_class = outside ? outside.className : null;
            // Selected day
            const selected = document.querySelector('.react-datepicker__day--selected');
            info.selected_class = selected ? selected.className : null;
            return info;
        }
    """)
    form2["calendar"] = calendar_info
    print("Calendar info:", json.dumps(calendar_info, indent=2, ensure_ascii=False))

    # Click a future day (tomorrow) and check the result
    tomorrow = date.today() + timedelta(days=1)
    day_str = str(tomorrow.day)
    future_day_sel = f'.react-datepicker__day:not(.react-datepicker__day--outside-month):not(.react-datepicker__day--disabled):has-text("{day_str}")'
    try:
        pg.locator(future_day_sel).first.click()
        pg.wait_for_timeout(500)
        date_value_after = date_inp.input_value()
        date_class_after = date_inp.get_attribute("class")
        form2["delivery_date"]["value_after_calendar_select"] = date_value_after
        form2["delivery_date"]["class_after_select"] = date_class_after
        print(f"  Date after select: '{date_value_after}', class: '{date_class_after}'")
    except Exception as e:
        form2["delivery_date"]["calendar_select_error"] = str(e)

    # Rental period dropdown
    pg.wait_for_timeout(300)
    dropdown_ctrl = pg.locator('.Dropdown-control').first
    form2["rental_period"] = {
        "control_class": dropdown_ctrl.get_attribute("class"),
        "control_text": dropdown_ctrl.inner_text().strip(),
        "selector_control": ".Dropdown-control",
        "selector_option": ".Dropdown-option",
    }
    dropdown_ctrl.click()
    pg.wait_for_timeout(600)
    ss(pg, "B5_rental_period_open")
    options_info = pg.evaluate("""
        () => {
            const opts = document.querySelectorAll('.Dropdown-option');
            return Array.from(opts).map(o => ({ class: o.className, text: o.innerText.trim() }));
        }
    """)
    form2["rental_period"]["options"] = options_info
    print("Rental options:", json.dumps(options_info, indent=2))
    # Select first option
    pg.locator('.Dropdown-option').first.click()
    pg.wait_for_timeout(400)

    # Color checkboxes
    color_info = pg.evaluate("""
        () => {
            const result = {};
            ['black', 'grey'].forEach(color => {
                const cb = document.getElementById(color);
                if (cb) {
                    const label = document.querySelector(`label[for="${color}"]`);
                    const wrapper = cb.parentElement;
                    result[color] = {
                        id: cb.id,
                        name: cb.name,
                        class: cb.className,
                        type: cb.type,
                        label_text: label ? label.innerText.trim() : null,
                        label_for: label ? label.getAttribute('for') : null,
                        label_class: label ? label.className : null,
                        wrapper_class: wrapper ? wrapper.className : null,
                    };
                } else {
                    result[color] = { error: 'not found by id' };
                }
            });
            return result;
        }
    """)
    form2["color_checkboxes"] = color_info
    print("Color checkboxes:", json.dumps(color_info, indent=2))

    # Comment field
    comment_inp = pg.locator('input[placeholder="Comment"]').first
    form2["comment"] = {
        "selector": 'input[placeholder="Comment"]',
        "class": comment_inp.get_attribute("class"),
        "type": comment_inp.get_attribute("type"),
        "maxlength": comment_inp.get_attribute("maxlength"),
        "placeholder": comment_inp.get_attribute("placeholder"),
    }

    # Back and Order buttons
    back_btn = pg.locator('button:has-text("Back")').first
    order_btn = pg.locator('button:has-text("Order")').first
    form2["back_button"] = {
        "selector": 'button:has-text("Back")',
        "class": back_btn.get_attribute("class") if back_btn.count() else None,
        "text": back_btn.inner_text().strip() if back_btn.count() else None,
    }
    form2["order_button"] = {
        "selector": 'button:has-text("Order")',
        "class": order_btn.get_attribute("class") if order_btn.count() else None,
        "text": order_btn.inner_text().strip() if order_btn.count() else None,
    }
    print("Back btn:", form2["back_button"])
    print("Order btn:", form2["order_button"])
    print("Comment:", form2["comment"])

    report["form2_selectors"] = form2
    pg.close()

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 6: Success modal
    # ══════════════════════════════════════════════════════════════════════════
    print("\n=== BLOQUE 6: Modal de éxito (envío completo) ===")
    pg = fresh_page(browser)
    go_to_form1(pg)
    pg.fill('input[placeholder="* First name"]', "Juan")
    pg.fill('input[placeholder="* Last name"]', "Perez")
    pg.fill('input[placeholder="* Address: where to bring the scooter"]', "Calle Falsa 123")
    pg.fill('input[placeholder="* Phone: the courier will call you"]', "12345678901")
    metro_inp4 = pg.locator('input[placeholder="* Subway station"]')
    metro_inp4.click()
    pg.wait_for_timeout(800)
    pg.locator('.select-search__option, .select-search__options li').first.click()
    pg.wait_for_timeout(500)
    pg.locator('button:has-text("Next")').click()
    pg.wait_for_selector('input[placeholder="* When to deliver the scooter"]', state="visible", timeout=10000)
    pg.wait_for_timeout(500)
    # Select date
    date_inp2 = pg.locator('input[placeholder="* When to deliver the scooter"]').first
    date_inp2.click()
    pg.wait_for_timeout(800)
    tomorrow2 = date.today() + timedelta(days=1)
    day_str2 = str(tomorrow2.day)
    future_sel2 = f'.react-datepicker__day:not(.react-datepicker__day--outside-month):not(.react-datepicker__day--disabled):has-text("{day_str2}")'
    pg.locator(future_sel2).first.click()
    pg.wait_for_timeout(500)
    # Select rental period
    pg.locator('.Dropdown-control').first.click()
    pg.wait_for_timeout(400)
    pg.locator('.Dropdown-option').first.click()
    pg.wait_for_timeout(400)
    # Submit
    pg.locator('button:has-text("Order")').click()
    pg.wait_for_timeout(3000)
    ss(pg, "B6_after_order_click")

    modal_info = pg.evaluate("""
        () => {
            const result = {};
            // Try different modal selectors
            const selectors = [
                '[class*="Modal"]',
                '[class*="modal"]',
                '[role="dialog"]',
                '[class*="Order_Modal"]',
                '[class*="overlay"]',
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetParent !== null) {
                    result.found_selector = sel;
                    result.class = el.className;
                    result.inner_text = el.innerText;
                    // Buttons inside modal
                    result.buttons = Array.from(el.querySelectorAll('button')).map(b => ({
                        text: b.innerText.trim(),
                        class: b.className
                    }));
                    break;
                }
            }
            if (!result.found_selector) {
                // Fallback: find anything that appeared
                result.all_modals = Array.from(document.querySelectorAll('[class*="Modal"], [class*="modal"]')).map(el => ({
                    class: el.className,
                    visible: el.offsetParent !== null,
                    text_preview: el.innerText.slice(0, 200)
                }));
            }
            return result;
        }
    """)
    print("Modal info:", json.dumps(modal_info, indent=2, ensure_ascii=False))
    report["success_modal"] = modal_info
    ss(pg, "B6_success_modal")
    pg.close()

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 7: Error al enviar form2 sin fecha
    # ══════════════════════════════════════════════════════════════════════════
    print("\n=== BLOQUE 7: Errores en formulario 2 ===")
    pg = fresh_page(browser)
    go_to_form1(pg)
    pg.fill('input[placeholder="* First name"]', "Juan")
    pg.fill('input[placeholder="* Last name"]', "Perez")
    pg.fill('input[placeholder="* Address: where to bring the scooter"]', "Calle Falsa 123")
    pg.fill('input[placeholder="* Phone: the courier will call you"]', "12345678901")
    metro_inp5 = pg.locator('input[placeholder="* Subway station"]')
    metro_inp5.click()
    pg.wait_for_timeout(800)
    pg.locator('.select-search__option, .select-search__options li').first.click()
    pg.wait_for_timeout(500)
    pg.locator('button:has-text("Next")').click()
    pg.wait_for_selector('input[placeholder="* When to deliver the scooter"]', state="visible", timeout=10000)
    pg.wait_for_timeout(500)

    # Click Order WITHOUT selecting date or rental period
    pg.locator('button:has-text("Order")').click()
    pg.wait_for_timeout(1500)
    ss(pg, "B7_form2_no_date_no_period")

    form2_errors = pg.evaluate("""
        () => {
            const errors = [];
            document.querySelectorAll('*').forEach(el => {
                if (!el.querySelector('*')) {
                    const txt = el.innerText ? el.innerText.trim() : '';
                    const cls = el.className || '';
                    if (txt && (cls.toLowerCase().includes('error') || cls.toLowerCase().includes('warning'))) {
                        errors.push({ tag: el.tagName, class: cls, text: txt });
                    }
                }
            });
            // Also check field classes
            const dateInp = document.querySelector('input[placeholder="* When to deliver the scooter"]');
            const dropdownCtrl = document.querySelector('.Dropdown-control');
            return {
                error_elements: errors,
                date_class: dateInp ? dateInp.className : null,
                dropdown_class: dropdownCtrl ? dropdownCtrl.className : null,
            };
        }
    """)
    report["form2_errors"] = form2_errors
    print("Form2 errors:", json.dumps(form2_errors, indent=2, ensure_ascii=False))
    pg.close()

    # ══════════════════════════════════════════════════════════════════════════
    # SAVE REPORT
    # ══════════════════════════════════════════════════════════════════════════
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Análisis completo guardado en: {REPORT_PATH}")
    browser.close()
