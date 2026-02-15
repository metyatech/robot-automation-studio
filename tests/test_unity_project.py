from robot_automation_studio.unity_project import (
    extract_project_path_from_command_line,
    resolve_attached_unity_project_path,
)


def test_extract_project_path_from_command_line_with_split_args() -> None:
    command_line = (
        '"C:\\Program Files\\Unity\\Editor\\Unity.exe" '
        '-projectPath "D:\\projects\\avatar-work" -logFile -'
    )
    result = extract_project_path_from_command_line(command_line)
    assert result == "D:\\projects\\avatar-work"


def test_extract_project_path_from_command_line_with_equals_arg() -> None:
    command_line = (
        '"C:\\Program Files\\Unity\\Editor\\Unity.exe" -projectpath=D:/projects/avatar-work'
    )
    result = extract_project_path_from_command_line(command_line)
    assert result == "D:/projects/avatar-work"


def test_extract_project_path_from_command_line_returns_none_when_missing() -> None:
    command_line = '"C:\\Program Files\\Unity\\Editor\\Unity.exe" -batchmode -quit'
    result = extract_project_path_from_command_line(command_line)
    assert result is None


def test_resolve_attached_unity_project_path_prefers_foreground_then_fallback() -> None:
    handles_by_hint = [200, 100]
    titles = {
        100: "Unity - Foreground",
        200: "Unity - Background",
    }
    pids = {
        100: 1100,
        200: 2200,
    }
    command_lines = {
        1100: '"Unity.exe" -batchmode',
        2200: '"Unity.exe" -projectPath "D:/projects/scene-a"',
    }

    result = resolve_attached_unity_project_path(
        window_hint="Unity",
        foreground_window_handle_getter=lambda: 100,
        window_title_getter=lambda handle: titles.get(handle, ""),
        candidate_window_handle_getter=lambda _hint: list(handles_by_hint),
        process_id_getter=lambda handle: pids.get(handle),
        process_command_line_getter=lambda pid: command_lines.get(pid),
    )

    assert result == "D:/projects/scene-a"


def test_resolve_attached_unity_project_path_returns_none_when_no_projectpath() -> None:
    result = resolve_attached_unity_project_path(
        window_hint="Unity",
        foreground_window_handle_getter=lambda: 100,
        window_title_getter=lambda _handle: "Unity",
        candidate_window_handle_getter=lambda _hint: [100],
        process_id_getter=lambda _handle: 1100,
        process_command_line_getter=lambda _pid: '"Unity.exe" -batchmode',
    )
    assert result is None
