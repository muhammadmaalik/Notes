"""User profile (configs/profile.yaml) -> text block for the system prompt."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Never render these, even if someone adds them to the file.
SENSITIVE_KEYS = {"immigration", "citizenship", "visa", "ssn", "passport", "password", "bank", "medical"}


def load_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {k: v for k, v in data.items() if str(k).lower() not in SENSITIVE_KEYS}


def _fmt(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(_fmt(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_fmt(v)}" for k, v in value.items())
    return str(value)


def render_profile(profile: dict[str, Any]) -> str:
    if not profile:
        return ""
    lines = []
    for key, value in profile.items():
        if key in ("timezone",):
            continue
        lines.append(f"- {key.replace('_', ' ').capitalize()}: {_fmt(value)}")
    return "\n".join(lines)


def user_timezone(profile: dict[str, Any], default: str = "America/New_York") -> str:
    return str(profile.get("timezone") or default)
