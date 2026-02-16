from __future__ import annotations

import pytest

from robot_automation_studio.app_dialogs import (
    normalize_profile_form_payload,
    normalize_variable_form_payload,
)


def test_normalize_variable_form_payload_parses_required_fields() -> None:
    payload = normalize_variable_form_payload(
        variable_id="unity_project_path",
        variable_type="path",
        required=True,
        default_text="D:/VRChatProjects/Ryuon",
    )
    assert payload["id"] == "unity_project_path"
    assert payload["type"] == "path"
    assert payload["required"] is True
    assert payload["default"] == "D:/VRChatProjects/Ryuon"


def test_normalize_variable_form_payload_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="Variable id is required"):
        normalize_variable_form_payload(
            variable_id="",
            variable_type="string",
            required=False,
            default_text="",
        )


def test_normalize_variable_form_payload_parses_typed_defaults() -> None:
    int_payload = normalize_variable_form_payload(
        variable_id="retry_count",
        variable_type="int",
        required=False,
        default_text="3",
    )
    bool_payload = normalize_variable_form_payload(
        variable_id="enabled",
        variable_type="bool",
        required=False,
        default_text="true",
    )
    json_payload = normalize_variable_form_payload(
        variable_id="settings",
        variable_type="json",
        required=False,
        default_text='{"quality":"high"}',
    )

    assert int_payload["default"] == 3
    assert bool_payload["default"] is True
    assert json_payload["default"] == {"quality": "high"}


def test_normalize_variable_form_payload_rejects_invalid_typed_default() -> None:
    with pytest.raises(ValueError, match="Invalid int value"):
        normalize_variable_form_payload(
            variable_id="retry_count",
            variable_type="int",
            required=False,
            default_text="abc",
        )


def test_normalize_profile_form_payload_parses_override_rows() -> None:
    payload = normalize_profile_form_payload(
        profile_name="vrchat",
        description="VRChat profile",
        override_rows=[
            ("unity_window_hint", "Unity"),
            ("unity_project_path", '"D:/VRChatProjects/Ryuon"'),
            ("max_retry", "3"),
        ],
    )
    assert payload["name"] == "vrchat"
    assert payload["profile"]["description"] == "VRChat profile"
    assert payload["profile"]["variables"]["unity_window_hint"] == "Unity"
    assert payload["profile"]["variables"]["unity_project_path"] == "D:/VRChatProjects/Ryuon"
    assert payload["profile"]["variables"]["max_retry"] == 3


def test_normalize_profile_form_payload_rejects_empty_profile_name() -> None:
    with pytest.raises(ValueError, match="Profile name is required"):
        normalize_profile_form_payload(
            profile_name="",
            description="",
            override_rows=[],
        )
