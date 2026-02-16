"""Hotkey parsing and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_STOP_HOTKEY_LABEL = "Alt+Shift+F12"
FALLBACK_STOP_HOTKEY_LABELS = (
    "Alt+Shift+F12",
    "Ctrl+Shift+F12",
    "Ctrl+Alt+F12",
)

_MODIFIER_ORDER = ("CTRL", "ALT", "SHIFT")
_MODIFIER_LABELS = {
    "CTRL": "Ctrl",
    "ALT": "Alt",
    "SHIFT": "Shift",
}
_MODIFIER_ALIASES = {
    "CTRL": "CTRL",
    "CONTROL": "CTRL",
    "ALT": "ALT",
    "SHIFT": "SHIFT",
}


@dataclass(frozen=True, slots=True)
class HotkeySpec:
    label: str
    bind: str
    main_key: str
    required_modifiers: frozenset[str]


def parse_hotkey_label(label: str) -> HotkeySpec:
    """Parse user-facing hotkey text (example: Alt+Shift+F12)."""
    tokens = [part.strip().upper() for part in str(label or "").split("+") if part.strip() != ""]
    if not tokens:
        raise ValueError("Hotkey must not be empty.")

    modifiers: set[str] = set()
    main_key = ""
    for token in tokens:
        normalized_modifier = _MODIFIER_ALIASES.get(token)
        if normalized_modifier is not None:
            modifiers.add(normalized_modifier)
            continue
        if main_key != "":
            raise ValueError("Hotkey must contain exactly one main key.")
        main_key = _normalize_main_key(token)

    if main_key == "":
        raise ValueError("Hotkey must include one main key.")
    if not modifiers:
        raise ValueError("Hotkey must include at least one modifier (Ctrl/Alt/Shift).")

    ordered_modifiers = tuple(mod for mod in _MODIFIER_ORDER if mod in modifiers)
    label_parts = [_MODIFIER_LABELS[modifier] for modifier in ordered_modifiers]
    label_parts.append(main_key)
    normalized_label = "+".join(label_parts)

    bind_parts = [f"<{modifier.lower()}>" for modifier in ordered_modifiers]
    bind_parts.append(f"<{main_key.lower()}>")
    bind = "+".join(bind_parts)

    return HotkeySpec(
        label=normalized_label,
        bind=bind,
        main_key=main_key,
        required_modifiers=frozenset(ordered_modifiers),
    )


def _normalize_main_key(token: str) -> str:
    value = str(token or "").strip().upper()
    if len(value) == 1 and value.isalnum():
        return value
    if value.startswith("F") and value[1:].isdigit():
        number = int(value[1:])
        if 1 <= number <= 24:
            return value
    raise ValueError(f"Unsupported hotkey main key: {token}")
