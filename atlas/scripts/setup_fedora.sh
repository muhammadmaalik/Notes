#!/usr/bin/env bash
# Atlas v0 setup for Fedora 44 (laptop or home PC).
# Usage:  cd /home/maalik/Desktop/Notes/Notes/atlas && bash scripts/setup_fedora.sh [laptop|homepc]
# Safe to re-run. It never installs the NVIDIA driver for you (that needs a reboot
# and possibly Secure Boot key enrollment); it tells you the exact commands instead.
set -euo pipefail

PROFILE="${1:-laptop}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32m✓ %s\033[0m\n' "$*"; }
warn() { printf '   \033[33m! %s\033[0m\n' "$*"; }

[[ -f "configs/${PROFILE}.yaml" ]] || { echo "No configs/${PROFILE}.yaml"; exit 1; }
say "Atlas setup · profile=${PROFILE} · repo=${REPO_DIR}"

# ---------------------------------------------------------------- 1. OS check
if [[ -r /etc/os-release ]]; then . /etc/os-release; fi
if [[ "${ID:-}" != "fedora" ]]; then warn "This script targets Fedora (found: ${PRETTY_NAME:-unknown}). Continuing anyway."; else ok "${PRETTY_NAME}"; fi

say "Base packages"
sudo dnf install -y git curl python3 pandoc nvtop >/dev/null && ok "git curl python3 pandoc nvtop"

# ---------------------------------------------------------------- 2. NVIDIA driver
say "NVIDIA driver"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | sed 's/^/   ✓ /'
else
  warn "nvidia-smi not working. Install the driver from RPM Fusion, then reboot and re-run this script:"
  cat <<'NV'
     sudo dnf install -y \
       https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
       https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
     sudo dnf upgrade --refresh -y
     sudo dnf install -y akmod-nvidia xorg-x11-drv-nvidia-cuda
     # Secure Boot on?  (mokutil --sb-state)  -> enroll the akmods key once:
     sudo kmodgenca -a
     sudo mokutil --import /etc/pki/akmods/certs/public_key.der   # set a short one-time password
     # wait ~5 min for the module to build:  modinfo -F version nvidia
     sudo reboot     # at the blue MOK screen: Enroll MOK -> Continue -> Yes -> password
NV
  exit 1
fi

# ---------------------------------------------------------------- 3. Ollama
say "Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable --now ollama >/dev/null 2>&1 || true
for i in {1..20}; do curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null && ok "ollama $(ollama --version 2>/dev/null | awk '{print $NF}') running on 127.0.0.1:11434" \
  || { warn "Ollama is not answering. Check: systemctl status ollama"; exit 1; }

# ---------------------------------------------------------------- 4. uv + Python deps
say "uv + Python 3.12"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv python install 3.12 >/dev/null
uv sync
ok "virtualenv ready at ${REPO_DIR}/.venv"

# ---------------------------------------------------------------- 5. Models
say "Pulling models listed in configs/${PROFILE}.yaml"
MODELS=$(uv run python -c "
from atlas.config import load_config
print(' '.join(dict.fromkeys(load_config('${PROFILE}').models.values())))")
for m in $MODELS; do
  echo "   pulling $m ..."
  ollama pull "$m"
done
ok "models: $MODELS"

# ---------------------------------------------------------------- 6. Data dir + check
mkdir -p data/workspace
say "Health check"
ATLAS_PROFILE="$PROFILE" uv run atlas doctor

cat <<DONE

Done. Next:
  cd ${REPO_DIR}
  uv run atlas chat                 # talk to Atlas (Ctrl+D to quit)
  uv run atlas deadlines add "PHY 251 lab report" --due friday --course "PHY 251"
  uv run atlas deadlines list
Data lives in ${REPO_DIR}/data (SQLite db + workspace).
DONE
