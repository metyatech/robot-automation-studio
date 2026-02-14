"""Robot suite execution helpers."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

Executor = Callable[[list[str]], tuple[int, str, str]]


@dataclass(slots=True)
class RunResult:
    return_code: int
    stdout: str
    stderr: str


def build_robot_command(suite_path: Path, output_dir: Path, variable_output_dir: Path) -> list[str]:
    return [
        "-m",
        "robot",
        "--outputdir",
        str(output_dir),
        "--output",
        "output.xml",
        "--log",
        "NONE",
        "--report",
        "NONE",
        "--variable",
        f"OUTPUT DIR:{variable_output_dir}",
        str(suite_path),
    ]


def _default_executor(args: list[str]) -> tuple[int, str, str]:
    process = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return (process.returncode, process.stdout, process.stderr)


def run_robot(
    suite_path: Path,
    output_dir: Path,
    variable_output_dir: Path,
    executor: Executor | None = None,
) -> RunResult:
    command = build_robot_command(
        suite_path=suite_path,
        output_dir=output_dir,
        variable_output_dir=variable_output_dir,
    )
    runner = executor or _default_executor
    return_code, stdout, stderr = runner(command)
    return RunResult(return_code=return_code, stdout=stdout, stderr=stderr)
