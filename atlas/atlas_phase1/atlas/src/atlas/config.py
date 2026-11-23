"""Load a YAML profile (laptop / homepc / your own) plus optional <profile>.local.yaml overrides."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("ATLAS_CONFIG_DIR", REPO_ROOT / "configs"))
ROLES = ("fast", "reasoning", "deep", "embed")

DEFAULT_MEMORY = {"enabled": True, "extract": True, "top_k": 6, "min_similarity": 0.35, "history_turns": 10}
DEFAULT_RESEARCH = {"subqueries": 5, "results_per_query": 5, "max_sources": 8, "max_chars_per_source": 6000,
                    "parallel": 2, "think": "medium", "num_ctx": 32768, "formats": ["md"]}


@dataclass
class Config:
    profile: str
    ollama_host: str
    timeout_s: float
    keep_alive: str
    models: dict[str, str]
    hosts: dict[str, str]
    model_options: dict[str, dict[str, Any]]
    llm_classify: bool
    long_prompt_chars: int
    db_path: Path
    workspace: Path
    reports_dir: Path
    profile_path: Path
    max_tool_steps: int
    system_prompt: str
    memory: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_MEMORY))
    research: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_RESEARCH))
    deep_unload_fast: bool = False
    voice_enabled: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def model_for(self, role: str) -> str:
        if role == "deep" and "deep" not in self.models:
            role = "reasoning"
        if role not in self.models:
            raise KeyError(f"No model configured for role '{role}' in profile '{self.profile}'")
        return self.models[role]

    def host_for(self, role: str) -> str:
        if role == "deep" and "deep" not in self.models:
            role = "reasoning"
        return self.hosts.get(role, self.ollama_host)

    def options_for(self, role: str) -> dict[str, Any]:
        if role == "deep" and "deep" not in self.model_options:
            role = "reasoning"
        return dict(self.model_options.get(role, {}))


def _expand(p: str) -> Path:
    """Expand ~ and $VARS; relative paths are relative to the repo root."""
    path = Path(os.path.expandvars(os.path.expanduser(p)))
    return path if path.is_absolute() else (REPO_ROOT / path)


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(profile: str | None = None, path: str | Path | None = None) -> Config:
    """Profile order: explicit path > --profile > $ATLAS_PROFILE > 'laptop'."""
    if path is None:
        profile = profile or os.environ.get("ATLAS_PROFILE", "laptop")
        path = CONFIG_DIR / f"{profile}.yaml"
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    local = path.with_name(path.stem + ".local.yaml")
    if local.exists():
        data = deep_merge(data, yaml.safe_load(local.read_text()) or {})

    ollama = data.get("ollama", {})
    default_host = os.environ.get("OLLAMA_HOST_URL", ollama.get("host", "http://127.0.0.1:11434"))
    models, hosts = {}, {}
    for role, spec in (data.get("models") or {}).items():
        if isinstance(spec, dict):
            models[role] = str(spec["name"])
            hosts[role] = str(spec.get("host") or default_host)
        else:
            models[role] = str(spec)
            hosts[role] = default_host
    router = data.get("router", {})
    paths = data.get("paths", {})
    agent = data.get("agent", {})
    return Config(
        profile=data.get("profile", path.stem),
        ollama_host=default_host,
        timeout_s=float(ollama.get("timeout_s", 300)),
        keep_alive=str(ollama.get("keep_alive", "10m")),
        models=models,
        hosts=hosts,
        model_options=dict(data.get("model_options", {})),
        llm_classify=bool(router.get("llm_classify", False)),
        long_prompt_chars=int(router.get("long_prompt_chars", 700)),
        db_path=_expand(os.environ.get("ATLAS_DB", paths.get("db", "data/atlas.db"))),
        workspace=_expand(paths.get("workspace", "data/workspace")),
        reports_dir=_expand(os.environ.get("ATLAS_REPORTS", paths.get("reports", "data/reports"))),
        profile_path=_expand(os.environ.get("ATLAS_USER_PROFILE", paths.get("profile", "configs/profile.yaml"))),
        max_tool_steps=int(agent.get("max_tool_steps", 5)),
        system_prompt=str(agent.get("system_prompt", "")).strip(),
        memory={**DEFAULT_MEMORY, **(data.get("memory") or {})},
        research={**DEFAULT_RESEARCH, **(data.get("research") or {})},
        deep_unload_fast=bool((data.get("deep") or {}).get("unload_fast", False)),
        voice_enabled=bool((data.get("voice") or {}).get("enabled", False)),
        raw=data,
    )
