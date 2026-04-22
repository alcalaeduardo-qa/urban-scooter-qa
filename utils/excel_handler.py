from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path
from typing import Generator

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from config import settings
from models.test_entities import (
    ApiChecklistItem, ChecklistItem, MobileTestCase, Status, ValidationCase,
)
from utils.logger import get_logger

log = get_logger("excel_handler")

_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
_RED   = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

_STATUS_FILLS = {
    Status.APPROVED: _GREEN,
    Status.NOT_APPROVED: _RED,
    Status.PENDING: _YELLOW,
    Status.SKIPPED: _YELLOW,
}

_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


class ExcelHandler:
    def __init__(self, template_filename: str) -> None:
        self._template_path = settings.EXCEL_TEMPLATES_DIR / template_filename
        self._working_path = self._make_working_copy(template_filename)
        self._wb: Workbook = openpyxl.load_workbook(self._working_path)
        log.info("[excel] Opened working copy: %s", self._working_path.name)

    @classmethod
    def for_tarea2_checklist(cls) -> "ExcelHandler":
        return cls(settings.excel.tarea_2_checklist)

    @classmethod
    def for_tarea2_validation(cls) -> "ExcelHandler":
        return cls(settings.excel.tarea_2_validation)

    @classmethod
    def for_tarea3_cases(cls) -> "ExcelHandler":
        return cls(settings.excel.tarea_3_cases)

    @classmethod
    def for_tarea4_checklist(cls) -> "ExcelHandler":
        return cls(settings.excel.tarea_4_checklist)

    @classmethod
    def for_tarea5_opera(cls) -> "ExcelHandler":
        """Open the happy-path template, active sheet = 'Happy Path - Opera'."""
        handler = cls(settings.excel.tarea_5_happy_path)
        # openpyxl loads sheets in order; make sheet 1 (Opera) the active one
        handler._wb.active = handler._wb.worksheets[0]
        return handler

    @classmethod
    def for_tarea5_chrome(cls) -> "ExcelHandler":
        """Open the happy-path template, active sheet = 'Happy Path - Chrome'."""
        handler = cls(settings.excel.tarea_5_happy_path)
        handler._wb.active = handler._wb.worksheets[1]
        return handler

    def read_checklist_t2(self) -> Generator[ChecklistItem, None, None]:
        ws = self._active_sheet()
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not self._has_data(row, 0):
                continue
            yield ChecklistItem(row_index=row_idx, item_id=row[0], description=str(row[1] or ""))

    def read_validation_t2(self) -> Generator[ValidationCase, None, None]:
        ws = self._active_sheet()
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not self._has_data(row, 0):
                continue
            yield ValidationCase(
                row_index=row_idx, field_name=str(row[0] or ""),
                class_name=str(row[1] or ""), limits=str(row[2] or ""),
                test_data=str(row[3] or ""), boundary_data=str(row[4] or ""),
                explanation=str(row[5] or ""),
            )

    def read_cases_t3(self) -> Generator[MobileTestCase, None, None]:
        """Read mobile test cases, skipping section headers and legend rows."""
        ws = self._active_sheet()
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not self._has_data(row, 0):
                continue
            case_id = str(row[0] or "").strip()
            # Skip section header rows and legend rows — only process mob-XX IDs
            if not case_id.startswith("mob-"):
                continue
            screenshot_val = str(row[7] or "").lower()
            required = "s\u00ed" in screenshot_val or "si" in screenshot_val or "yes" in screenshot_val
            step_count = 0
            if row[3] is not None:
                try:
                    step_count = int(row[3])
                except (ValueError, TypeError):
                    step_count = 0
            yield MobileTestCase(
                row_index=row_idx, case_id=case_id,
                name=str(row[1] or ""), preconditions=str(row[2] or ""),
                step_count=step_count,
                steps=str(row[4] or ""), expected_result=str(row[5] or ""),
                version=str(row[6] or ""), screenshot_required=required,
            )

    def read_checklist_t4(self) -> Generator[ApiChecklistItem, None, None]:
        # Template: ID(A) | Endpoint(B) | Código Respuesta(C) | Descripción(D) | Estado(E) | Jira(F)
        ws = self._active_sheet()
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not self._has_data(row, 0):
                continue
            yield ApiChecklistItem(
                row_index=row_idx, endpoint=str(row[1] or ""),
                expected_code=str(row[2] or ""), description=str(row[3] or ""),
            )

    def read_cases_t5(self, prefix: str = "op") -> Generator[MobileTestCase, None, None]:
        """Read happy-path cases from the active sheet.

        Args:
            prefix: 'op' for Opera cases (op-XX) or 'ch' for Chrome cases (ch-XX).
        """
        ws = self._active_sheet()
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not self._has_data(row, 0):
                continue
            case_id = str(row[0] or "").strip()
            # Skip section header rows — only process IDs matching the expected prefix
            if not case_id.startswith(f"{prefix}-"):
                continue
            screenshot_val = str(row[7] or "").lower()
            required = "sí" in screenshot_val or "si" in screenshot_val or "yes" in screenshot_val
            step_count = 0
            if row[3] is not None:
                try:
                    step_count = int(row[3])
                except (ValueError, TypeError):
                    step_count = 0
            yield MobileTestCase(
                row_index=row_idx, case_id=case_id,
                name=str(row[1] or ""), preconditions=str(row[2] or ""),
                step_count=step_count,
                steps=str(row[4] or ""), expected_result=str(row[5] or ""),
                version=str(row[6] or ""), screenshot_required=required,
            )

    def write_status(
        self, row_index: int, status: Status, status_col: int,
        jira_col: int | None = None, jira_link: str = "",
        screenshot_path: str = "", error_message: str = "",
        comment: str = "",
    ) -> None:
        ws = self._active_sheet()
        cell = ws.cell(row=row_index, column=status_col + 1)
        cell.value = status.value
        cell.fill = _STATUS_FILLS.get(status, _YELLOW)

        if jira_col is not None and jira_link:
            ws.cell(row=row_index, column=jira_col + 1).value = jira_link

        # Screenshot path goes in col H (captura de pantalla)
        if screenshot_path:
            ws.cell(row=row_index, column=8).value = screenshot_path

        # Comment / error reason goes in Col K (Comentarios)
        comment_text = comment or (f"Error: {error_message[:300]}" if error_message else "")
        if comment_text:
            try:
                comment_col = (jira_col + 2) if jira_col is not None else (status_col + 2)
                ws.cell(row=row_index, column=comment_col).value = comment_text
            except Exception:
                pass

    def save(self) -> Path:
        self._wb.save(self._working_path)
        log.info("[excel] Saved: %s", self._working_path)
        return self._working_path

    def _active_sheet(self) -> Worksheet:
        return self._wb.active  # type: ignore

    @staticmethod
    def _has_data(row: tuple, col: int) -> bool:
        return row[col] is not None and str(row[col]).strip() != ""

    def _make_working_copy(self, filename: str) -> Path:
        dest = settings.RESULTS_DIR / f"{Path(filename).stem}_{_TIMESTAMP}.xlsx"
        if not self._template_path.exists():
            raise FileNotFoundError(
                f"Template not found: {self._template_path}\n"
                "Copy your Excel templates into the excel_templates/ folder."
            )
        shutil.copy2(self._template_path, dest)
        return dest
