"""Unity UPM manifest helpers for Studio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_UNITY_BRIDGE_PACKAGE_NAME = "com.metyatech.unity-automation-bridge"
DEFAULT_UNITY_BRIDGE_PACKAGE_URL = (
    "https://github.com/metyatech/robotframework-unity-editor.git?path=/unity-package#main"
)
LEGACY_UNITY_BRIDGE_SCRIPT_RELATIVE_PATH = Path("Assets/Editor/RobotFrameworkUnityBridge.cs")


def _remove_legacy_bridge_script(project_root: Path) -> bool:
    changed = False
    script_path = project_root / LEGACY_UNITY_BRIDGE_SCRIPT_RELATIVE_PATH
    for path in (script_path, Path(f"{script_path}.meta")):
        if not path.exists():
            continue
        path.unlink()
        changed = True
    return changed


def _ensure_dependency_in_manifest(
    manifest: dict[str, Any],
    package_name: str,
    package_url: str,
) -> bool:
    dependencies = manifest.setdefault("dependencies", {})
    if not isinstance(dependencies, dict):
        raise ValueError("manifest.json dependencies must be a JSON object.")
    current_value = dependencies.get(package_name)
    current = str(current_value or "").strip()
    if current != "":
        return False
    dependencies[package_name] = package_url
    return True


def ensure_unity_bridge_upm_dependency(
    project_path: Path,
    package_name: str = DEFAULT_UNITY_BRIDGE_PACKAGE_NAME,
    package_url: str = DEFAULT_UNITY_BRIDGE_PACKAGE_URL,
) -> bool:
    project_root = Path(project_path).resolve()
    manifest_path = project_root / "Packages" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Unity manifest.json not found: {manifest_path}. "
            "Set Unity Project Path to a valid Unity project."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8") or "{}")
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json root must be a JSON object.")

    manifest_changed = _ensure_dependency_in_manifest(
        manifest,
        package_name=package_name,
        package_url=package_url,
    )
    if manifest_changed:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    legacy_changed = _remove_legacy_bridge_script(project_root)
    return manifest_changed or legacy_changed
