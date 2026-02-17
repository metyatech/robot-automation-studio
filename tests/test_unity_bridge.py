from robot_automation_studio.unity_bridge import UnityBridgeClient


class DummyBridgeClient(UnityBridgeClient):
    def __init__(self, payloads: list[dict[str, object] | Exception]) -> None:
        super().__init__(host="127.0.0.1", port=39067, timeout_seconds=0.1)
        self._payloads = list(payloads)

    def _request(  # type: ignore[override]
        self,
        method: str,
        path: str,
        payload=None,
        timeout_seconds=None,
    ):
        assert method == "GET"
        assert path == "/v1/selection"
        if not self._payloads:
            raise RuntimeError("no payload")
        next_item = self._payloads.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return dict(next_item)


def test_is_available_returns_true_when_bridge_reports_ok() -> None:
    client = DummyBridgeClient([{"ok": True, "hierarchy_path": ""}])
    assert client.is_available() is True


def test_wait_until_available_returns_true_when_bridge_becomes_ready() -> None:
    client = DummyBridgeClient(
        [
            RuntimeError("not ready"),
            {"ok": False},
            {"ok": True, "hierarchy_path": ""},
        ]
    )
    timeline = iter([0.0, 0.1, 0.2, 0.3, 0.4])
    sleeps: list[float] = []

    ready = client.wait_until_available(
        timeout_seconds=1.0,
        poll_interval_seconds=0.1,
        now_func=lambda: next(timeline),
        sleep_func=sleeps.append,
    )

    assert ready is True
    assert len(sleeps) >= 1


def test_wait_until_available_returns_false_on_timeout() -> None:
    client = DummyBridgeClient([RuntimeError("not ready"), RuntimeError("not ready")])
    timeline = iter([0.0, 0.2, 0.5, 1.0, 1.1])

    ready = client.wait_until_available(
        timeout_seconds=1.0,
        poll_interval_seconds=0.2,
        now_func=lambda: next(timeline),
        sleep_func=lambda _seconds: None,
    )

    assert ready is False


def test_wait_until_available_passes_request_timeout_override() -> None:
    class TimeoutProbeBridge(UnityBridgeClient):
        def __init__(self) -> None:
            super().__init__(host="127.0.0.1", port=39067, timeout_seconds=0.1)
            self.request_timeouts: list[float | None] = []

        def _request(  # type: ignore[override]
            self,
            method: str,
            path: str,
            payload=None,
            timeout_seconds=None,
        ):
            self.request_timeouts.append(timeout_seconds)
            return {"ok": True}

    client = TimeoutProbeBridge()
    ready = client.wait_until_available(
        timeout_seconds=1.0,
        poll_interval_seconds=0.1,
        request_timeout_seconds=0.8,
    )

    assert ready is True
    assert client.request_timeouts == [0.8]


def test_get_selection_state_includes_selection_version_when_present() -> None:
    client = DummyBridgeClient(
        [{"ok": True, "hierarchy_path": "Root/Child", "selection_version": 123}]
    )
    state = client.get_selection_state()
    assert state["ok"] is True
    assert state["hierarchy_path"] == "Root/Child"
    assert state["selection_version"] == 123


def test_wait_for_selection_change_requests_wait_endpoint() -> None:
    class DummyWaitBridge(UnityBridgeClient):
        def __init__(self) -> None:
            super().__init__(host="127.0.0.1", port=39067, timeout_seconds=0.1)
            self.requests: list[tuple[str, str]] = []

        def _request(  # type: ignore[override]
            self,
            method: str,
            path: str,
            payload=None,
            timeout_seconds=None,
        ):
            _ = payload
            _ = timeout_seconds
            self.requests.append((method, path))
            return {"ok": True, "hierarchy_path": "Main Camera", "selection_version": 11}

    client = DummyWaitBridge()
    state = client.wait_for_selection_change(after_version=10, timeout_seconds=0.2)

    assert state["ok"] is True
    assert state["hierarchy_path"] == "Main Camera"
    assert state["selection_version"] == 11
    assert client.requests == [("GET", "/v1/selection/wait?after_version=10&timeout_ms=200")]
