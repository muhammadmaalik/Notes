#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
echo "Project: $root"
echo "Backend: ${FOAM_BACKEND:-auto}; expected version: ${FOAM_VERSION:-2606}"
echo "Container image: ${FOAM_IMAGE:-docker.io/opencfd/openfoam-run:2606}"
for cmd in g++ python3 podman docker paraview; do
    if command -v "$cmd" >/dev/null; then echo "$cmd: $(command -v "$cmd")"; else echo "$cmd: unavailable"; fi
done
exec "$root/scripts/foam_exec.sh" bash -c '
    echo "OpenFOAM: $WM_PROJECT_VERSION ($WM_PROJECT_DIR)"
    for cmd in blockMesh checkMesh foamDictionary surfaceCheck surfaceFeatureExtract snappyHexMesh icoFoam simpleFoam pimpleFoam decomposePar reconstructPar mpirun flock; do
        command -v "$cmd" || exit 1
    done
'
