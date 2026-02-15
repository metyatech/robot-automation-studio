import json

from robot_automation_studio.upm import (
    DEFAULT_UNITY_BRIDGE_PACKAGE_NAME,
    DEFAULT_UNITY_BRIDGE_PACKAGE_URL,
    ensure_unity_bridge_upm_dependency,
    has_unity_bridge_package_script_meta,
    install_legacy_unity_bridge_script,
)


def test_ensure_unity_bridge_upm_dependency_adds_dependency(tmp_path) -> None:
    project_path = tmp_path / "sample-project"
    packages_dir = project_path / "Packages"
    packages_dir.mkdir(parents=True)
    manifest_path = packages_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"dependencies": {"com.unity.textmeshpro": "3.0.6"}}, indent=2),
        encoding="utf-8",
    )

    changed = ensure_unity_bridge_upm_dependency(project_path)

    assert changed is True
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["dependencies"][DEFAULT_UNITY_BRIDGE_PACKAGE_NAME] == (
        DEFAULT_UNITY_BRIDGE_PACKAGE_URL
    )


def test_ensure_unity_bridge_upm_dependency_is_idempotent(tmp_path) -> None:
    project_path = tmp_path / "sample-project"
    packages_dir = project_path / "Packages"
    packages_dir.mkdir(parents=True)
    manifest_path = packages_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"dependencies": {DEFAULT_UNITY_BRIDGE_PACKAGE_NAME: DEFAULT_UNITY_BRIDGE_PACKAGE_URL}},
            indent=2,
        ),
        encoding="utf-8",
    )

    changed = ensure_unity_bridge_upm_dependency(project_path)

    assert changed is False


def test_ensure_unity_bridge_upm_dependency_does_not_overwrite_existing_source(
    tmp_path,
) -> None:
    project_path = tmp_path / "sample-project"
    packages_dir = project_path / "Packages"
    packages_dir.mkdir(parents=True)
    manifest_path = packages_dir / "manifest.json"
    existing_url = "file:../local-packages/unity-automation-bridge"
    manifest_path.write_text(
        json.dumps(
            {"dependencies": {DEFAULT_UNITY_BRIDGE_PACKAGE_NAME: existing_url}},
            indent=2,
        ),
        encoding="utf-8",
    )

    changed = ensure_unity_bridge_upm_dependency(project_path)

    assert changed is False
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["dependencies"][DEFAULT_UNITY_BRIDGE_PACKAGE_NAME] == existing_url


def test_ensure_unity_bridge_upm_dependency_removes_legacy_bridge_script(tmp_path) -> None:
    project_path = tmp_path / "sample-project"
    packages_dir = project_path / "Packages"
    packages_dir.mkdir(parents=True)
    manifest_path = packages_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"dependencies": {DEFAULT_UNITY_BRIDGE_PACKAGE_NAME: DEFAULT_UNITY_BRIDGE_PACKAGE_URL}},
            indent=2,
        ),
        encoding="utf-8",
    )
    legacy_script = project_path / "Assets" / "Editor" / "RobotFrameworkUnityBridge.cs"
    legacy_meta = project_path / "Assets" / "Editor" / "RobotFrameworkUnityBridge.cs.meta"
    legacy_script.parent.mkdir(parents=True)
    legacy_script.write_text("// legacy bridge", encoding="utf-8")
    legacy_meta.write_text("fileFormatVersion: 2", encoding="utf-8")

    changed = ensure_unity_bridge_upm_dependency(project_path)

    assert changed is True
    assert not legacy_script.exists()
    assert not legacy_meta.exists()


def test_has_unity_bridge_package_script_meta_detects_cache_meta(tmp_path) -> None:
    project_path = tmp_path / "sample-project"
    meta_path = (
        project_path
        / "Library"
        / "PackageCache"
        / "com.metyatech.unity-automation-bridge@abc123"
        / "Editor"
        / "RobotFrameworkUnityBridge.cs.meta"
    )
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text("fileFormatVersion: 2", encoding="utf-8")

    assert has_unity_bridge_package_script_meta(project_path) is True


def test_install_legacy_unity_bridge_script_writes_script(tmp_path) -> None:
    project_path = tmp_path / "sample-project"
    changed_first = install_legacy_unity_bridge_script(project_path)
    changed_second = install_legacy_unity_bridge_script(project_path)

    script_path = project_path / "Assets" / "Editor" / "RobotFrameworkUnityBridge.cs"
    assert changed_first is True
    assert changed_second is False
    assert script_path.exists()
