from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    APPROVED = "Aprobado"
    NOT_APPROVED = "No Aprobado"
    PENDING = "Pendiente"
    SKIPPED = "Omitido"


@dataclass
class CourierCredentials:
    login: str
    password: str
    first_name: str
    courier_id: Optional[int] = None


@dataclass
class OrderPayload:
    first_name: str
    last_name: str
    address: str
    metro_station: str
    phone: str
    rent_time: int
    delivery_date: str
    color: list[str] = field(default_factory=list)
    comment: str = ""


@dataclass
class OrderResult:
    track: str
    order_id: Optional[int] = None


@dataclass
class ChecklistItem:
    row_index: int
    item_id: int | str
    description: str
    status: Status = Status.PENDING
    jira_link: str = ""
    screenshot_path: str = ""
    error_message: str = ""


@dataclass
class ValidationCase:
    row_index: int
    field_name: str
    class_name: str
    limits: str
    test_data: str
    boundary_data: str
    explanation: str
    status: Status = Status.PENDING
    jira_link: str = ""
    screenshot_path: str = ""
    error_message: str = ""

    @property
    def case_id(self) -> str:
        safe_field = self.field_name.replace(" ", "_").lower()
        safe_class = self.class_name.replace(" ", "_").lower()
        return f"val_{safe_field}_{safe_class}"


@dataclass
class MobileTestCase:
    row_index: int
    case_id: str
    name: str
    preconditions: str
    step_count: int
    steps: str
    expected_result: str
    version: str
    screenshot_required: bool
    status: Status = Status.PENDING
    jira_link: str = ""
    screenshot_path: str = ""
    error_message: str = ""


@dataclass
class ApiChecklistItem:
    row_index: int
    endpoint: str
    expected_code: str
    description: str
    status: Status = Status.PENDING
    jira_link: str = ""
    screenshot_path: str = ""
    error_message: str = ""

    @property
    def item_id(self) -> str:
        safe_ep = self.endpoint.replace("/", "_").replace(" ", "_").strip("_")
        return f"api_{safe_ep}_{self.row_index}"
