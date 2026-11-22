#!/usr/bin/env python3
import re
import sys
from collections import defaultdict
from pathlib import Path
import matplotlib.pyplot as plt


def find_log_file(target: Path) -> Path:
    if target.is_file():
        return target
    logs = sorted(target.glob("log.*Foam"))
    if not logs:
        print(f"Error: No 'log.*Foam' file found in {target}")
        sys.exit(1)
    return logs[0]


def parse_residuals(log_path: Path) -> dict[str, list[float]]:
    residuals: dict[str, list[float]] = defaultdict(list)
    pattern = re.compile(r"Solving for ([\w.]+), Initial residual = ([0-9.eE+-]+)")
    with log_path.open("r", errors="ignore") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                residuals[match.group(1)].append(float(match.group(2)))
    return residuals


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/plot_residuals.py cases/<case_name>")
        sys.exit(1)

    log_file = find_log_file(Path(sys.argv[1]))
    data = parse_residuals(log_file)

    if not data:
        print(f"No residual entries found in {log_file}.")
        sys.exit(1)

    plt.figure(figsize=(9, 5))
    for field, values in data.items():
        plt.semilogy(values, label=field, linewidth=1.4)

    plt.xlabel("Solver Sub-Iteration")
    plt.ylabel("Initial Residual (log scale)")
    plt.title(f"Convergence History: {log_file.parent.name} ({log_file.name})")
    plt.legend()
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.tight_layout()

    out_png = log_file.parent / "residuals.png"
    plt.savefig(out_png, dpi=150)
    print(f"Parsed {log_file.name} -> Saved plot to {out_png}")


if __name__ == "__main__":
    main()
