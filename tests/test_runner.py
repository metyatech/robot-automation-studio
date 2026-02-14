from pathlib import Path

from robot_automation_studio.runner import build_robot_command, run_robot


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
