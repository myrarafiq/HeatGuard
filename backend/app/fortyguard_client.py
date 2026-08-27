from __future__ import annotations

"""FortyGuard Temperature API client.

Submits heatmap and env_params jobs, then polls GET /status/{activity_id}
until the job completes. A 404 right after submit is a known API quirk and
is treated as "still running," not a missing job.
"""

import time
from typing import Any

import httpx

from .config import FORTYGUARD_API_KEY, FORTYGUARD_BASE_URL, FORTYGUARD_ENV_PARAMS, HEATMAP_GRANULARITY_M


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

    def _post(self, path: str, payload: dict[str, Any], *, retries: int = 3) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self._http.post(url, json=payload, headers={"Content-Type": "application/json"})
                if response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                return self._decode(response, url)
            except FortyGuardError as exc:
                last_error = exc
                if "429" in str(exc) or "500" in str(exc):
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise last_error or FortyGuardError(f"{url} failed after {retries} retries")

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
        granularity: int | None = None,
        analytic_type: str = "tcm",
        threshold: float | None = None,
        direction: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "polygon_aoi": polygon_aoi,
            "date_time": date_time,
            "granularity": granularity if granularity is not None else HEATMAP_GRANULARITY_M,
            "analytic_type": analytic_type,
        }
        if analytic_type in {"exceedance", "persistence"}:
            payload["threshold"] = 30.0 if threshold is None else threshold
            payload["direction"] = direction or "above"
        body = self._post("/heatmap", payload)
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
            # Documented quirk: GET /status/{id} may 404 immediately after submit.
            if status in {"completed", "succeeded", "success"}:
                return last
            if status in {"failed", "error"}:
                raise FortyGuardError(f"Activity {activity_id} failed: {last}")
            time.sleep(interval_s)
        raise TimeoutError(f"Activity {activity_id} did not complete in {max_wait_s}s. Last: {last}")

    def credits(self) -> dict[str, Any]:
        url = f"{self.base_url}/system/fetch-api-key-usage"
        response = self._http.post(
            url,
            json={"api_key": self.api_key},
            headers={"Content-Type": "application/json"},
            timeout=8.0,
        )
        return self._decode(response, url)

    def credits_remaining(self) -> dict[str, Any]:
        """Best-effort remaining-credit read. Never raises — /health must stay up."""
        if not self.api_key:
            return {"credits_remaining": None, "credits_status": "no_api_key"}
        try:
            body = self.credits()
        except Exception as exc:  # noqa: BLE001
            return {"credits_remaining": None, "credits_status": "error", "credits_error": str(exc)}
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        remaining = None
        for key in (
            "credits_remaining",
            "remaining_credits",
            "remaining",
            "credits",
            "balance",
        ):
            if isinstance(data, dict) and data.get(key) is not None:
                remaining = data.get(key)
                break
            if isinstance(body, dict) and body.get(key) is not None:
                remaining = body.get(key)
                break
        try:
            remaining_n = float(remaining) if remaining is not None else None
        except (TypeError, ValueError):
            remaining_n = None
        return {
            "credits_remaining": remaining_n,
            "credits_status": "ok" if remaining_n is not None else "unknown_shape",
            "credits_raw_keys": sorted((data or {}).keys()) if isinstance(data, dict) else [],
        }

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
