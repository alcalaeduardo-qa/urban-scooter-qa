"""
tests/test_tarea_2_validacion_datos.py
======================================
Validación de datos del formulario "Realizar pedido" – Tarea 2.
Cubre 39 casos de prueba (IDs 1-40, omitiendo ID 18 – eliminado por el usuario).

Convenciones:
  • Cada test corresponde a exactamente una fila del Excel.
  • Status se escribe en la columna H (status_col=7 → col 7+1=8) del Excel.
  • Enlace Jira en columna I  (jira_col=8   → col 8+1=9).
  • Si el sistema se comporta como requiere el criterio → APROBADO.
  • Si falla (bug) o la aserción falla → NO APROBADO.

Selectores confirmados con el análisis DOM ejecutado en Opera el 13/04/2026.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from components.web.pages import HomePage, OrderFormPage
from config import settings
from models.test_entities import Status
from utils.logger import get_logger
from utils.screenshot_manager import ScreenshotManager

log = get_logger("test_validacion_t2")
_sm = ScreenshotManager("tarea_2_validacion")

# ─── Browser context (set by parametrized order_form fixture) ──────────────────
_browser_ctx: dict = {"name": "opera"}

# ─── Configuración Excel ────────────────────────────────────────────────────────
# write_status usa (col + 1) internamente, así que:
#   _OPERA_COL=7  → escribe en columna 8  (H) ✓
#   _CHROME_COL=8 → escribe en columna 9  (I) ✓
#   _JIRA_COL=9   → escribe en columna 10 (J) ✓
_OPERA_COL  = 7
_CHROME_COL = 8
_JIRA_COL   = 9


def _row(test_id: int) -> int:
    """Excel row para el test ID indicado (fila 1 = cabecera, ID n → fila n+1)."""
    return test_id + 1


# ─── Valores válidos por defecto ────────────────────────────────────────────────
_FN    = "Juan"              # first name  (2-16 chars, letras latinas/espacio/guion)
_LN    = "Perez"             # last name
_ADDR  = "Calle Falsa 123"  # address     (5-50 chars)
_PHONE = "12345678901"       # phone       (11 dígitos – válido según sistema actual)

# ─── Selectores confirmados (análisis DOM 13/04/2026) ──────────────────────────
_SEL = {
    # Formulario 1
    "fn":           'input[placeholder="* First name"]',
    "ln":           'input[placeholder="* Last name"]',
    "addr":         'input[placeholder="* Address: where to bring the scooter"]',
    "metro":        'input[placeholder="* Subway station"]',
    "phone":        'input[placeholder="* Phone: the courier will call you"]',
    "next":         'button:has-text("Next")',
    "back":         'button:has-text("Back")',
    # Metro dropdown
    "metro_opt":    '.select-search__option',         # BUTTON tags en UL
    "metro_err":    '.Order_MetroError__1BtZb',       # "Choose the station"
    # Mensajes de error visibles (tienen clase Input_Visible___syz6)
    "err_visible":  '.Input_ErrorMessage__3HvIb.Input_Visible___syz6',
    # Formulario 2
    "date":         'input[placeholder="* When to deliver the scooter"]',
    "period":       '.Dropdown-control',
    "period_opt":   '.Dropdown-option',
    "comment":      'input[placeholder="Comment"]',
    # Modal de confirmación
    "modal":        '[class*="Modal"]',
}

# Clase CSS que indica campo con error
_ERR_CLS    = "Input_Error__1Tx5d"
# Clase CSS que indica campo con valor (relleno)
_FILLED_CLS = "Input_Filled__1rDxs"

# Mensajes de error esperados según REQUISITOS (usados en prueba ID 39)
# Nota: los marcados BUG son mensajes que el sistema actual NO muestra correctamente.
_EMSG = {
    "fn":    "Enter a valid name",           # sistema muestra esto ✓
    "ln":    "Enter a valid last name",      # BUG: sistema muestra "Enter a valid name"
    "addr":  "Enter a valid address",        # BUG: sistema no muestra mensaje
    "phone": "Enter a valid phone number",   # BUG: sistema muestra "Enter a valid number"
    "metro": "Choose the station",           # sistema muestra esto ✓
}


# ─── Helpers internos ───────────────────────────────────────────────────────────

def _goto_form1(page) -> None:
    """Navegar a la home y hacer clic en 'Order' para llegar al formulario 1."""
    home = HomePage(page)
    home.goto()
    home.click_order_button()
    page.wait_for_selector(_SEL["fn"], state="visible", timeout=10_000)
    page.wait_for_timeout(400)


def _select_metro_first_option(page) -> None:
    """Hacer clic en metro y seleccionar la primera opción del dropdown ('1st Street')."""
    page.locator(_SEL["metro"]).click()
    page.wait_for_timeout(900)
    page.locator(_SEL["metro_opt"]).first.click()
    page.wait_for_timeout(400)


def _fill1(page, fn=_FN, ln=_LN, addr=_ADDR, phone=_PHONE, metro: bool = True) -> None:
    """
    Rellenar formulario 1 con los valores indicados.
    Pasar None en cualquier campo para omitirlo.
    metro=False omite la selección del metro.
    """
    if fn    is not None: page.fill(_SEL["fn"],    fn)
    if ln    is not None: page.fill(_SEL["ln"],    ln)
    if addr  is not None: page.fill(_SEL["addr"],  addr)
    if phone is not None: page.fill(_SEL["phone"], phone)
    if metro:
        _select_metro_first_option(page)


def _click_next(page) -> None:
    page.locator(_SEL["next"]).click()
    page.wait_for_timeout(1_000)


def _form2_visible(page, timeout: int = 2_500) -> bool:
    """True si el formulario 2 es visible (campo de fecha visible)."""
    try:
        page.wait_for_selector(_SEL["date"], state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def _has_err_cls(page, field_sel: str) -> bool:
    """True si el campo indicado tiene la clase de error CSS."""
    try:
        cls = page.locator(field_sel).first.get_attribute("class") or ""
        return _ERR_CLS in cls
    except Exception:
        return False


def _err_msg_visible(page, text: str, timeout: int = 1_500) -> bool:
    """True si hay un mensaje de error visible con el texto exacto indicado."""
    try:
        loc = page.locator(f'{_SEL["err_visible"]}:has-text("{text}")')
        return loc.count() > 0 and loc.first.is_visible(timeout=timeout)
    except Exception:
        return False


def _metro_err_visible(page) -> bool:
    """True si se muestra el error de metro 'Choose the station'."""
    try:
        return page.locator(_SEL["metro_err"]).is_visible(timeout=1_500)
    except Exception:
        return False


def _advance_to_form2(page) -> None:
    """Rellenar form 1 con datos válidos y avanzar al form 2. Lanza excepción si falla."""
    _fill1(page)
    _click_next(page)
    page.wait_for_selector(_SEL["date"], state="visible", timeout=10_000)
    page.wait_for_timeout(400)


def _select_date(page, days: int = 1) -> None:
    """Abrir calendario y seleccionar una fecha futura."""
    OrderFormPage(page).select_delivery_date(days)


def _select_period(page, days: int = 1) -> None:
    """Seleccionar periodo de alquiler en el dropdown."""
    periods = ["a day", "two days", "three days", "four days",
               "five days", "six days", "seven days"]
    text = periods[days - 1]
    page.locator(_SEL["period"]).first.click()
    page.wait_for_selector(_SEL["period_opt"], state="visible", timeout=3_000)
    page.locator(f'{_SEL["period_opt"]}:has-text("{text}")').click()
    page.wait_for_timeout(400)


def _click_order(page) -> None:
    """
    Hacer clic en el botón Order del formulario 2 y confirmar el pedido.
    Flujo real:
      1. Hay 3 botones con texto 'Order': [0]=Home 'Order', [1]='Order status', [2]=Form submit.
         El botón del formulario 2 es el ÚLTIMO (.last).
      2. Aparece modal de confirmación: "Would you like to make the order? No / Yes"
      3. Hay que hacer click en 'Yes' para completar el pedido.
    """
    page.locator('button:has-text("Order")').last.click()
    page.wait_for_timeout(1_500)
    # Diálogo de confirmación intermedio → click 'Yes'
    try:
        yes_btn = page.locator('button:has-text("Yes")')
        yes_btn.wait_for(state="visible", timeout=5_000)
        yes_btn.click()
        page.wait_for_timeout(1_000)
    except Exception:
        pass  # Si no aparece el diálogo, continuar (no bloquear)


def _modal_visible(page, timeout: int = 10_000) -> bool:
    """True si el modal de ÉXITO del pedido aparece (contiene 'Order number' o 'order has been made')."""
    try:
        # Esperar que el DOM muestre el modal de éxito con el número de pedido
        page.wait_for_function(
            """() => {
                const els = document.querySelectorAll('[class*="Modal"]');
                return Array.from(els).some(el =>
                    el.innerText.includes('Order number') ||
                    el.innerText.toLowerCase().includes('order has been made')
                );
            }""",
            timeout=timeout,
        )
        return True
    except Exception:
        return False


def _fail_screenshot(page, test_id: int) -> str:
    """
    Captura una screenshot del estado actual del navegador cuando un test falla.
    Retorna la ruta del archivo o cadena vacía si falla la captura.
    """
    try:
        path = _sm.capture_playwright(page, f"test_id_{test_id:02d}_no_aprobado")
        log.info("[screenshot] Evidencia guardada: %s", path)
        return path
    except Exception as exc:
        log.warning("[screenshot] No se pudo capturar test_id=%d: %s", test_id, exc)
        return ""


def _write_excel(excel, test_id: int, status: Status, error: str = "") -> None:
    """Escribir resultado en la fila correspondiente del Excel."""
    col = _OPERA_COL if _browser_ctx.get("name", "opera") == "opera" else _CHROME_COL
    try:
        excel.write_status(
            row_index=_row(test_id),
            status=status,
            status_col=col,
            jira_col=_JIRA_COL,
            error_message=error[:250] if error else "",
            screenshot_path="",
        )
        excel.save()
    except Exception as exc:
        log.warning("[excel] No se pudo escribir test_id=%d: %s", test_id, exc)


# ─── Fixture ────────────────────────────────────────────────────────────────────

@pytest.fixture(params=["opera", "chrome"])
def order_form(request, browser_context, chrome_browser_context):
    """Navegar al formulario de pedido (form 1) en Opera y Chrome."""
    _browser_ctx["name"] = request.param
    ctx = browser_context if request.param == "opera" else chrome_browser_context
    pg = ctx.new_page()
    pg.goto(settings.server.base_url, wait_until="networkidle")
    _goto_form1(pg)
    yield pg
    pg.close()


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: NOMBRE  (IDs 1–5)
# ══════════════════════════════════════════════════════════════════════════════

class TestNombre:
    """Validación del campo 'Nombre' – IDs 1 al 5."""

    def test_id_01_limite_inferior_invalido(self, order_form, excel_t2_validation):
        """ID 1 – Nombre con 1 carácter (inválido): el sistema debe bloquear el avance."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, fn="B")
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con nombre de 1 carácter (debería bloquearse)"
            assert _has_err_cls(page, _SEL["fn"]), \
                "El campo 'nombre' no muestra clase de error visual"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 1); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 1); raise
        finally:
            _write_excel(excel_t2_validation, 1, st, err)

    def test_id_02_limite_inferior_valido(self, order_form, excel_t2_validation):
        """ID 2 – Nombre con 2 caracteres (válido – límite inferior): debe avanzar."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, fn="Lu")
            _click_next(page)
            assert _form2_visible(page), \
                "El formulario NO avanzó con nombre de 2 caracteres (debería ser válido)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 2); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 2); raise
        finally:
            _write_excel(excel_t2_validation, 2, st, err)

    def test_id_03_limite_superior_valido(self, order_form, excel_t2_validation):
        """ID 3 – Nombre con 15 caracteres (válido – límite superior): debe avanzar."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, fn="Roberto-Garcias")  # 15 chars exactos
            _click_next(page)
            assert _form2_visible(page), \
                "El formulario NO avanzó con nombre de 15 caracteres (debería ser válido)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 3); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 3); raise
        finally:
            _write_excel(excel_t2_validation, 3, st, err)

    def test_id_04_limite_superior_invalido(self, order_form, excel_t2_validation):
        """ID 4 – Nombre con 16 caracteres (inválido – supera límite): debe bloquear."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, fn="Roberto-Garciasz")  # 16 chars
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con nombre de 16 caracteres (debería bloquearse)"
            assert _has_err_cls(page, _SEL["fn"]), \
                "El campo 'nombre' no muestra error visual con 16 caracteres"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 4); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 4); raise
        finally:
            _write_excel(excel_t2_validation, 4, st, err)

    def test_id_05_caracteres(self, order_form, excel_t2_validation):
        """ID 5 – Nombre con caracteres inválidos (números) debe rechazarse."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, fn="Ana123")  # dígitos en el nombre → inválido
            _click_next(page)
            assert not _form2_visible(page), \
                "Nombre 'Ana123' avanzó al formulario 2 (BUG: debe rechazarse)"
            assert _has_err_cls(page, _SEL["fn"]), \
                "El campo 'nombre' no muestra error con caracteres inválidos"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 5); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 5); raise
        finally:
            _write_excel(excel_t2_validation, 5, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: APELLIDO  (IDs 6–9)
# ══════════════════════════════════════════════════════════════════════════════

class TestApellido:
    """Validación del campo 'Apellido' – IDs 6 al 9."""

    def test_id_06_limite_inferior_invalido(self, order_form, excel_t2_validation):
        """ID 6 – Apellido con 1 carácter (inválido): debe bloquear el avance."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, ln="K")
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con apellido de 1 carácter"
            assert _has_err_cls(page, _SEL["ln"]), \
                "El campo 'apellido' no muestra clase de error"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 6); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 6); raise
        finally:
            _write_excel(excel_t2_validation, 6, st, err)

    def test_id_07_limite_inferior_valido(self, order_form, excel_t2_validation):
        """ID 7 – Apellido con 2 caracteres (válido – límite inferior): debe avanzar."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, ln="Vi")
            _click_next(page)
            assert _form2_visible(page), \
                "El formulario NO avanzó con apellido de 2 caracteres"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 7); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 7); raise
        finally:
            _write_excel(excel_t2_validation, 7, st, err)

    def test_id_08_limite_superior_valido(self, order_form, excel_t2_validation):
        """ID 8 – Apellido con 15 caracteres (válido – límite superior): debe avanzar."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, ln="Gutierrez-Vegas")  # 15 chars exactos
            _click_next(page)
            assert _form2_visible(page), \
                "El formulario NO avanzó con apellido de 15 caracteres"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 8); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 8); raise
        finally:
            _write_excel(excel_t2_validation, 8, st, err)

    def test_id_09_limite_superior_invalido(self, order_form, excel_t2_validation):
        """ID 9 – Apellido con 16 caracteres (inválido – supera límite): debe bloquear."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, ln="Gutierrez-Vegasb")  # 16 chars
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con apellido de 16 caracteres"
            assert _has_err_cls(page, _SEL["ln"]), \
                "El campo 'apellido' no muestra error con 16 caracteres"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 9); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 9); raise
        finally:
            _write_excel(excel_t2_validation, 9, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: DIRECCIÓN  (IDs 10–14)
# ══════════════════════════════════════════════════════════════════════════════

class TestDireccion:
    """Validación del campo 'Dirección' – IDs 10 al 14."""

    def test_id_10_limite_inferior_invalido(self, order_form, excel_t2_validation):
        """ID 10 – Dirección con 4 caracteres (inválido): debe bloquear el avance."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, addr="Cll1")  # 4 chars
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con dirección de 4 caracteres"
            assert _has_err_cls(page, _SEL["addr"]), \
                "El campo 'dirección' no muestra clase de error con 4 chars"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 10); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 10); raise
        finally:
            _write_excel(excel_t2_validation, 10, st, err)

    def test_id_11_limite_inferior_valido(self, order_form, excel_t2_validation):
        """ID 11 – Dirección con 5 caracteres (válido – límite inferior): debe avanzar."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, addr="Av. 5")  # 5 chars exactos
            _click_next(page)
            assert _form2_visible(page), \
                "El formulario NO avanzó con dirección de 5 caracteres"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 11); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 11); raise
        finally:
            _write_excel(excel_t2_validation, 11, st, err)

    def test_id_12_limite_superior_valido(self, order_form, excel_t2_validation):
        """ID 12 – Dirección con 50 caracteres (válido – límite superior): debe avanzar."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            addr_50 = "Avenida Principal 1234 Colonia Centro Norte Blvd 5"  # 50 chars sin comas
            _fill1(page, addr=addr_50)
            _click_next(page)
            assert _form2_visible(page), \
                "El formulario NO avanzó con dirección de 50 caracteres"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 12); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 12); raise
        finally:
            _write_excel(excel_t2_validation, 12, st, err)

    def test_id_13_trim_espacios(self, order_form, excel_t2_validation):
        """ID 13 – Espacios al inicio/fin de la dirección deben eliminarse al perder el foco."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            addr_inp = page.locator(_SEL["addr"])
            addr_inp.fill("   Main St 123   ")
            # Pasar el foco a otro campo para activar el trim
            page.locator(_SEL["fn"]).click()
            page.wait_for_timeout(600)
            val = addr_inp.input_value()
            assert val == val.strip(), \
                f"El campo no eliminó los espacios al inicio/fin. Valor actual: '{val}'"
            assert "Main St 123" in val, \
                f"El contenido cambió de forma inesperada: '{val}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 13); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 13); raise
        finally:
            _write_excel(excel_t2_validation, 13, st, err)

    def test_id_14_caracteres_invalidos(self, order_form, excel_t2_validation):
        """ID 14 – Dirección con caracteres inválidos (emoji) debe rechazarse."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, addr="Main St \U0001F47E")  # emoji en la dirección
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con emoji en la dirección (BUG: debe rechazarse)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 14); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 14); raise
        finally:
            _write_excel(excel_t2_validation, 14, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: ESTACIÓN DE METRO  (IDs 15–17 | ID 18 eliminado)
# ══════════════════════════════════════════════════════════════════════════════

class TestMetro:
    """Validación del campo 'Estación de Metro' – IDs 15, 16, 17 (ID 18 eliminado)."""

    def test_id_15_seleccion_valida(self, order_form, excel_t2_validation):
        """ID 15 – Selección válida desde el dropdown debe permitir el avance."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page)  # incluye selección de metro ✓
            _click_next(page)
            assert _form2_visible(page), \
                "El formulario no avanzó con metro válido seleccionado"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 15); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 15); raise
        finally:
            _write_excel(excel_t2_validation, 15, st, err)

    def test_id_16_valor_inexistente(self, order_form, excel_t2_validation):
        """ID 16 – Texto libre no seleccionado del dropdown debe bloquear el avance."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, metro=False)
            # Escribir texto que no existe y cerrar el dropdown sin seleccionar
            page.fill(_SEL["metro"], "Estacion XYZ Imaginaria")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con metro de texto libre (sin selección del dropdown)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 16); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 16); raise
        finally:
            _write_excel(excel_t2_validation, 16, st, err)

    def test_id_17_campo_vacio(self, order_form, excel_t2_validation):
        """ID 17 – Campo metro vacío debe bloquear el avance y mostrar mensaje de error."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, metro=False)  # no se selecciona metro
            _click_next(page)
            assert not _form2_visible(page), \
                "El formulario avanzó con el campo metro vacío"
            assert _metro_err_visible(page), \
                f"No se muestra el error de metro ('{_EMSG['metro']}')"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 17); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 17); raise
        finally:
            _write_excel(excel_t2_validation, 17, st, err)

    # ID 18 – Fallo de catálogo de metro → ELIMINADO por solicitud del usuario.


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: TELÉFONO  (IDs 19–23)
# ══════════════════════════════════════════════════════════════════════════════

