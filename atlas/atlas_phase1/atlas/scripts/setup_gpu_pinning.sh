#!/usr/bin/env bash
# Pin Atlas roles to GPUs with two Ollama instances (home PC: RTX 5070 Ti + RTX 3060).
#
#   :11434  ollama.service       -> sees 5070 Ti first, then 3060   (reasoning gpt-oss:20b, deep qwen3.8:27b)
#   :11435  ollama-fast.service  -> sees ONLY the 3060               (fast qwen3.5:9b + embeddings)
#
# GPUs are selected by UUID (stable), with CUDA_DEVICE_ORDER=PCI_BUS_ID. Plain indexes can differ
# between nvidia-smi and CUDA, which is why this script never uses them.
#
# Usage:
#   bash scripts/setup_gpu_pinning.sh            # dry run: show what would be written
#   bash scripts/setup_gpu_pinning.sh --apply    # write units (sudo), restart, write configs/homepc.local.yaml
#   bash scripts/setup_gpu_pinning.sh --undo     # remove the units/drop-in, back to one instance
# Options: --strict  main instance sees only the 5070 Ti (deep mode then offloads to CPU instead of the 3060)
set -euo pipefail

MODE=dry; STRICT=0
for a in "$@"; do
  case "$a" in
    --apply) MODE=apply ;; --undo) MODE=undo ;; --strict) STRICT=1 ;;
    -h|--help) sed -n 2,16p "$0"; exit 0 ;;
    *) echo "unknown option $a"; exit 2 ;;
  esac
done
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SMI="${NVIDIA_SMI:-nvidia-smi}"
FAST_NAME="${ATLAS_FAST_GPU:-3060}"     # substring of the GPU name for the fast instance
MAIN_NAME="${ATLAS_MAIN_GPU:-5070}"     # substring of the GPU name for the main instance
DROPIN_DIR=/etc/systemd/system/ollama.service.d
DROPIN="$DROPIN_DIR/10-atlas-gpu.conf"
FAST_UNIT=/etc/systemd/system/ollama-fast.service
LOCAL_CFG="$REPO_DIR/configs/homepc.local.yaml"

if [[ "$MODE" == undo ]]; then
  sudo systemctl disable --now ollama-fast.service 2>/dev/null || true
  sudo rm -f "$FAST_UNIT" "$DROPIN"
  sudo systemctl daemon-reload && sudo systemctl restart ollama
  echo "Back to a single Ollama on :11434. Remove the 'host: ...11435' lines from $LOCAL_CFG if present."
  exit 0
fi

echo "GPUs (nvidia-smi):"
"$SMI" -L
mapfile -t ROWS < <("$SMI" --query-gpu=name,uuid,pci.bus_id --format=csv,noheader)
FAST_UUID=""; MAIN_UUID=""
for row in "${ROWS[@]}"; do
  name="${row%%,*}"; rest="${row#*, }"; uuid="${rest%%,*}"
  [[ "$name" == *"$FAST_NAME"* && -z "$FAST_UUID" ]] && FAST_UUID="$uuid"
  [[ "$name" == *"$MAIN_NAME"* && -z "$MAIN_UUID" ]] && MAIN_UUID="$uuid"
done
[[ -n "$FAST_UUID" && -n "$MAIN_UUID" ]] || {
  echo "Could not find both GPUs (looking for '$MAIN_NAME' and '$FAST_NAME'). Set ATLAS_MAIN_GPU / ATLAS_FAST_GPU."; exit 1; }
echo "main (11434): $MAIN_UUID   fast (11435): $FAST_UUID"

MAIN_VISIBLE="$MAIN_UUID,$FAST_UUID"; [[ "$STRICT" == 1 ]] && MAIN_VISIBLE="$MAIN_UUID"
OLLAMA_BIN="$(command -v ollama || echo /usr/local/bin/ollama)"
MODELS_DIR="$( { systemctl show ollama -p Environment 2>/dev/null || true; } | tr ' ' '\n' | sed -n 's/^OLLAMA_MODELS=//p' || true)"
MODELS_DIR="${MODELS_DIR:-/usr/share/ollama/.ollama/models}"

DROPIN_TXT="[Service]
Environment=\"CUDA_DEVICE_ORDER=PCI_BUS_ID\"
Environment=\"CUDA_VISIBLE_DEVICES=$MAIN_VISIBLE\"
Environment=\"OLLAMA_HOST=127.0.0.1:11434\"
Environment=\"OLLAMA_MAX_LOADED_MODELS=2\"
"
FAST_TXT="[Unit]
Description=Ollama fast instance for Atlas (RTX 3060, port 11435)
After=network-online.target ollama.service

[Service]
ExecStart=$OLLAMA_BIN serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment=\"HOME=/usr/share/ollama\"
Environment=\"CUDA_DEVICE_ORDER=PCI_BUS_ID\"
Environment=\"CUDA_VISIBLE_DEVICES=$FAST_UUID\"
Environment=\"OLLAMA_HOST=127.0.0.1:11435\"
Environment=\"OLLAMA_MODELS=$MODELS_DIR\"
Environment=\"OLLAMA_KEEP_ALIVE=24h\"
Environment=\"OLLAMA_MAX_LOADED_MODELS=2\"

[Install]
WantedBy=multi-user.target
"
LOCAL_TXT="# Written by scripts/setup_gpu_pinning.sh: fast + embed on the 3060 instance.
models:
  fast:  {host: \"http://127.0.0.1:11435\"}
  embed: {host: \"http://127.0.0.1:11435\"}
"

if [[ "$MODE" == dry ]]; then
  printf '\n--- %s ---\n%s\n--- %s ---\n%s\n--- %s ---\n%s\n' "$DROPIN" "$DROPIN_TXT" "$FAST_UNIT" "$FAST_TXT" "$LOCAL_CFG" "$LOCAL_TXT"
  echo "Dry run only. Re-run with --apply to install."
  exit 0
fi

sudo mkdir -p "$DROPIN_DIR"
printf '%s' "$DROPIN_TXT" | sudo tee "$DROPIN" >/dev/null
printf '%s' "$FAST_TXT"  | sudo tee "$FAST_UNIT" >/dev/null
sudo restorecon -v "$DROPIN" "$FAST_UNIT" >/dev/null 2>&1 || true   # SELinux labels
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl enable --now ollama-fast.service

if [[ -f "$LOCAL_CFG" ]] && ! grep -q 11435 "$LOCAL_CFG"; then
  echo "NOTE: $LOCAL_CFG exists; add these lines yourself:"; printf '%s' "$LOCAL_TXT"
elif [[ ! -f "$LOCAL_CFG" ]]; then
  printf '%s' "$LOCAL_TXT" > "$LOCAL_CFG"
fi

for i in {1..20}; do curl -fsS http://127.0.0.1:11435/api/tags >/dev/null 2>&1 && break; sleep 1; done
echo "Instances:"
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null && echo "  ✓ 11434 main" || echo "  ✗ 11434 main (journalctl -u ollama)"
curl -fsS http://127.0.0.1:11435/api/tags >/dev/null && echo "  ✓ 11435 fast" || echo "  ✗ 11435 fast (journalctl -u ollama-fast)"
cat <<DONE

Both instances share the model store ($MODELS_DIR), so nothing needs re-downloading.
Check placement while chatting:   watch -n1 nvidia-smi
                                  OLLAMA_HOST=127.0.0.1:11435 ollama ps ; ollama ps
Then: cd $REPO_DIR && uv run atlas doctor --profile homepc
DONE
