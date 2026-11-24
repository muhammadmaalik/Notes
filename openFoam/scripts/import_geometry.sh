#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
name=${1:?Usage: scripts/import_geometry.sh NAME FILE.stl [--scale FACTOR] [--center] [--translate X Y Z]}
input=${2:?Missing STL file; convert STEP first with scripts/step_to_stl.py}
[[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]] || { echo "Invalid run name" >&2; exit 2; }
case_dir="$root/runs/$name"
[[ -f "$case_dir/system/snappyHexMeshDict" ]] || { echo "Create an external-stl run first" >&2; exit 1; }
[[ $(realpath "$case_dir") == "$root/runs/$name" ]] || { echo "Symlinked cases are not supported" >&2; exit 2; }
exec 9>"$case_dir/.workflow.lock"
flock -n 9 || { echo "Case is in use" >&2; exit 1; }
[[ ! -e "$case_dir/constant/polyMesh/points" ]] || { echo "Mesh already exists. Import into a fresh run so the mesh and geometry stay consistent." >&2; exit 1; }
shift 2
exec python3 "$root/scripts/prepare_geometry.py" "$input" "$case_dir/constant/triSurface/body.stl" "$@"
