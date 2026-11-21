# Atlas v0

Atlas is a local, multi-model personal assistant that runs on your own machines through
[Ollama](https://ollama.com). v0 is intentionally small. It has:

- **Router**: sends each message to a **fast** model (chat, quick facts) or a **reasoning** model
  (math, code, multi-step). It uses a free heuristic first; if `router.llm_classify: true` and the
  heuristic is unsure, it asks the fast model to classify.
- **Tools with permission tiers**:
  - `read`: runs automatically (`web_search`, `read_file`, `list_dir`, `deadlines_list`)
  - `change`: asks you **y/N** first (`write_file` (only inside `data/workspace`, never overwrites), `deadlines_add`)
  - `forbidden`: deletes, sudo, sending messages, payments. These **cannot be registered at all** in v0.
  - Every tool call (allowed or denied) is written to the `tool_log` table.
- **Memory**: SQLite at `data/atlas.db` (conversations, messages, deadlines, tool log).
- **CLI**: `atlas chat`, `atlas ask`, `atlas deadlines add/list/done`, `atlas history`, `atlas doctor`, `atlas serve`.
- **Gateway**: FastAPI on `127.0.0.1:8765` (`/health`, `/chat`, `/deadlines`). Over HTTP there is
  no one to answer y/N, so `change` tools are always denied there.
- **Profiles**: `configs/laptop.yaml` and `configs/homepc.yaml` choose the models per machine.

The repo lives at `/home/maalik/Desktop/Notes/Notes/atlas`. All data stays inside it, in `atlas/data/`.

## Quick start (Fedora 44 laptop, RTX 5060 Laptop GPU 8 GB)

```bash
cd /home/maalik/Desktop/Notes/Notes/atlas

# 1) NVIDIA driver must work first. If this prints your GPU, skip to step 2.
nvidia-smi

#    If not: install it from RPM Fusion, then reboot
sudo dnf install -y \
  https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
  https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
sudo dnf upgrade --refresh -y
sudo dnf install -y akmod-nvidia xorg-x11-drv-nvidia-cuda
mokutil --sb-state                       # if "SecureBoot enabled":
sudo kmodgenca -a
sudo mokutil --import /etc/pki/akmods/certs/public_key.der   # pick a short one-time password
modinfo -F version nvidia                # wait until this prints a version (akmod build ~5 min)
sudo reboot                              # blue MOK screen: Enroll MOK -> Continue -> Yes -> password

# 2) Everything else (Ollama, uv, Python deps, model pulls, health check)
bash scripts/setup_fedora.sh laptop

# 3) Use it
uv run atlas chat
```

## Daily use

```bash
cd /home/maalik/Desktop/Notes/Notes/atlas
uv run atlas chat                       # /fast /reason /auto /new /exit;  -v shows routing reasons
uv run atlas ask "Derive the period of a physical pendulum" -v
uv run atlas deadlines add "PHY 251 lab report" --due friday --course "PHY 251"
uv run atlas deadlines add "MEC 262 HW 7" --due "2026-12-03 17:00"
uv run atlas deadlines list             # --all to include done
uv run atlas deadlines done 1           # marks done; nothing is ever deleted
uv run atlas history
uv run atlas doctor                     # is Ollama up, are models pulled?
uv run atlas serve                      # http://127.0.0.1:8765/docs
```

Due dates accept: `YYYY-MM-DD [HH:MM]`, `today`, `tomorrow`, `+3d`, or a weekday (`friday`).
The default time is 23:59.

Optional: `alias atlas='uv run --project /home/maalik/Desktop/Notes/Notes/atlas atlas'` in `~/.bashrc`.

## Models per profile

| Profile | fast | reasoning | embed (future RAG) |
|---|---|---|---|
| `laptop` (8 GB) | `qwen3.5:4b` (3.3 GB) | `qwen3.5:9b` (6.6 GB) | `qwen3-embedding:0.6b` |
| `homepc` (5070 Ti + 3060) | `qwen3.5:9b` | `gpt-oss:20b` | `qwen3-embedding:0.6b` |

On 8 GB, only one of the two chat models fits on the GPU at a time. Ollama swaps them in a few
seconds when the router switches. Optional heavier laptop model: `ollama pull gpt-oss:20b`
(14 GB). It runs with partial CPU offload, so it is slower but smarter. Put it in
`models.reasoning` to try it.

To switch profiles, use `--profile homepc` or `export ATLAS_PROFILE=homepc`. To make your own,
copy a YAML file into `configs/` and use its file name as the profile.

## Tests

```bash
uv run pytest -q          # uses a fake Ollama, no GPU or network needed
```

## Layout

```
atlas/
├── configs/            laptop.yaml, homepc.yaml  (models, options, paths)
├── data/               atlas.db + workspace/  (created on first run, gitignored)
├── scripts/setup_fedora.sh
├── src/atlas/
│   ├── cli.py          typer CLI
│   ├── gateway.py      FastAPI app
│   ├── agent.py        route -> chat -> tool loop -> memory
│   ├── router.py       heuristic + optional LLM classify
│   ├── ollama_client.py
│   ├── memory.py       SQLite
│   ├── dates.py
│   └── tools/          registry.py (tiers), builtin.py (starter tools)
└── tests/
```

## Fedora notes

- **SELinux**: Ollama installs as a system service. Its models live in `/usr/share/ollama/.ollama`.
  If you move them (`OLLAMA_MODELS`), restore labels with `sudo restorecon -Rv <dir>`. When you
  later run containers with Podman, add `:Z` to volume mounts (`-v ./data:/data:Z`).
- **GPU in containers (later)**: install `nvidia-container-toolkit` from NVIDIA's repo, run
  `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`, then
  `podman run --device nvidia.com/gpu=all --security-opt=label=disable ...`.
- **Hybrid laptop graphics**: Ollama uses CUDA directly, so it works fine on Optimus laptops.
  Check `nvidia-smi` while chatting to confirm the model is on the GPU.
- **Kernel updates**: akmods rebuilds the NVIDIA module on boot. After a big kernel update,
  wait a minute before launching anything heavy.

## Roadmap after v0

Phase 1 adds a home PC profile with GPU pinning and Tailscale access from the laptop. Then:
research + docs tools (SearXNG, pandoc), calendar and Brightspace iCal sync, voice, computer
control via a confirm-first "hands" agent, the watch link (BLE + LoRa), and local QLoRA
fine-tuning with Unsloth on logged conversations.
