from __future__ import annotations
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOGS_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_root_logger() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(console)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"rombo_{timestamp}.log"
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(file_handler)

    for lib in ("urllib3", "selenium", "appium", "asyncio", "playwright"):
        logging.getLogger(lib).setLevel(logging.WARNING)


_configure_root_logger()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
