import os
import shutil
import subprocess

import pytest

from atlas.config import REPO_ROOT

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

FAKE_SMI = """#!/usr/bin/env bash
if [[ "$1" == "-L" ]]; then echo "GPU 0: NVIDIA GeForce RTX 3060 (UUID: GPU-aaaa)"; echo "GPU 1: NVIDIA GeForce RTX 5070 Ti (UUID: GPU-bbbb)"
else echo "NVIDIA GeForce RTX 3060, GPU-aaaa, 00000000:05:00.0"; echo "NVIDIA GeForce RTX 5070 Ti, GPU-bbbb, 00000000:01:00.0"; fi
"""


def test_scripts_parse():
    for s in ("setup_fedora.sh", "setup_gpu_pinning.sh", "upgrade.sh"):
        subprocess.run(["bash", "-n", str(REPO_ROOT / "scripts" / s)], check=True)


def test_gpu_pinning_dry_run_uses_uuids(tmp_path):
    smi = tmp_path / "nvidia-smi"
    smi.write_text(FAKE_SMI)
    smi.chmod(0o755)
    out = subprocess.run(["bash", str(REPO_ROOT / "scripts" / "setup_gpu_pinning.sh")], capture_output=True,
                         text=True, env={**os.environ, "NVIDIA_SMI": str(smi)}, check=True).stdout
    assert 'CUDA_VISIBLE_DEVICES=GPU-aaaa"' in out            # fast instance: 3060 only
    assert 'CUDA_VISIBLE_DEVICES=GPU-bbbb,GPU-aaaa"' in out   # main: 5070 Ti first
    assert "CUDA_DEVICE_ORDER=PCI_BUS_ID" in out and "127.0.0.1:11435" in out
    assert "Dry run only" in out


def test_upgrade_preserves_data_readme_and_profile(tmp_path):
    target = tmp_path / "Notes" / "atlas"
    (target / "src" / "atlas").mkdir(parents=True)
    (target / "pyproject.toml").write_text("old")
    (target / "README.md").write_text("MY OWN README")
    (target / "data").mkdir()
    (target / "data" / "atlas.db").write_text("precious")
    (target / "configs").mkdir()
    (target / "configs" / "profile.yaml").write_text("name: Me\n")
    (target / "configs" / "homepc.yaml").write_text("profile: homepc\n# my edit\n")
    (target / "configs" / "homepc.local.yaml").write_text("mine: true\n")

    subprocess.run(["bash", str(REPO_ROOT / "scripts" / "upgrade.sh"), str(target)], check=True,
                   capture_output=True, text=True, env={**os.environ, "ATLAS_UPGRADE_SKIP_SYNC": "1"})
    assert (target / "README.md").read_text() == "MY OWN README"
    assert (target / "data" / "atlas.db").read_text() == "precious"
    assert (target / "configs" / "profile.yaml").read_text() == "name: Me\n"
    assert (target / "configs" / "profile.yaml.new").exists()
    assert (target / "configs" / "homepc.local.yaml").read_text() == "mine: true\n"
    assert "deep:" in (target / "configs" / "homepc.yaml").read_text()
    assert list((target / "configs").glob("homepc.yaml.bak-*"))
    assert (target / "src" / "atlas" / "research.py").exists() and (target / "SETUP.md").exists()
    assert list(tmp_path.joinpath("Notes").glob("atlas-backup-*.tar.gz"))
