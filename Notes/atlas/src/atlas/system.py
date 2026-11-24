"""Live system info for the TUI: GPU stats (nvidia-smi) and Ollama status (/api/tags, /api/ps)."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from .ollama_client import ClientPool, OllamaError

GPU_QUERY = "index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw"


def _num(x: str) -> float | None:
    try:
        return float(x)
    except ValueError:
        return None


def gpu_stats(smi: str = "nvidia-smi") -> list[dict[str, Any]] | None:
    """Per-GPU stats, or None when nvidia-smi is missing or fails."""
    if not shutil.which(smi):
        return None
    try:
        out = subprocess.run([smi, f"--query-gpu={GPU_QUERY}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        gpus.append({"index": parts[0], "name": parts[1].replace("NVIDIA GeForce ", ""),
                     "util": _num(parts[2]), "mem_used": _num(parts[3]), "mem_total": _num(parts[4]),
                     "temp": _num(parts[5]), "power": _num(parts[6]) if len(parts) > 6 else None})
    return gpus


def ollama_status(cfg, pool: ClientPool) -> list[dict[str, Any]]:
    """One entry per configured Ollama host: reachable?, which roles, loaded models."""
    roles_by_host: dict[str, list[str]] = {}
    for role in cfg.models:
        roles_by_host.setdefault(cfg.host_for(role), []).append(role)
    out = []
    for host, roles in sorted(roles_by_host.items()):
        entry: dict[str, Any] = {"host": host, "roles": roles, "ok": False, "loaded": [], "error": ""}
        try:
            client = pool.get(host)
            entry["loaded"] = client.ps()
            entry["ok"] = True
        except OllamaError as e:
            entry["error"] = str(e)
        except Exception as e:  # noqa: BLE001 - status must never crash the UI
            entry["error"] = f"{e.__class__.__name__}: {e}"
        out.append(entry)
    return out
