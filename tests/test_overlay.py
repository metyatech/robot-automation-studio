from robot_automation_studio.overlay import Rect, build_banner_text, compute_banner_rect


def test_compute_banner_rect_uses_target_window_center() -> None:
    screen = Rect(left=0, top=0, right=1920, bottom=1080)
    target = Rect(left=200, top=120, right=1200, bottom=900)

    rect = compute_banner_rect(
        screen=screen,
        target=target,
        banner_width=400,
        banner_height=40,
        margin_top=16,
    )

    assert rect.left == 500
    assert rect.top == 136
    assert rect.right == 900
    assert rect.bottom == 176


def test_compute_banner_rect_falls_back_to_screen_when_target_missing() -> None:
    screen = Rect(left=100, top=50, right=1700, bottom=950)

    rect = compute_banner_rect(
        screen=screen,
        target=None,
        banner_width=400,
        banner_height=40,
        margin_top=10,
    )

    assert rect.left == 700
    assert rect.top == 60
    assert rect.right == 1100
    assert rect.bottom == 100


def test_build_banner_text_contains_progress_and_hotkey() -> None:
    text = build_banner_text("Attaching to Unity /", "Ctrl+Shift+F12")
    assert text == "Attaching to Unity /  |  Press Ctrl+Shift+F12 to stop"


def test_build_banner_text_normalizes_blank_progress() -> None:
    text = build_banner_text("", "Ctrl+Shift+F12")
    assert text == "Running  |  Press Ctrl+Shift+F12 to stop"
