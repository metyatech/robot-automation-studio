import json
from pathlib import Path

from robot_automation_studio.run_diagnostics import (
    capture_failure_screenshot,
    parse_robot_output,
    summarize_run_diagnostics_payload,
    write_run_diagnostics_file,
)


def test_parse_robot_output_extracts_failure_and_docmeta(tmp_path: Path) -> None:
    output_xml = tmp_path / "output.xml"
    output_xml.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<robot generated="2026-02-16T10:00:00.000000">\n'
            '  <suite name="suite-a">\n'
            '    <test name="case-a">\n'
            '      <kw name="Click Unity Relative" owner="lib">\n'
            '        <msg level="INFO">'
            'DOCMETA:{"annotation":{"type":"click","box":{"x":10,"y":20}}}'
            "</msg>\n"
            "        <arg>0.5</arg>\n"
            "        <arg>0.4</arg>\n"
            '        <status status="PASS" elapsed="0.250000"/>\n'
            "      </kw>\n"
            '      <kw name="Type Unity Text" owner="lib">\n'
            '        <msg level="FAIL">Element not interactable</msg>\n'
            "        <arg>tail-length</arg>\n"
            '        <status status="FAIL" elapsed="0.100000"/>\n'
            "      </kw>\n"
            '      <status status="FAIL" elapsed="0.450000"/>\n'
            "    </test>\n"
            "  </suite>\n"
            "</robot>\n"
        ),
        encoding="utf-8",
    )

    diagnostics = parse_robot_output(output_xml)

    assert diagnostics.test_status == "FAIL"
    assert diagnostics.suite_name == "suite-a"
    assert diagnostics.test_name == "case-a"
    assert diagnostics.total_keyword_count == 2
    assert diagnostics.failed_keyword is not None
    assert diagnostics.failed_keyword.name == "Type Unity Text"
    assert diagnostics.last_annotation is not None
    assert diagnostics.last_annotation["annotation"]["type"] == "click"
    assert diagnostics.slowest_keywords[0].name == "Click Unity Relative"


def test_write_run_diagnostics_file_writes_json_payload(tmp_path: Path) -> None:
    output_xml = tmp_path / "output.xml"
    output_xml.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<robot generated="2026-02-16T10:00:00.000000">\n'
            '  <suite name="suite-b">\n'
            '    <test name="case-b">\n'
            '      <kw name="Wait For Seconds" owner="lib">\n'
            "        <arg>0.2</arg>\n"
            '        <status status="PASS" elapsed="0.200000"/>\n'
            "      </kw>\n"
            '      <status status="PASS" elapsed="0.200000"/>\n'
            "    </test>\n"
            "  </suite>\n"
            "</robot>\n"
        ),
        encoding="utf-8",
    )
    diagnostics = parse_robot_output(output_xml)
    target = tmp_path / "run-diagnostics.json"

    saved = write_run_diagnostics_file(diagnostics, target_path=target, screenshot_path=None)

    assert saved == target
    payload = target.read_text(encoding="utf-8")
    assert '"suite_name": "suite-b"' in payload
    assert '"test_status": "PASS"' in payload


def test_write_run_diagnostics_file_includes_run_context(tmp_path: Path) -> None:
    output_xml = tmp_path / "output.xml"
    output_xml.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<robot generated="2026-02-16T10:00:00.000000">\n'
            '  <suite name="suite-c">\n'
            '    <test name="case-c">\n'
            '      <kw name="Wait For Seconds" owner="lib">\n'
            "        <arg>0.2</arg>\n"
            '        <status status="PASS" elapsed="0.200000"/>\n'
            "      </kw>\n"
            '      <status status="PASS" elapsed="0.200000"/>\n'
            "    </test>\n"
            "  </suite>\n"
            "</robot>\n"
        ),
        encoding="utf-8",
    )
    diagnostics = parse_robot_output(output_xml)
    target = tmp_path / "run-diagnostics.json"
    context = {"execution_mode": "attach", "active_profile": "vrchat"}

    saved = write_run_diagnostics_file(
        diagnostics,
        target_path=target,
        screenshot_path=None,
        run_context=context,
    )

    assert saved == target
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["run_context"] == context


def test_capture_failure_screenshot_returns_none_on_capture_error(tmp_path: Path) -> None:
    screenshot = capture_failure_screenshot(
        diagnostics_dir=tmp_path,
        image_grab=lambda: (_ for _ in ()).throw(RuntimeError("capture failed")),
    )
    assert screenshot is None


def test_summarize_run_diagnostics_payload_includes_run_context() -> None:
    summary = summarize_run_diagnostics_payload(
        {
            "test_status": "PASS",
            "suite_name": "suite-a",
            "test_name": "case-a",
            "total_elapsed_seconds": 0.42,
            "total_keyword_count": 5,
            "run_context": {
                "execution_mode": "attach",
                "active_profile": "vrchat",
                "window_hint": "Unity",
                "unity_project_path": "D:/VRChatProjects/Ryuon",
            },
        }
    )

    assert "Status: PASS" in summary
    assert "Suite/Test: suite-a / case-a" in summary
    assert "Execution Mode: attach" in summary
    assert "Active Profile: vrchat" in summary
