from __future__ import annotations
import uuid
from typing import Any

import requests

from config.settings import server as srv_cfg, test_data
from models.test_entities import CourierCredentials, OrderResult
from utils.decorators import log_step, retry
from utils.logger import get_logger

log = get_logger("api_client")
_TIMEOUT = 30


class _ApiSession:
    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or srv_cfg.api_base_url).rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self._session.post(self._url(path), timeout=_TIMEOUT, **kwargs)

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self._session.get(self._url(path), timeout=_TIMEOUT, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self._session.put(self._url(path), timeout=_TIMEOUT, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self._session.delete(self._url(path), timeout=_TIMEOUT, **kwargs)

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    def close(self) -> None:
        self._session.close()


class CourierApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._session = _ApiSession(base_url)

    @log_step("POST /api/v1/courier — create courier")
    @retry(max_attempts=2, delay=1.0, exceptions=(requests.ConnectionError,))
    def create(self, login=None, password=None, first_name=None) -> requests.Response:
        payload: dict[str, Any] = {}
        if login is not None:
            payload["login"] = login
        if password is not None:
            payload["password"] = password
        if first_name is not None:
            payload["firstName"] = first_name
        return self._session.post("/courier", json=payload)

    @log_step("POST /api/v1/courier/login — authenticate courier")
    @retry(max_attempts=2, delay=1.0, exceptions=(requests.ConnectionError,))
    def login(self, login=None, password=None) -> requests.Response:
        payload: dict[str, Any] = {}
        if login is not None:
            payload["login"] = login
        if password is not None:
            payload["password"] = password
        return self._session.post("/courier/login", json=payload)

    @log_step("DELETE /api/v1/courier/{id}")
    def delete(self, courier_id) -> requests.Response:
        if courier_id is None:
            return self._session.delete("/courier/")
        return self._session.delete(f"/courier/{courier_id}")

    @log_step("GET /api/v1/courier/{id}/ordersCount")
    def get_orders_count(self, courier_id) -> requests.Response:
        if courier_id is None:
            return self._session.get("/courier//ordersCount")
        return self._session.get(f"/courier/{courier_id}/ordersCount")

    def create_valid_courier(self) -> CourierCredentials:
        login = test_data.courier_login_prefix + uuid.uuid4().hex[:8]
        password = test_data.courier_password
        first_name = test_data.courier_first_name

        log.info(
            f"\n{'='*54}\n[QA] CREATING COURIER ON SERVER\n"
            f"login='{login}', first_name='{first_name}'\n{'='*54}"
        )

        resp = self.create(login=login, password=password, first_name=first_name)
        if resp.status_code not in (201, 409):
            log.warning(f"Unexpected status creating courier: {resp.status_code} - {resp.text}")

        return CourierCredentials(login=login, password=password, first_name=first_name)

    def login_and_get_id(self, credentials: CourierCredentials) -> int:
        resp = self.login(login=credentials.login, password=credentials.password)
        assert resp.status_code == 200, (
            f"Expected 200 on login, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        
        log.info(f"\n======================================================\n"
                 f"[QA] AUTHENTICATING AND EXTRACTING SERVER DATA\n"
                 f"Sever explicitly recognized the courier. Data extracted: {data}\n"
                 f"======================================================\n")
                 
        courier_id = data.get("id") or data.get("courierId")
        assert courier_id, f"No id in login response: {data}"
        credentials.courier_id = int(courier_id)
        return int(courier_id)

    def close(self) -> None:
        self._session.close()


class OrderApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._session = _ApiSession(base_url)

    @log_step("POST /api/v1/orders — create order")
    @retry(max_attempts=2, delay=1.0, exceptions=(requests.ConnectionError,))
    def create(self, payload: dict[str, Any]) -> requests.Response:
        return self._session.post("/orders", json=payload)

    @log_step("GET /api/v1/orders/track")
    def get_by_track(self, track=None) -> requests.Response:
        params = {"t": track} if track is not None else {}
        return self._session.get("/orders/track", params=params)

    @log_step("GET /api/v1/orders — list all")
    def list_all(self) -> requests.Response:
        return self._session.get("/orders")

    @log_step("PUT /api/v1/orders/accept/{id}")
    def accept(self, order_id, courier_id) -> requests.Response:
        if order_id is None:
            return self._session.put("/orders/accept/",
                                     params={"courierId": courier_id})
        params = {}
        if courier_id is not None:
            params["courierId"] = courier_id
        return self._session.put(f"/orders/accept/{order_id}", params=params)

    @log_step("PUT /api/v1/orders/cancel")
    def cancel(self, track=None) -> requests.Response:
        payload: dict[str, Any] = {}
        if track is not None:
            # The server expects `track` as an integer in the JSON body.
            # Sending a numeric string causes 400 'Not enough data for search'.
            try:
                payload["track"] = int(track)
            except (ValueError, TypeError):
                payload["track"] = track  # keep as-is for intentional negative tests
        return self._session.put("/orders/cancel", json=payload)

    @log_step("PUT /api/v1/orders/finish/{id}")
    def finish(self, order_id) -> requests.Response:
        if order_id is None:
            return self._session.put("/orders/finish/")
        return self._session.put(f"/orders/finish/{order_id}")

    def create_valid_order(self) -> OrderResult:
        from datetime import date, timedelta
        delivery_date = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        payload = {
            "firstName": test_data.order_first_name,
            "lastName": test_data.order_last_name,
            "address": test_data.order_address,
            "metroStation": test_data.order_metro_station,
            "phone": test_data.order_phone,
            "rentTime": test_data.order_rental_days,
            "deliveryDate": delivery_date,
            "comment": test_data.order_comment,
            "color": [],
        }
        resp = self.create(payload)
        assert resp.status_code == 201, (
            f"Expected 201 creating order, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        track = str(data.get("track", ""))
        order_id = data.get("id") or data.get("orderId")
        assert track, f"No track in create-order response: {data}"
        return OrderResult(track=track, order_id=int(order_id) if order_id else None)

    def close(self) -> None:
        self._session.close()
