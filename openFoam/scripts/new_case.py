#!/usr/bin/env python3
import argparse
import re
import shutil
import sys
from pathlib import Path


def update_cores(case_dir: Path, cores: int) -> None:
    decomp_file = case_dir / "system" / "decomposeParDict"
    if not decomp_file.exists():
        return
    text = decomp_file.read_text()
    text = re.sub(r"numberOfSubdomains\s+\d+;", f"numberOfSubdomains {cores};", text)
    text = re.sub(r"method\s+\w+;", "method          scotch;", text)
    decomp_file.write_text(text)
    print(f"Configured parallel run for {cores} CPU cores (method: scotch).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new OpenFOAM case from a template.")
    parser.add_argument("template", help="Folder name inside templates/ (e.g., 01_incompressible)")
    parser.add_argument("name", help="Name for the new case inside cases/")
    parser.add_argument("--cores", type=int, default=None, help="Set CPU core count for parallel runs")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    src = repo_root / "templates" / args.template
    dst = repo_root / "cases" / args.name

    if not src.exists():
        available = [p.name for p in (repo_root / "templates").iterdir() if p.is_dir()]
        print(f"Error: Template '{args.template}' not found. Available: {available}")
        sys.exit(1)

    if dst.exists():
        print(f"Error: Case '{dst}' already exists.")
        sys.exit(1)

    shutil.copytree(src, dst)
    if args.cores:
        update_cores(dst, args.cores)

    print(f"Created new case at: {dst}")
    print(f"Run it with:\n  cd cases/{args.name} && ../../scripts/run_case.sh")


if __name__ == "__main__":
    main()