class TestTelefono:
    """Validación del campo 'Teléfono' – IDs 19 al 23."""

    def test_id_19_valido_numerico(self, order_form, excel_t2_validation):
        """
        ID 19 – Teléfono de 10 dígitos (válido según requisito: 10-12 chars).
        BUG conocido: el sistema lo rechaza; el test fallará → NO APROBADO.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, phone="1234567890")  # 10 dígitos – válido por requisito
            _click_next(page)
            assert _form2_visible(page), \
                "Teléfono de 10 dígitos fue rechazado (BUG: requisito indica 10-12 válido)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 19); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 19); raise
        finally:
            _write_excel(excel_t2_validation, 19, st, err)

    def test_id_20_menor_al_minimo(self, order_form, excel_t2_validation):
        """ID 20 – Teléfono de 9 dígitos (menos del mínimo): debe rechazarse."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, phone="123456789")  # 9 dígitos
            _click_next(page)
            assert not _form2_visible(page), \
                "Teléfono de 9 dígitos avanzó (debería ser inválido)"
            assert _has_err_cls(page, _SEL["phone"]), \
                "El campo 'teléfono' no muestra error con 9 dígitos"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 20); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 20); raise
        finally:
            _write_excel(excel_t2_validation, 20, st, err)

    def test_id_21_mayor_al_maximo(self, order_form, excel_t2_validation):
        """
        ID 21 – Teléfono de 13 dígitos (mayor al máximo de 12): debe rechazarse.
        BUG conocido: el sistema lo acepta; el test fallará → NO APROBADO.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, phone="1234567890123")  # 13 dígitos
            _click_next(page)
            assert not _form2_visible(page), \
                "Teléfono de 13 dígitos avanzó (BUG: debe rechazarse, máximo 12)"
            assert _has_err_cls(page, _SEL["phone"]), \
                "El campo 'teléfono' no muestra error con 13 dígitos"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 21); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 21); raise
        finally:
            _write_excel(excel_t2_validation, 21, st, err)

    def test_id_22_caracteres_invalidos(self, order_form, excel_t2_validation):
        """ID 22 – Teléfono con guiones/paréntesis debe rechazarse."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, phone="123-456-7890")  # guiones → inválido
            _click_next(page)
            assert not _form2_visible(page), \
                "Teléfono con guiones avanzó (debería ser inválido)"
            assert _has_err_cls(page, _SEL["phone"]), \
                "El campo 'teléfono' no muestra error con guiones"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 22); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 22); raise
        finally:
            _write_excel(excel_t2_validation, 22, st, err)

    def test_id_23_plus_posicion_interna(self, order_form, excel_t2_validation):
        """ID 23 – Símbolo '+' en posición interna debe rechazarse."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page, phone="123+45678901")  # '+' en posición interna
            _click_next(page)
            assert not _form2_visible(page), \
                "Teléfono con '+' interno avanzó (debería ser inválido)"
            assert _has_err_cls(page, _SEL["phone"]), \
                "El campo 'teléfono' no muestra error con '+' interno"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 23); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 23); raise
        finally:
            _write_excel(excel_t2_validation, 23, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: FECHA DE ENTREGA  (IDs 24–27)
# ══════════════════════════════════════════════════════════════════════════════

class TestFechaEntrega:
    """Validación del campo 'Fecha de entrega' – IDs 24 al 27."""

    def test_id_24_fecha_valida_futura(self, order_form, excel_t2_validation):
        """ID 24 – Seleccionar una fecha futura debe guardarse correctamente en el campo."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _advance_to_form2(page)
            tomorrow = date.today() + timedelta(days=1)
            _select_date(page, days=1)
            val = page.locator(_SEL["date"]).input_value()
            assert val, "El campo fecha quedó vacío tras selección en el calendario"
            # Formato confirmado: DD.MM.YYYY
            day_str = str(tomorrow.day)
            assert day_str in val, \
                f"El día seleccionado ({day_str}) no aparece en el valor del campo: '{val}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 24); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 24); raise
        finally:
            _write_excel(excel_t2_validation, 24, st, err)

    def test_id_25_fecha_hoy_no_permitida(self, order_form, excel_t2_validation):
        """
        ID 25 – El día de hoy debe estar deshabilitado en el calendario.
        BUG conocido: el calendario NO deshabilita hoy → NO APROBADO.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _advance_to_form2(page)
            page.locator(_SEL["date"]).click()
            page.wait_for_selector('.react-datepicker', state="visible", timeout=5_000)
            page.wait_for_timeout(500)

            # Navegar al mes actual si el calendario muestra otro mes
            today_cell = page.locator('.react-datepicker__day--today')
            if today_cell.count() == 0:
                for _ in range(12):  # máximo 12 meses hacia atrás
                    prev = page.locator('.react-datepicker__navigation--previous')
                    if prev.is_visible(timeout=1_000):
                        prev.click()
                        page.wait_for_timeout(300)
                        if page.locator('.react-datepicker__day--today').count() > 0:
                            break

            today_cls = page.locator('.react-datepicker__day--today').first.get_attribute("class") or ""
            assert "disabled" in today_cls, \
                f"BUG: el día de hoy NO está deshabilitado. Clase actual: '{today_cls}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 25); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 25); raise
        finally:
            _write_excel(excel_t2_validation, 25, st, err)

    def test_id_26_entrada_manual_bloqueada(self, order_form, excel_t2_validation):
        """
        ID 26 – La escritura manual en el campo fecha debe estar bloqueada.
        BUG conocido: el campo acepta texto manual → NO APROBADO.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _advance_to_form2(page)
            date_inp = page.locator(_SEL["date"])
            # Intentar escribir manualmente una fecha
            date_inp.fill("2099-12-31")
            page.locator("body").click()
            page.wait_for_timeout(600)
            val = date_inp.input_value()
            assert val != "2099-12-31", \
                f"BUG: la entrada manual fue aceptada en el campo fecha. Valor: '{val}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 26); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 26); raise
        finally:
            _write_excel(excel_t2_validation, 26, st, err)

    def test_id_27_cambio_fecha_resaltada(self, order_form, excel_t2_validation):
        """ID 27 – Al seleccionar una fecha, el campo debe resaltarse (clase 'Filled')."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _advance_to_form2(page)
            date_inp = page.locator(_SEL["date"])
            cls_before = date_inp.get_attribute("class") or ""
            assert _FILLED_CLS not in cls_before, \
                "El campo fecha ya tenía la clase Filled antes de seleccionar"
            _select_date(page, days=2)
            cls_after = date_inp.get_attribute("class") or ""
            assert _FILLED_CLS in cls_after, \
                f"El campo fecha no se resaltó tras selección. Clase: '{cls_after}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 27); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 27); raise
        finally:
            _write_excel(excel_t2_validation, 27, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: PERÍODO DE ALQUILER  (IDs 28–30)
# ══════════════════════════════════════════════════════════════════════════════

class TestPeriodoAlquiler:
    """Validación del campo 'Período de alquiler' – IDs 28 al 30."""

    def test_id_28_valor_valido(self, order_form, excel_t2_validation):
        """ID 28 – Seleccionar 1, 3 y 7 días debe mostrar el texto correcto."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _advance_to_form2(page)
            _select_date(page, days=1)
            expected = {1: "a day", 3: "three days", 7: "seven days"}
            for days, text in expected.items():
                ctrl = page.locator(_SEL["period"]).first
                ctrl.click()
                page.wait_for_selector(_SEL["period_opt"], state="visible", timeout=3_000)
                page.locator(f'{_SEL["period_opt"]}:has-text("{text}")').click()
                page.wait_for_timeout(350)
                ctrl_text = ctrl.inner_text().strip()
                assert text in ctrl_text, \
                    f"Período de {days} día(s): texto incorrecto en control: '{ctrl_text}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 28); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 28); raise
        finally:
            _write_excel(excel_t2_validation, 28, st, err)

    def test_id_29_fuera_de_rango(self, order_form, excel_t2_validation):
        """ID 29 – El dropdown no debe contener opciones para 0 u 8 días."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _advance_to_form2(page)
            page.locator(_SEL["period"]).first.click()
            page.wait_for_selector(_SEL["period_opt"], state="visible", timeout=3_000)
            options = [o.strip().lower() for o in page.locator(_SEL["period_opt"]).all_text_contents()]
            out_of_range = {"zero days", "0 days", "eight days", "8 days"}
            found = out_of_range & set(options)
            assert not found, \
                f"El dropdown contiene opciones fuera de rango: {found}"
            assert len(options) == 7, \
                f"El dropdown tiene {len(options)} opciones; se esperan exactamente 7 (1-7 días)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 29); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 29); raise
        finally:
            _write_excel(excel_t2_validation, 29, st, err)

    def test_id_30_campo_sin_seleccion(self, order_form, excel_t2_validation):
        """
        ID 30 – El campo de período siempre tiene valor por defecto ('a day');
        sin selección explícita el pedido debe crearse correctamente.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _advance_to_form2(page)
            _select_date(page, days=1)
            # Verificar que hay un valor por defecto antes de tocar el dropdown
            default_text = page.locator(_SEL["period"]).first.inner_text().strip()
            assert default_text, \
                "El campo período no tiene valor por defecto antes de selección"
            # Enviar pedido sin cambiar el período (usando el default)
            _click_order(page)
            assert _modal_visible(page), \
                "No apareció modal de confirmación con período por defecto"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 30); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 30); raise
        finally:
            _write_excel(excel_t2_validation, 30, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: COLOR  (IDs 31–33)
# ══════════════════════════════════════════════════════════════════════════════

class TestColor:
    """Validación del campo 'Color' – IDs 31 al 33."""

    def _prep_form2(self, page) -> None:
        """Avanzar al formulario 2 con fecha y período válidos."""
        _advance_to_form2(page)
        _select_date(page, days=1)
        _select_period(page, days=1)

    def test_id_31_sin_seleccion(self, order_form, excel_t2_validation):
        """ID 31 – Color es opcional: sin selección el pedido debe crearse."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            self._prep_form2(page)
            # No se selecciona ningún color
            _click_order(page)
            assert _modal_visible(page), \
                "No apareció modal de éxito sin seleccionar color (debería ser opcional)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 31); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 31); raise
        finally:
            _write_excel(excel_t2_validation, 31, st, err)

    def test_id_32_seleccion_simple(self, order_form, excel_t2_validation):
        """ID 32 – Seleccionar un color (negro) debe permitir crear el pedido."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            self._prep_form2(page)
            page.check("#black")
            _click_order(page)
            assert _modal_visible(page), \
                "No apareció modal de éxito con color negro seleccionado"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 32); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 32); raise
        finally:
            _write_excel(excel_t2_validation, 32, st, err)

    def test_id_33_seleccion_multiple(self, order_form, excel_t2_validation):
        """ID 33 – Seleccionar ambos colores debe permitir crear el pedido."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            self._prep_form2(page)
            page.check("#black")
            page.check("#grey")
            _click_order(page)
            assert _modal_visible(page), \
                "No apareció modal de éxito con ambos colores seleccionados"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 33); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 33); raise
        finally:
            _write_excel(excel_t2_validation, 33, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPO: COMENTARIO  (IDs 34–37)
# ══════════════════════════════════════════════════════════════════════════════

class TestComentario:
    """Validación del campo 'Comentario' – IDs 34 al 37."""

    def _prep_form2(self, page) -> None:
        _advance_to_form2(page)
        _select_date(page, days=1)
        _select_period(page, days=1)

    def test_id_34_valido_caracteres_permitidos(self, order_form, excel_t2_validation):
        """ID 34 – Comentario con caracteres válidos debe permitir el pedido."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            self._prep_form2(page)
            page.fill(_SEL["comment"], "Llamar antes, pto. 2")
            _click_order(page)
            assert _modal_visible(page), \
                "No apareció modal con comentario válido"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 34); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 34); raise
        finally:
            _write_excel(excel_t2_validation, 34, st, err)

    def test_id_35_excede_maximo(self, order_form, excel_t2_validation):
        """
        ID 35 – Comentario con más de 24 caracteres debe rechazarse.
        BUG probable: el campo no tiene maxlength → el sistema puede aceptarlo → NO APROBADO.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            self._prep_form2(page)
            # 25 caracteres – supera el máximo de 24
            page.fill(_SEL["comment"], "no llamar, nino dormido!")
            _click_order(page)
            modal_shown = _modal_visible(page, timeout=4_000)
            assert not modal_shown, \
                "BUG: El pedido se creó con comentario de 25 chars (supera el máximo de 24)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 35); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 35); raise
        finally:
            _write_excel(excel_t2_validation, 35, st, err)

    def test_id_36_caracteres_invalidos(self, order_form, excel_t2_validation):
        """
        ID 36 – Comentario con caracteres inválidos (emoji) debe rechazarse.
        BUG probable: el campo no valida charset → puede aceptarse → NO APROBADO.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            self._prep_form2(page)
            page.fill(_SEL["comment"], "Llegare pronto \U0001F47E")  # emoji
            _click_order(page)
            modal_shown = _modal_visible(page, timeout=4_000)
            assert not modal_shown, \
                "BUG: El pedido se creó con emoji en el comentario (debe rechazarse)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 36); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 36); raise
        finally:
            _write_excel(excel_t2_validation, 36, st, err)

    def test_id_37_vacio_permitido(self, order_form, excel_t2_validation):
        """ID 37 – Comentario vacío es permitido (campo opcional)."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            self._prep_form2(page)
            page.fill(_SEL["comment"], "")
            _click_order(page)
            assert _modal_visible(page), \
                "No apareció modal de éxito con comentario vacío (campo es opcional)"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 37); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 37); raise
        finally:
            _write_excel(excel_t2_validation, 37, st, err)


# ══════════════════════════════════════════════════════════════════════════════
# FLUJO GENERAL  (IDs 38–40)
# ══════════════════════════════════════════════════════════════════════════════

class TestFlujoGeneral:
    """Validación de flujo general – IDs 38 al 40."""

    def test_id_38_persistencia_al_atras(self, order_form, excel_t2_validation):
        """ID 38 – Al volver al formulario 1 con 'Back', los datos deben conservarse."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            _fill1(page)
            _click_next(page)
            page.wait_for_selector(_SEL["date"], state="visible", timeout=10_000)
            # Volver al formulario 1
            page.locator(_SEL["back"]).click()
            page.wait_for_selector(_SEL["fn"], state="visible", timeout=5_000)
            page.wait_for_timeout(500)
            # Verificar que los datos se conservan
            fn_val    = page.locator(_SEL["fn"]).input_value()
            ln_val    = page.locator(_SEL["ln"]).input_value()
            addr_val  = page.locator(_SEL["addr"]).input_value()
            phone_val = page.locator(_SEL["phone"]).input_value()
            assert fn_val    == _FN,    f"Nombre no preservado: '{fn_val}'"
            assert ln_val    == _LN,    f"Apellido no preservado: '{ln_val}'"
            assert addr_val  == _ADDR,  f"Dirección no preservada: '{addr_val}'"
            assert phone_val == _PHONE, f"Teléfono no preservado: '{phone_val}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 38); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 38); raise
        finally:
            _write_excel(excel_t2_validation, 38, st, err)

    def test_id_39_mensajes_error_especificos(self, order_form, excel_t2_validation):
        """
        ID 39 – Cada campo debe mostrar su propio mensaje de error específico.
        BUGs: apellido y teléfono muestran mensajes genéricos → NO APROBADO.
        """
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        failures = []
        try:
            # Sub-test 1: Nombre
            _fill1(page, fn="")
            _click_next(page)
            page.wait_for_timeout(600)
            if not _err_msg_visible(page, _EMSG["fn"]):
                failures.append(f"Nombre: no se ve '{_EMSG['fn']}'")
            # Recargar para el siguiente sub-test
            _goto_form1(page)

            # Sub-test 2: Apellido (BUG – sistema muestra "Enter a valid name")
            _fill1(page, ln="")
            _click_next(page)
            page.wait_for_timeout(600)
            if not _err_msg_visible(page, _EMSG["ln"]):
                failures.append(
                    f"Apellido: no se ve '{_EMSG['ln']}' "
                    f"(BUG: sistema muestra \"Enter a valid name\")"
                )
            _goto_form1(page)

            # Sub-test 3: Teléfono (BUG – sistema muestra "Enter a valid number")
            _fill1(page, phone="")
            _click_next(page)
            page.wait_for_timeout(600)
            if not _err_msg_visible(page, _EMSG["phone"]):
                failures.append(
                    f"Teléfono: no se ve '{_EMSG['phone']}' "
                    f"(BUG: sistema muestra \"Enter a valid number\")"
                )
            _goto_form1(page)

            # Sub-test 4: Metro
            _fill1(page, metro=False)
            _click_next(page)
            page.wait_for_timeout(600)
            if not _metro_err_visible(page):
                failures.append(f"Metro: no se ve '{_EMSG['metro']}'")

            assert not failures, (
                "Mensajes de error no específicos:\n" + "\n".join(f"  • {f}" for f in failures)
            )
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 39); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 39); raise
        finally:
            _write_excel(excel_t2_validation, 39, st, err)

    def test_id_40_envio_exitoso(self, order_form, excel_t2_validation):
        """ID 40 – Flujo completo con datos válidos debe generar número de pedido."""
        page = order_form
        st, err, shot = Status.NOT_APPROVED, "", ""
        try:
            # Formulario 1
            _fill1(page)
            _click_next(page)
            page.wait_for_selector(_SEL["date"], state="visible", timeout=10_000)
            # Formulario 2
            _select_date(page, days=1)
            _select_period(page, days=1)
            # Enviar
            _click_order(page)
            assert _modal_visible(page), \
                "No apareció el modal de éxito del pedido"
            # Obtener texto del modal de éxito (el que contiene 'Order number')
            modal_text = ""
            for el in page.locator('[class*="Modal"]').all():
                try:
                    txt = el.inner_text()
                    if "Order number" in txt or "order has been made" in txt.lower():
                        modal_text = txt
                        break
                except Exception:
                    pass
            track_match = re.search(r'Order number[:\s]+(\d+)', modal_text)
            assert track_match, \
                f"No se encontró 'Order number: XXXXX' en el modal. Texto: '{modal_text[:300]}'"
            st = Status.APPROVED
        except AssertionError as e:
            err = str(e); shot = _fail_screenshot(page, 40); raise
        except Exception as e:
            err = str(e); shot = _fail_screenshot(page, 40); raise
        finally:
            _write_excel(excel_t2_validation, 40, st, err)