"""Unity Editor bridge client helpers for Studio recording."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any


class UnityBridgeClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 39067,
        timeout_seconds: float = 1.2,
    ) -> None:
        self.host = str(host).strip() or "127.0.0.1"
        self.port = int(port)
        self.timeout_seconds = max(0.1, float(timeout_seconds))

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    def is_available(self) -> bool:
        try:
            payload = self._request("GET", "/v1/selection")
        except Exception:
            return False
        return bool(payload.get("ok", False))

    def wait_until_available(
        self,
        timeout_seconds: float = 12.0,
        poll_interval_seconds: float = 0.25,
        now_func: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> bool:
        timeout = max(0.0, float(timeout_seconds))
        poll_interval = max(0.05, float(poll_interval_seconds))
        deadline = now_func() + timeout
        while True:
            if self.is_available():
                return True
            now = now_func()
            if now >= deadline:
                return False
            sleep_func(min(poll_interval, deadline - now))

    def get_selected_hierarchy_path(self) -> str | None:
        try:
            payload = self._request("GET", "/v1/selection")
        except Exception:
            return None
        if not bool(payload.get("ok", False)):
            return None
        hierarchy_path = str(payload.get("hierarchy_path") or "").strip()
        return hierarchy_path or None

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data: bytes | None = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            f"{self.endpoint}{path}",
            data=data,
            headers=headers,
            method=method.upper(),
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body or "{}")
        if not isinstance(parsed, dict):
            return {}
        return parsed
