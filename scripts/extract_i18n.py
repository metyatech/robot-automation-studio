"""Extract i18n translations from i18n.py into react-i18next JSON files.

Usage:
    python scripts/extract_i18n.py

Outputs:
    tauri-app/src/locales/en.json
    tauri-app/src/locales/ja.json

Transformation rules:
    - Dot-separated keys are expanded into nested JSON objects.
      e.g.  "app.button.save"  ->  {"app": {"button": {"save": "..."}}}
    - Python {variable} interpolation is converted to i18next {{variable}} format.
      e.g.  "Stop: {hotkey}"  ->  "Stop: {{hotkey}}"
    - All entries are preserved, including empty strings.
    - Multi-line Python string concatenations are collapsed to a single string.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Ensure the src package is importable when running from the project root.
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from robot_automation_studio.i18n import _TRANSLATIONS  # noqa: E402


def _convert_placeholders(text: str) -> str:
    """Convert Python {var} format placeholders to i18next {{var}} format.

    Only bare {identifier} patterns are converted; already-doubled braces
    ({{ or }}) and non-identifier placeholders are left unchanged.
    """
    # Replace single-brace Python placeholders with double-brace i18next ones.
    # Match {word_chars} that are not already doubled.
    result = re.sub(r"(?<!\{)\{(\w+)\}(?!\})", r"{{\1}}", text)
    return result


def _set_nested(obj: dict, keys: list[str], value: str) -> None:
    """Recursively set a nested dict value from a list of key parts.

    When a key segment already holds a leaf string but a deeper key also needs
    it as a namespace (e.g. "app.tab.step" and "app.tab.step.tooltip"), the
    existing leaf is moved under the special sub-key "_self" so both can
    coexist in the nested structure.  This is a recognised i18next pattern.
    """
    for key in keys[:-1]:
        if key not in obj:
            obj[key] = {}
        elif isinstance(obj[key], str):
            # Promote existing leaf to {"_self": <leaf>} dict
            obj[key] = {"_self": obj[key]}
        obj = obj[key]
    leaf_key = keys[-1]
    if leaf_key in obj and isinstance(obj[leaf_key], dict):
        # The key already exists as a namespace dict; store value under _self
        obj[leaf_key]["_self"] = value
    else:
        obj[leaf_key] = value


def build_locale_tree(locale_code: str) -> dict:
    """Build a nested dict for the given locale from _TRANSLATIONS."""
    tree: dict = {}
    for dot_key, translations in _TRANSLATIONS.items():
        raw_value = translations.get(locale_code, "")
        # Normalize the value: it may be a plain str or a multi-line concatenation
        # (Python parses those at import time, so it arrives as a plain str here).
        value = _convert_placeholders(raw_value)
        keys = dot_key.split(".")
        _set_nested(tree, keys, value)
    return tree


def main() -> None:
    output_dir = project_root / "tauri-app" / "src" / "locales"
    output_dir.mkdir(parents=True, exist_ok=True)

    total_keys = len(_TRANSLATIONS)
    print(f"Extracting {total_keys} translation keys...")

    for locale_code in ("en", "ja"):
        tree = build_locale_tree(locale_code)
        out_path = output_dir / f"{locale_code}.json"
        out_path.write_text(
            json.dumps(tree, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  Written: {out_path}")

    print("Done.")


if __name__ == "__main__":
    main()
