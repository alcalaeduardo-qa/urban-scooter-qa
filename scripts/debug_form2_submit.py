"""
Debug: ¿Qué pasa al hacer click en 'Order' en el form 2?
Busca todos los botones, modales y popups que aparecen.
"""
import os, sys
sys.path.insert(0, str(__file__).replace("/scripts/debug_form2_submit.py", ""))

from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright
from datetime import date, timedelta

BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:3000")
OPERA    = os.getenv("OPERA_EXECUTABLE_PATH", "")

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=OPERA or None,
            headless=False,
            slow_mo=300,
        )
        ctx  = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        print(f"Navigating to {BASE_URL}")
        page.goto(BASE_URL, wait_until="networkidle")

        # Home → click Order
        page.locator('button:has-text("Order")').first.click()
        page.wait_for_selector('input[placeholder="* First name"]', timeout=10_000)
        page.wait_for_timeout(500)

        # Fill form 1
        page.fill('input[placeholder="* First name"]',  "Juan")
        page.fill('input[placeholder="* Last name"]',   "Perez")
        page.fill('input[placeholder="* Address: where to bring the scooter"]', "Calle 123")
        page.fill('input[placeholder="* Phone: the courier will call you"]', "12345678901")
        # Metro
        page.locator('input[placeholder="* Subway station"]').click()
        page.wait_for_timeout(800)
        opts = page.locator('.select-search__option')
        print(f"Metro options count: {opts.count()}")
        opts.first.click()
        page.wait_for_timeout(400)

        # Next
        page.locator('button:has-text("Next")').click()
        page.wait_for_selector('input[placeholder="* When to deliver the scooter"]', timeout=10_000)
        page.wait_for_timeout(500)
        print("Form 2 visible ✓")

        # Date
        target = date.today() + timedelta(days=1)
        page.locator('input[placeholder="* When to deliver the scooter"]').click()
        page.wait_for_selector('.react-datepicker', timeout=5_000)
        day_str = str(target.day)
        for _ in range(3):
            month = page.text_content('.react-datepicker__current-month') or ""
            if target.strftime("%B %Y").lower() in month.lower():
                break
            page.click('.react-datepicker__navigation--next')
            page.wait_for_timeout(300)
        page.click(f'.react-datepicker__day:not(.react-datepicker__day--outside-month):has-text("{day_str}")')
        page.click('body')
        page.wait_for_timeout(400)
        date_val = page.locator('input[placeholder="* When to deliver the scooter"]').input_value()
        print(f"Date value in field: '{date_val}'")

        # Period
        page.locator('.Dropdown-control').first.click()
        page.wait_for_selector('.Dropdown-option', timeout=3_000)
        page.locator('.Dropdown-option:has-text("a day")').click()
        page.wait_for_timeout(400)

        # List ALL buttons on page before submit
        btns = page.locator('button').all()
        print(f"\n=== Buttons BEFORE submit ({len(btns)}) ===")
        for i, b in enumerate(btns):
            try:
                print(f"  [{i}] text='{b.inner_text().strip()}' visible={b.is_visible()} disabled={b.is_disabled()}")
            except Exception as e:
                print(f"  [{i}] error: {e}")

        # Click Order button
        print("\nClicking 'Order' button (form submit)...")
        # Try via evaluate to click the LAST Order button (the form submit one)
        page.evaluate("""
            const btns = Array.from(document.querySelectorAll('button'));
            const orderBtns = btns.filter(b => b.innerText.trim() === 'Order');
            console.log('Order buttons found:', orderBtns.length);
            orderBtns.forEach((b, i) => {
                console.log('  orderBtn[' + i + ']:', b.outerHTML.substring(0, 200));
            });
        """)
        page.wait_for_timeout(300)

        # Click the last Order button (should be the form submit)
        order_btns = page.locator('button:has-text("Order")')
        cnt = order_btns.count()
        print(f"'Order' buttons count: {cnt}")
        for i in range(cnt):
            try:
                b = order_btns.nth(i)
                print(f"  [{i}] visible={b.is_visible()} text='{b.inner_text().strip()}'")
            except Exception as e:
                print(f"  [{i}] error: {e}")

        # Click the last one
        order_btns.last.click()
        page.wait_for_timeout(3000)

        # Check what appeared
        print("\n=== State after click ===")
        print(f"URL: {page.url}")

        # Check for dialogs/modals/popups
        modal_sels = [
            '[class*="Modal"]',
            '[role="dialog"]',
            '.Order_Modal__YZ-d3',
            '[class*="modal"]',
            '[class*="popup"]',
            '[class*="Popup"]',
        ]
        for sel in modal_sels:
            try:
                count = page.locator(sel).count()
                if count > 0:
                    for i in range(min(count, 3)):
                        el = page.locator(sel).nth(i)
                        print(f"  MODAL '{sel}'[{i}]: visible={el.is_visible()} text='{el.inner_text()[:100]}'")
            except Exception as e:
                print(f"  sel '{sel}' error: {e}")

        # Check all visible dialogs
        all_divs = page.evaluate("""
            Array.from(document.querySelectorAll('[class*="Modal"],[class*="modal"],[role="dialog"]'))
                .map(el => ({tag: el.tagName, cls: el.className, text: el.innerText.substring(0,100), vis: el.offsetParent !== null}))
        """)
        print(f"\nAll modal-like elements: {all_divs}")

        # Wait for user to inspect
        print("\nWaiting 5s for inspection...")
        page.wait_for_timeout(5000)

        # Try clicking YES if there's a confirmation dialog
        yes_btns = page.locator('button:has-text("Yes")')
        if yes_btns.count() > 0:
            print(f"Found {yes_btns.count()} 'Yes' button(s)! Clicking...")
            yes_btns.first.click()
            page.wait_for_timeout(3000)
            # Re-check modal
            for sel in modal_sels:
                try:
                    count = page.locator(sel).count()
                    if count > 0:
                        for i in range(min(count, 3)):
                            el = page.locator(sel).nth(i)
                            print(f"  AFTER YES - MODAL '{sel}'[{i}]: visible={el.is_visible()} text='{el.inner_text()[:100]}'")
                except Exception:
                    pass

        browser.close()
        print("Done.")

if __name__ == "__main__":
    main()
