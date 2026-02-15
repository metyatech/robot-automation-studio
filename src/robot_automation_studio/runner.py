"""Robot suite execution helpers."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def start_robot_process(
    suite_path: Path,
    output_dir: Path,
    variable_output_dir: Path,
) -> subprocess.Popen[str]:
    command = build_robot_command(
        suite_path=suite_path,
        output_dir=output_dir,
        variable_output_dir=variable_output_dir,
    )
    creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return subprocess.Popen(
        [sys.executable, *command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )


def wait_robot_process(process: subprocess.Popen[str]) -> RunResult:
    stdout, stderr = process.communicate()
    return RunResult(return_code=int(process.returncode or 0), stdout=stdout, stderr=stderr)


def stop_robot_process(process: subprocess.Popen[Any]) -> bool:
    if process.poll() is not None:
        return False
    subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def run_robot(
    suite_path: Path,
    output_dir: Path,
    variable_output_dir: Path,
    executor: Executor | None = None,
) -> RunResult:
    if executor is not None:
        command = build_robot_command(
            suite_path=suite_path,
            output_dir=output_dir,
            variable_output_dir=variable_output_dir,
        )
        return_code, stdout, stderr = executor(command)
        return RunResult(return_code=return_code, stdout=stdout, stderr=stderr)

    process = start_robot_process(
        suite_path=suite_path,
        output_dir=output_dir,
        variable_output_dir=variable_output_dir,
    )
    return wait_robot_process(process)
