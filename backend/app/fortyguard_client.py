from __future__ import annotations

import time
from typing import Any

import httpx

from .config import FORTYGUARD_API_KEY, FORTYGUARD_BASE_URL, FORTYGUARD_ENV_PARAMS


class FortyGuardError(RuntimeError):
    pass


class FortyGuardClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or FORTYGUARD_API_KEY
        self.base_url = (base_url or FORTYGUARD_BASE_URL).rstrip("/")
        self._http = httpx.Client(timeout=60.0, headers={"api-key": self.api_key})

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "FortyGuardClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = self._http.post(url, json=payload, headers={"Content-Type": "application/json"})
        return self._decode(response, url)

    def _get(self, path: str) -> httpx.Response:
        return self._http.get(f"{self.base_url}{path}")

    def _decode(self, response: httpx.Response, url: str) -> dict[str, Any]:
        try:
            body = response.json()
        except Exception as exc:
            raise FortyGuardError(f"{url} returned {response.status_code}: {response.text[:500]}") from exc
        if response.status_code >= 400:
            raise FortyGuardError(f"{url} returned {response.status_code}: {body}")
        return body

    def submit_heatmap(
        self,
        polygon_aoi: dict[str, Any],
        date_time: dict[str, Any],
        granularity: int = 100,
        analytic_type: str = "tcm",
    ) -> str:
        body = self._post(
            "/heatmap",
            {
                "polygon_aoi": polygon_aoi,
                "date_time": date_time,
                "granularity": granularity,
                "analytic_type": analytic_type,
            },
        )
        return self._activity_id(body)

    def submit_env_params(
        self,
        latitude: float,
        longitude: float,
        temperature: float,
        date_time: dict[str, Any],
        analysis: list[str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "temperature": temperature,
            "date_time": date_time,
        }
        params = analysis if analysis is not None else FORTYGUARD_ENV_PARAMS
        if params:
            payload["analysis"] = params
        body = self._post("/env_params", payload)
        return self._activity_id(body)

    def get_status(self, activity_id: str) -> dict[str, Any]:
        response = self._get(f"/status/{activity_id}")
        if response.status_code == 404:
            return {"status_code": 404, "data": {"status": "NotFound", "activity_id": activity_id}}
        return self._decode(response, f"/status/{activity_id}")

    def wait_for_result(
        self,
        activity_id: str,
        *,
        interval_s: float = 5.0,
        max_wait_s: float = 600.0,
    ) -> dict[str, Any]:
        deadline = time.time() + max_wait_s
        last: dict[str, Any] = {}
        while time.time() < deadline:
            last = self.get_status(activity_id)
            status = str(self._status_value(last)).lower()
            if status in {"completed", "succeeded", "success"}:
                return last
            if status in {"failed", "error"}:
                raise FortyGuardError(f"Activity {activity_id} failed: {last}")
            time.sleep(interval_s)
        raise TimeoutError(f"Activity {activity_id} did not complete in {max_wait_s}s. Last: {last}")

    def credits(self) -> dict[str, Any]:
        return self._post("/system/fetch-api-key-usage", {})

    @staticmethod
    def _activity_id(body: dict[str, Any]) -> str:
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        activity_id = (data or {}).get("activity_id") or body.get("activity_id")
        if not activity_id:
            raise FortyGuardError(f"No activity_id in submit response: {body}")
        return str(activity_id)

    @staticmethod
    def _status_value(body: dict[str, Any]) -> str:
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        return str((data or {}).get("status") or body.get("status") or body.get("message") or "")
