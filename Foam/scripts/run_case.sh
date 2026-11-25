#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
name=${1:?Usage: scripts/run_case.sh NAME [run|mesh|remesh|solve|check|view] [--parallel N]}
stage=${2:-run}
[[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]] || { echo "Invalid run name" >&2; exit 2; }
case_dir="$root/runs/$name"
[[ -d "$case_dir/0" && -f "$case_dir/system/controlDict" ]] || { echo "Incomplete or missing case: $name" >&2; exit 1; }
[[ $(realpath "$case_dir") == "$root/runs/$name" ]] || { echo "Symlinked cases are not supported" >&2; exit 2; }
shift
[[ $# == 0 ]] || shift
parallel=1
if [[ $# -gt 0 ]]; then
    [[ $# == 2 && $1 == --parallel && $2 =~ ^[1-9][0-9]*$ && ${#2} -le 5 ]] || { echo "Expected --parallel N (positive integer)" >&2; exit 2; }
    [[ "$stage" == run || "$stage" == solve ]] || { echo "--parallel is for run/solve only" >&2; exit 2; }
    parallel=$2
fi
case "$stage" in
    run|mesh|remesh|solve|check)
        exec "$root/scripts/foam_exec.sh" bash scripts/case_pipeline.sh "runs/$name" "$stage" "$parallel" ;;
    view)
        touch "$case_dir/case.foam"
        command -v paraview >/dev/null || { echo "Install host ParaView, then open $case_dir/case.foam" >&2; exit 1; }
        exec paraview "$case_dir/case.foam" ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
