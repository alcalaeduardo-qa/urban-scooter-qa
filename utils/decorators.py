from __future__ import annotations
import functools
import time
from typing import Any, Callable, Type, TypeVar

import pytest
import requests

from utils.logger import get_logger

log = get_logger("decorators")
F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    backoff: float = 1.0,
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        log.warning(
                            "[retry] %s — attempt %d/%d failed (%s). Retrying in %.1fs…",
                            func.__qualname__, attempt, max_attempts,
                            type(exc).__name__, current_delay,
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        log.error(
                            "[retry] %s — all %d attempts exhausted. Last error: %s",
                            func.__qualname__, max_attempts, exc,
                        )
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


def log_step(description: str = "") -> Callable[[F], F]:
    def decorator(func: F) -> F:
        label = description or func.__qualname__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log.info("▶  START  %s", label)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                log.info("✔  END    %s  (%.2fs)", label, elapsed)
                return result
            except Exception as exc:
                elapsed = time.perf_counter() - start
                log.error("✖  FAIL   %s  (%.2fs) — %s", label, elapsed, exc)
                raise
        return wrapper  # type: ignore[return-value]
    return decorator


def screenshot_on_fail(
    category: str = "general",
    page_kwarg: str = "page",
    driver_kwarg: str = "driver",
) -> Callable[[F], F]:
    """
    Captura una evidencia automáticamente cuando un test falla.

    Uso:
        @screenshot_on_fail("api")
        def test_api(): ...

        @screenshot_on_fail
        def test_web(): ...   # usa categoría "general"

    Si no hay objeto page ni driver, se genera una imagen de texto con el error.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                _capture_on_failure(
                    func_name=func.__qualname__,
                    exception=e,
                    args=args,
                    kwargs=kwargs,
                    category=_resolve_category(category, func),
                    page_kwarg=page_kwarg,
                    driver_kwarg=driver_kwarg,
                )
                raise
        return wrapper  # type: ignore[return-value]

    # Permitir uso sin paréntesis: @screenshot_on_fail
    if callable(category):
        func = category
        category = "general"
        return decorator(func)
    return decorator


def _resolve_category(category, func) -> str:
    if callable(category):
        return "general"
    return category


def _capture_on_failure(
    func_name: str,
    exception: Exception,
    args: tuple,
    kwargs: dict,
    category: str,
    page_kwarg: str,
    driver_kwarg: str,
) -> None:
    """Intenta capturar evidencia: navegador, dispositivo móvil o texto (API)."""
    try:
        from utils.screenshot_manager import ScreenshotManager
        sm = ScreenshotManager(category)

        # Buscar objeto Playwright (page) o Appium (driver)
        page = kwargs.get(page_kwarg) or next(
            (a for a in args if hasattr(a, "screenshot")), None
        )
        driver = kwargs.get(driver_kwarg) or next(
            (a for a in args if hasattr(a, "save_screenshot")), None
        )

        if page is not None:
            sm.capture_playwright(page, func_name.replace(".", "_"))
        elif driver is not None:
            sm.capture_appium(driver, func_name.replace(".", "_"))
        else:
            # API test: crear captura de texto con el error
            error_msg = f"{type(exception).__name__}: {exception}"
            sm.capture_api_failure(
                test_name=func_name.replace(".", "_"),
                error_message=error_msg,
            )
    except Exception as e:
        log.debug("[screenshot_on_fail] Could not capture evidence: %s", e)


def require_server(url_attr: str = "base_url") -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from config.settings import server as _srv
            url = getattr(_srv, url_attr, _srv.base_url)
            try:
                requests.get(url, timeout=3)
            except requests.RequestException:
                pytest.skip(f"Server unreachable at {url}")
            return func(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorator