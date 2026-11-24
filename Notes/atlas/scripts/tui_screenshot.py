"""Render the Atlas TUI with mocked data (no Ollama / GPU needed) and save an SVG screenshot.

    uv run python scripts/tui_screenshot.py out.svg
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

from atlas.config import load_config
from atlas.memory import Memory
from atlas.ollama_client import ClientPool, OllamaClient
from atlas.tui import AtlasApp

ANSWER = """Here's the short version for **PsiSat**'s attitude loop:

1. Model the sat as a rigid body: `I·ω̇ + ω × (I·ω) = τ`
2. Use a **quaternion PD** controller: `τ = -Kp·q_err,vec - Kd·ω`
3. Tune on the linearized axis first, then check saturation of the reaction wheels.

| Gain | Start value | Why |
|------|-------------|-----|
| Kp   | 0.02 N·m    | ~60 s settle |
| Kd   | 0.15 N·m·s  | ζ ≈ 0.8 |

Want me to write the sim in Python with a plot?"""

GPUS = [
    {"index": "0", "name": "RTX 5070 Ti", "util": 71.0, "mem_used": 13900.0, "mem_total": 16303.0, "temp": 63.0,
     "power": 231.0},
    {"index": "1", "name": "RTX 3060", "util": 9.0, "mem_used": 4300.0, "mem_total": 12288.0, "temp": 47.0,
     "power": 41.0},
]


def handler(req: httpx.Request) -> httpx.Response:
    if req.url.path == "/api/chat":
        body = json.loads(req.content)
        msg = {"role": "assistant", "content": ANSWER,
               "thinking": "Maalik asked about attitude control for PsiSat; keep it concise, give gains."}
        if not body.get("stream"):
            return httpx.Response(200, json={"message": msg, "done": True})
        lines = [{"message": {"role": "assistant", "content": "", "thinking": msg["thinking"]}, "done": False},
                 {"message": {"role": "assistant", "content": ANSWER}, "done": False},
                 {"message": {"role": "assistant", "content": ""}, "done": True}]
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines).encode())
    if req.url.path == "/api/embed":
        n = len(json.loads(req.content)["input"])
        return httpx.Response(200, json={"embeddings": [[0.1] * 8] * n})
    return httpx.Response(200, json={"models": []})


async def main(out: str) -> None:
    tmp = Path(tempfile.mkdtemp())
    os.environ["ATLAS_DB"] = str(tmp / "atlas.db")
    os.environ["ATLAS_REPORTS"] = str(tmp / "reports")
    cfg = load_config("homepc")
    cfg.memory["extract"] = False
    mem = Memory(cfg.db_path)
    for title, due in [("PHY 251 lab report", "2026-11-25 23:59"), ("MEC 260 problem set 9", "2026-11-26 17:00"),
                       ("Robotics FEA review: chassis bracket", "2026-11-30 14:00"),
                       ("DARPA Lift: weight budget v2", "2026-12-04 23:59")]:
        mem.add_deadline(title, due)
    for f in ["Maalik is the FEA Lead at Stony Brook Robotics", "Prefers concise, direct answers",
              "PsiSat uses 3 reaction wheels + magnetorquers", "Eats halal only"]:
        mem.add_fact(f, None, source="user")
    old = mem.new_conversation()
    mem.add_message(old, "user", "research Voyager 1 mission design")
    mem.add_message(old, "assistant", "Report saved.", model="gpt-oss:20b", route_reason="research")
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "2026-11-21-voyager-1-mission-design.md").write_text("# Voyager 1\n")
    client = OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    pool = ClientPool.single(cfg, client)
    status = [{"host": "http://127.0.0.1:11434", "roles": ["reasoning", "deep"], "ok": True, "error": "",
               "loaded": [{"name": "gpt-oss:20b", "size": 13.8e9, "size_vram": 13.8e9}]},
              {"host": "http://127.0.0.1:11435", "roles": ["fast", "embed"], "ok": True, "error": "",
               "loaded": [{"name": "qwen3.5:9b", "size": 6.6e9, "size_vram": 6.6e9},
                          {"name": "qwen3-embedding:0.6b", "size": 1.1e9, "size_vram": 1.1e9}]}]
    app = AtlasApp(cfg, pool, mem, gpu_probe=lambda: GPUS, status_probe=lambda: status, poll_seconds=2)
    async with app.run_test(size=(150, 44)) as pilot:
        app.set_mode("reasoning")
        app.handle_text("How should I do attitude control for PsiSat? Short answer.")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause(0.3)
        app.action_show_tab("tab-system")
        await pilot.pause(0.3)
        app.query_one("#prompt").value = "/res"
        app.query_one("#prompt").focus()
        await pilot.pause(0.3)
        app.save_screenshot(out)
    print(out)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "atlas_tui.svg"))
