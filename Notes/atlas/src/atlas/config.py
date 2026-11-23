"""Load a YAML profile (laptop / homepc / your own) into a small dataclass."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("ATLAS_CONFIG_DIR", REPO_ROOT / "configs"))


@dataclass
class Config:
    profile: str
    ollama_host: str
    timeout_s: float
    keep_alive: str
    models: dict[str, str]
    model_options: dict[str, dict[str, Any]]
    llm_classify: bool
    long_prompt_chars: int
    db_path: Path
    workspace: Path
    max_tool_steps: int
    system_prompt: str
    raw: dict[str, Any] = field(default_factory=dict)

    def model_for(self, role: str) -> str:
        if role not in self.models:
            raise KeyError(f"No model configured for role '{role}' in profile '{self.profile}'")
        return self.models[role]

    def options_for(self, role: str) -> dict[str, Any]:
        return dict(self.model_options.get(role, {}))


def _expand(p: str) -> Path:
    """Expand ~ and $VARS; relative paths are relative to the repo root."""
    path = Path(os.path.expandvars(os.path.expanduser(p)))
    return path if path.is_absolute() else (REPO_ROOT / path)


def load_config(profile: str | None = None, path: str | Path | None = None) -> Config:
    """Profile order: explicit path > --profile > $ATLAS_PROFILE > 'laptop'."""
    if path is None:
        profile = profile or os.environ.get("ATLAS_PROFILE", "laptop")
        path = CONFIG_DIR / f"{profile}.yaml"
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}

    ollama = data.get("ollama", {})
    router = data.get("router", {})
    paths = data.get("paths", {})
    agent = data.get("agent", {})
    return Config(
        profile=data.get("profile", path.stem),
        ollama_host=os.environ.get("OLLAMA_HOST_URL", ollama.get("host", "http://127.0.0.1:11434")),
        timeout_s=float(ollama.get("timeout_s", 300)),
        keep_alive=str(ollama.get("keep_alive", "10m")),
        models=dict(data.get("models", {})),
        model_options=dict(data.get("model_options", {})),
        llm_classify=bool(router.get("llm_classify", False)),
        long_prompt_chars=int(router.get("long_prompt_chars", 700)),
        db_path=_expand(os.environ.get("ATLAS_DB", paths.get("db", "data/atlas.db"))),
        workspace=_expand(paths.get("workspace", "data/workspace")),
        max_tool_steps=int(agent.get("max_tool_steps", 5)),
        system_prompt=str(agent.get("system_prompt", "You are Atlas, a helpful assistant.")).strip(),
        raw=data,
    )
