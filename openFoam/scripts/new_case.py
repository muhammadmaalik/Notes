#!/usr/bin/env python3
import argparse
import re
import shutil
import sys
from pathlib import Path


def safe_name(value: str) -> str:
    """Keep template and case names inside their intended parent folders."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise argparse.ArgumentTypeError("Use letters, digits, underscores, or hyphens; start with a letter or digit.")
    return value


def positive_cores(value: str) -> int:
    cores = int(value)
    if cores < 1:
        raise argparse.ArgumentTypeError("Core count must be at least 1 (serial).")
    return cores


def update_cores(case_dir: Path, cores: int) -> None:
    """Only alter the copy. Every supplied template uses scotch decomposition."""
    decomp_file = case_dir / "system" / "decomposeParDict"
    if not decomp_file.exists():
        return
    text = decomp_file.read_text()
    text, count = re.subn(r"(?m)^numberOfSubdomains\s+\d+;", f"numberOfSubdomains {cores};", text)
    if count != 1:
        raise ValueError(f"Expected one numberOfSubdomains entry in {decomp_file}")
    decomp_file.write_text(text)
    if cores == 1:
        print("Configured serial run (1 CPU core).")
    else:
        print(f"Configured parallel run for {cores} CPU cores (method: scotch).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new OpenFOAM case from a template.")
    parser.add_argument("template", type=safe_name, help="Folder name inside templates/ (e.g., 01_incompressible)")
    parser.add_argument("name", type=safe_name, help="Name for the new case inside cases/")
    parser.add_argument("--cores", type=positive_cores, default=1, help="CPU cores: 1 = serial (default), >1 = MPI parallel")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    src = repo_root / "templates" / args.template
    dst = repo_root / "cases" / args.name

    if not src.is_dir() or not (src / "system" / "controlDict").is_file():
        available = [p.name for p in (repo_root / "templates").iterdir() if p.is_dir()]
        print(f"Error: Template '{args.template}' not found. Available: {available}")
        sys.exit(1)

    if dst.exists() or dst.is_symlink():
        print(f"Error: Case '{dst}' already exists.")
        sys.exit(1)

    if src.resolve().parent != (repo_root / "templates").resolve():
        parser.error("Template must be directly inside templates/.")
    if dst.resolve().parent != (repo_root / "cases").resolve():
        parser.error("Case must be directly inside cases/.")
    shutil.copytree(src, dst)
    update_cores(dst, args.cores)

    print(f"Created new case at: {dst}")
    print(f"Run it with:\n  cd cases/{args.name} && ../../scripts/run_case.sh")


if __name__ == "__main__":
    main()
