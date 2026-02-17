from robot_automation_studio.window_focus import focus_visible_window_with_hint


def test_focus_does_not_restore_when_foreground_window_matches_and_is_not_minimized() -> None:
    show_calls: list[tuple[int, int]] = []
    focus_calls: list[int] = []

    focused = focus_visible_window_with_hint(
        "unity",
        enum_windows_func=lambda *_args: None,
        is_window_visible_func=lambda _handle: True,
        is_iconic_func=lambda _handle: False,
        get_window_text_func=lambda _handle: "MyProject - Unity 2022.3",
        get_foreground_window_func=lambda: 101,
        show_window_func=lambda handle, flag: show_calls.append((handle, flag)),
        set_foreground_window_func=lambda handle: focus_calls.append(handle),
        restore_flag=123,
    )

    assert focused is True
    assert show_calls == []
    assert focus_calls == [101]


def test_focus_restores_when_foreground_window_matches_and_is_minimized() -> None:
    show_calls: list[tuple[int, int]] = []
    focus_calls: list[int] = []

    focused = focus_visible_window_with_hint(
        "unity",
        enum_windows_func=lambda *_args: None,
        is_window_visible_func=lambda _handle: True,
        is_iconic_func=lambda _handle: True,
        get_window_text_func=lambda _handle: "MyProject - Unity 2022.3",
        get_foreground_window_func=lambda: 202,
        show_window_func=lambda handle, flag: show_calls.append((handle, flag)),
        set_foreground_window_func=lambda handle: focus_calls.append(handle),
        restore_flag=999,
    )

    assert focused is True
    assert show_calls == [(202, 999)]
    assert focus_calls == [202]


def test_focus_does_not_restore_when_matching_window_is_not_minimized() -> None:
    show_calls: list[tuple[int, int]] = []
    focus_calls: list[int] = []
    titles = {10: "Notepad", 11: "Unity 2022.3 - Sample Project"}
    visibles = {10: True, 11: True}

    def _enum_windows(callback, _param):
        for handle in (10, 11):
            if not callback(handle, 0):
                return

    focused = focus_visible_window_with_hint(
        "unity",
        enum_windows_func=_enum_windows,
        is_window_visible_func=lambda handle: visibles[handle],
        is_iconic_func=lambda _handle: False,
        get_window_text_func=lambda handle: titles[handle],
        get_foreground_window_func=lambda: 0,
        show_window_func=lambda handle, flag: show_calls.append((handle, flag)),
        set_foreground_window_func=lambda handle: focus_calls.append(handle),
        restore_flag=321,
    )

    assert focused is True
    assert show_calls == []
    assert focus_calls == [11]


def test_focus_restores_when_matching_window_is_minimized() -> None:
    show_calls: list[tuple[int, int]] = []
    focus_calls: list[int] = []
    titles = {11: "Unity 2022.3 - Sample Project"}

    def _enum_windows(callback, _param):
        if not callback(11, 0):
            return

    focused = focus_visible_window_with_hint(
        "unity",
        enum_windows_func=_enum_windows,
        is_window_visible_func=lambda _handle: True,
        is_iconic_func=lambda _handle: True,
        get_window_text_func=lambda handle: titles[handle],
        get_foreground_window_func=lambda: 0,
        show_window_func=lambda handle, flag: show_calls.append((handle, flag)),
        set_foreground_window_func=lambda handle: focus_calls.append(handle),
        restore_flag=456,
    )

    assert focused is True
    assert show_calls == [(11, 456)]
    assert focus_calls == [11]
