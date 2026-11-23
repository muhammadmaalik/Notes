#!/usr/bin/env bash
# Overnight setup for the home PC: boot the kernel the NVIDIA driver was built for,
# install Ollama, download all Atlas models, then reboot so the driver loads.
set -euo pipefail
LOG=~/atlas_overnight.log
exec > >(tee -a "$LOG") 2>&1
echo "== $(date) starting"
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" 2>/dev/null || exit; done 2>/dev/null &
sudo grubby --set-default /boot/vmlinuz-7.3.4-200.fc44.x86_64
sudo dnf install -y pandoc nvtop
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
sleep 5
for m in qwen3.5:9b gpt-oss:20b qwen3-embedding:0.6b qwen3.5:4b qwen3.8:27b; do
  echo "== pulling $m"
  for try in 1 2 3; do ollama pull "$m" && break; echo "retry $try"; sleep 20; done
done
ollama list
echo "== $(date) done, rebooting into the NVIDIA kernel"
sudo reboot
