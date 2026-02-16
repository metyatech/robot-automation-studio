"""Run diagnostics helpers for Robot output parsing and failure artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


@dataclass(slots=True)
class KeywordDiagnostic:
    name: str
    owner: str
    status: str
    elapsed_seconds: float
    args: list[str] = field(default_factory=list)
    message: str = ""


@dataclass(slots=True)
class RunDiagnostics:
    output_xml_path: Path
    generated_at: str
    suite_name: str
    test_name: str
    test_status: str
    total_elapsed_seconds: float
    total_keyword_count: int
    keywords: list[KeywordDiagnostic]
    slowest_keywords: list[KeywordDiagnostic]
    failed_keyword: KeywordDiagnostic | None
    last_annotation: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["output_xml_path"] = str(self.output_xml_path)
        return payload


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _msg_texts(keyword_node: ElementTree.Element) -> list[str]:
    texts: list[str] = []
    for msg in keyword_node.findall("msg"):
        text = _safe_text(msg.text)
        if text:
            texts.append(text)
    return texts


def _last_docmeta(msg_texts: list[str]) -> dict[str, Any] | None:
    for message in reversed(msg_texts):
        if not message.startswith("DOCMETA:"):
            continue
        payload_text = message[len("DOCMETA:") :].strip()
        if payload_text == "":
            continue
        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_robot_output(output_xml_path: Path) -> RunDiagnostics:
    tree = ElementTree.parse(output_xml_path)
    root = tree.getroot()
    suite = root.find(".//suite")
    test = root.find(".//test")
    if suite is None or test is None:
        raise ValueError(f"Robot output XML is missing suite/test: {output_xml_path}")

    test_status_node = test.find("status")
    if test_status_node is None:
        test_status = ""
        total_elapsed = 0.0
    else:
        test_status = _safe_text(test_status_node.attrib.get("status"))
        total_elapsed = _safe_float(test_status_node.attrib.get("elapsed"))

    keywords: list[KeywordDiagnostic] = []
    failed_keyword: KeywordDiagnostic | None = None
    last_annotation: dict[str, Any] | None = None

    for kw in test.iter("kw"):
        status_node = kw.find("status")
        if status_node is None:
            continue
        status = _safe_text(status_node.attrib.get("status")).upper()
        if status == "" or status == "NOT RUN":
            continue
        message_texts = _msg_texts(kw)
        annotation = _last_docmeta(message_texts)
        if annotation is not None:
            last_annotation = annotation

        fail_message = ""
        if status == "FAIL":
            for msg in kw.findall("msg"):
                level = _safe_text(msg.attrib.get("level")).upper()
                text = _safe_text(msg.text)
                if level in {"FAIL", "ERROR"} and text:
                    fail_message = text
                    break
            if fail_message == "":
                fail_message = _safe_text(status_node.text)

        item = KeywordDiagnostic(
            name=_safe_text(kw.attrib.get("name")),
            owner=_safe_text(kw.attrib.get("owner")),
            status=status,
            elapsed_seconds=_safe_float(status_node.attrib.get("elapsed")),
            args=[_safe_text(arg.text) for arg in kw.findall("arg") if _safe_text(arg.text)],
            message=fail_message,
        )
        keywords.append(item)
        if status == "FAIL" and failed_keyword is None:
            failed_keyword = item

    slowest = sorted(keywords, key=lambda item: item.elapsed_seconds, reverse=True)[:5]
    return RunDiagnostics(
        output_xml_path=output_xml_path,
        generated_at=_safe_text(root.attrib.get("generated")),
        suite_name=_safe_text(suite.attrib.get("name")),
        test_name=_safe_text(test.attrib.get("name")),
        test_status=test_status or ("FAIL" if failed_keyword else "PASS"),
        total_elapsed_seconds=total_elapsed,
        total_keyword_count=len(keywords),
        keywords=keywords,
        slowest_keywords=slowest,
        failed_keyword=failed_keyword,
        last_annotation=last_annotation,
    )


def write_run_diagnostics_file(
    diagnostics: RunDiagnostics,
    *,
    target_path: Path,
    screenshot_path: Path | None,
    run_context: dict[str, Any] | None = None,
) -> Path:
    payload = diagnostics.to_dict()
    payload["failure_screenshot_path"] = str(screenshot_path) if screenshot_path else None
    payload["run_context"] = dict(run_context) if isinstance(run_context, dict) else None
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def summarize_run_diagnostics_payload(payload: dict[str, Any]) -> str:
    test_status = _safe_text(payload.get("test_status")).upper() or "-"
    suite_name = _safe_text(payload.get("suite_name")) or "-"
    test_name = _safe_text(payload.get("test_name")) or "-"
    elapsed = _safe_float(payload.get("total_elapsed_seconds"))
    total_keywords = int(payload.get("total_keyword_count") or 0)

    run_context = payload.get("run_context")
    context = run_context if isinstance(run_context, dict) else {}
    execution_mode = _safe_text(context.get("execution_mode")) or "-"
    active_profile = _safe_text(context.get("active_profile")) or "-"
    window_hint = _safe_text(context.get("window_hint")) or "-"
    unity_project_path = _safe_text(context.get("unity_project_path")) or "-"

    return (
        "Run Diagnostics Summary\n"
        f"- Status: {test_status}\n"
        f"- Suite/Test: {suite_name} / {test_name}\n"
        f"- Elapsed: {elapsed:.3f}s\n"
        f"- Keywords: {total_keywords}\n"
        f"- Execution Mode: {execution_mode}\n"
        f"- Active Profile: {active_profile}\n"
        f"- Window Hint: {window_hint}\n"
        f"- Unity Project Path: {unity_project_path}"
    )


def capture_failure_screenshot(
    *,
    diagnostics_dir: Path,
    image_grab: Any | None = None,
    now_func: Any | None = None,
) -> Path | None:
    if image_grab is None:
        from PIL import ImageGrab

        def _default_grab() -> Any:
            return ImageGrab.grab(all_screens=True)

        image_grab = _default_grab
    now = now_func or datetime.now
    try:
        image = image_grab()
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        name = now().strftime("failure-%Y%m%d-%H%M%S.png")
        target = diagnostics_dir / name
        image.save(target)
        return target
    except Exception:
        return None
