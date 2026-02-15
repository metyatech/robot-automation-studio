import subprocess
from pathlib import Path
from typing import Any

from robot_automation_studio.runner import (
    build_robot_command,
    run_robot,
    start_robot_process,
    stop_robot_process,
    wait_robot_process,
)


def test_build_robot_command() -> None:
    args = build_robot_command(
        suite_path=Path("suite.robot"),
        output_dir=Path("artifacts"),
        variable_output_dir=Path("out"),
    )
    assert args[0:2] == ["-m", "robot"]
    assert "--outputdir" in args
    assert "suite.robot" in args
    assert any(part.startswith("OUTPUT DIR:") for part in args)


def test_run_robot_with_fake_executor(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_executor(command: list[str]) -> tuple[int, str, str]:
        calls.append(command)
        return (0, "ok", "")

    suite_path = tmp_path / "suite.robot"
    suite_path.write_text("*** Test Cases ***\nDemo\n    No Operation\n", encoding="utf-8")
    result = run_robot(
        suite_path=suite_path,
        output_dir=tmp_path / "artifacts",
        variable_output_dir=tmp_path / "out",
        executor=fake_executor,
    )

    assert result.return_code == 0
    assert result.stdout == "ok"
    assert len(calls) == 1


def test_start_robot_process_builds_python_command(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class DummyPopen:
        def __init__(self, args: list[str], **kwargs: Any) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(subprocess, "Popen", DummyPopen)
    process = start_robot_process(
        suite_path=Path("suite.robot"),
        output_dir=Path("out"),
        variable_output_dir=Path("var"),
    )

    assert isinstance(process, DummyPopen)
    assert captured["args"][1:3] == ["-m", "robot"]
    assert captured["kwargs"]["text"] is True


def test_wait_robot_process_collects_stdout_and_stderr() -> None:
    class DummyProcess:
        returncode = 3

        def communicate(self) -> tuple[str, str]:
            return ("stdout", "stderr")

    result = wait_robot_process(DummyProcess())  # type: ignore[arg-type]
    assert result.return_code == 3
    assert result.stdout == "stdout"
    assert result.stderr == "stderr"


def test_stop_robot_process_terminates_process_tree(monkeypatch: Any) -> None:
    called: dict[str, Any] = {}

    class DummyProcess:
        pid = 1234

        def poll(self) -> None:
            return None

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        called["args"] = args
        called["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(subprocess, "run", fake_run)
    stopped = stop_robot_process(DummyProcess())  # type: ignore[arg-type]

    assert stopped is True
    assert called["args"] == ["taskkill", "/PID", "1234", "/T", "/F"]


def test_stop_robot_process_returns_false_when_already_finished() -> None:
    class DummyProcess:
        def poll(self) -> int:
            return 0

    stopped = stop_robot_process(DummyProcess())  # type: ignore[arg-type]
    assert stopped is False
