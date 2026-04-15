from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class CRMClient:
    def __init__(self) -> None:
        self.base_url = settings.crm_api_base_url.rstrip("/")
        self.timeout = settings.crm_api_timeout_seconds
        self.max_retries = settings.crm_api_max_retries

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        delay = 0.5
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "CRM request",
                    extra={"event": "crm_request", "context": {"url": url, "params": params, "attempt": attempt}},
                )
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                status_code = exc.response.status_code if getattr(exc, "response", None) is not None else None
                is_retryable = status_code is None or status_code >= 500
                logger.warning(
                    "CRM request failed",
                    extra={
                        "event": "crm_request_failed",
                        "context": {"url": url, "params": params, "attempt": attempt, "retryable": is_retryable},
                    },
                )
                if attempt >= self.max_retries or not is_retryable:
                    break
                import time

                time.sleep(delay)
                delay *= 2

        assert last_error is not None
        raise last_error

    def fetch_incremental(self, entity: str, updated_since: datetime | None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset = 0
        limit = 2
        while True:
            params: dict[str, Any] = {"limit": limit, "offset": offset}
            if updated_since:
                params["updated_since"] = updated_since.isoformat()
            payload = self._request(entity, params)
            records.extend(payload["data"])
            pagination = payload["pagination"]
            if pagination["next_offset"] is None:
                break
            offset = pagination["next_offset"]
        return records
