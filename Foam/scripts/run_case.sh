#!/usr/bin/env bash
# Fresh-case workflow: mesh -> check -> initialize -> solve -> reconstruct.
# Run from a COPY in cases/. Use the solver directly for a deliberate restart.
set -Eeo pipefail

mesh_only=false
existing_mesh=false
while [ "$#" -gt 0 ]; do
case "$1" in
    --mesh-only) mesh_only=true ;;
    --existing-mesh) existing_mesh=true ;;
    -h|--help)
        echo "Usage: run_case.sh [--mesh-only] [--existing-mesh] (from inside a cloned case)"
        echo "OPENFOAM_IMAGE overrides the container image; OPENFOAM_RUNTIME=podman|docker selects the runtime."
        exit 0 ;;
    *) echo "Unknown argument: $1; see --help." >&2; exit 1 ;;
esac
shift
done
if [ ! -f system/controlDict ]; then
    echo "Error: run from a case containing system/controlDict; see --help." >&2
    exit 1
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
case_dir=$(pwd -P)
case "$case_dir" in
    */templates/*)
        echo "Error: create a working run before running a reference template." >&2
        exit 1 ;;
esac

# One workflow is shared by native OpenFOAM, Podman and Docker. The container
# only receives this case and this runner; it does not need the whole repository.
if [ -z "${WM_PROJECT_DIR:-}" ]; then
    runtime=${OPENFOAM_RUNTIME:-}
    if [ -z "$runtime" ]; then
        if command -v podman >/dev/null 2>&1; then runtime=podman
        elif command -v docker >/dev/null 2>&1; then runtime=docker
        else echo "Error: load OpenFOAM or install Podman/Docker." >&2; exit 1
        fi
    fi
    image=${OPENFOAM_IMAGE:-docker.io/opencfd/openfoam-default:latest}
    options=()
    case "$runtime" in
        # The runner is shared by concurrent cases; its SELinux label must be shared too.
        podman) options+=(--userns=keep-id); mount_mode=Z; runner_mode=ro,z ;;
        docker) options+=(-u "$(id -u):$(id -g)"); mount_mode=rw; runner_mode=ro ;;
        *) echo "Error: OPENFOAM_RUNTIME must be podman or docker." >&2; exit 1 ;;
    esac
    arguments=()
    if "$mesh_only"; then arguments+=(--mesh-only); fi
    if "$existing_mesh"; then arguments+=(--existing-mesh); fi
    echo "Container: $runtime / $image"
    exec "$runtime" run --rm "${options[@]}" \
        -v "$case_dir:/case:$mount_mode" \
        -v "$script_dir/run_case.sh:/workflow/run_case.sh:$runner_mode" \
        -w /case --entrypoint /bin/bash "$image" -c '
            # Images differ in installation prefix. Source the first matching environment.
            for rc in /usr/lib/openfoam/openfoam*/etc/bashrc /opt/openfoam*/etc/bashrc; do
                if [ -f "$rc" ]; then source "$rc"; break; fi
            done
            if [ -z "${WM_PROJECT_DIR:-}" ]; then
                echo "Error: OpenFOAM environment not found in container." >&2; exit 1
            fi
            exec bash /workflow/run_case.sh "$@"
        ' bash "${arguments[@]}"
fi

. "${WM_PROJECT_DIR}/bin/tools/RunFunctions"
solver=$(getApplication)
command -v "$solver" >/dev/null 2>&1 || { echo "Solver not found: $solver" >&2; exit 1; }
cores=1
if [ -f system/decomposeParDict ]; then cores=$(getNumberOfProcessors); fi
if ! [[ "$cores" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: numberOfSubdomains must be a positive integer." >&2; exit 1
fi

# Refuse an accidental rerun: RunFunctions normally skips commands whose logs
# already exist, potentially leaving old results after an input edit.
shopt -s nullglob
solver_logs=(log.*Foam)
processors=(processor[0-9]* processors[0-9]*)
if [ "${#solver_logs[@]}" -gt 0 ] || [ "${#processors[@]}" -gt 0 ]; then
    echo "Error: existing solver logs or decomposed results; create a new run or clean generated output first." >&2
    exit 1
fi
for time_dir in */; do
    name=${time_dir%/}
    if [[ "$name" =~ ^[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$ ]] &&
       [[ ! "$name" =~ ^0+([.]0+)?([eE][+-]?[0-9]+)?$ ]]; then
        echo "Error: existing time directory $name; use a new case or clean first." >&2
        exit 1
    fi
done

# -o replaces preprocessing logs, so --mesh-only can be followed by a full run.
trap 'echo "Run failed. Inspect the latest log.* in the case directory." >&2' ERR
echo "Case: $(basename "$case_dir") | OpenFOAM: ${WM_PROJECT_VERSION:-unknown} | Solver: $solver | Cores: $cores"
if "$existing_mesh"; then
    # Importers such as gmshToFoam populate these files. Preserve them verbatim.
    for mesh_file in points faces owner neighbour boundary; do
        if [ ! -f "constant/polyMesh/$mesh_file" ] && [ ! -f "constant/polyMesh/$mesh_file.gz" ]; then
            echo "Error: --existing-mesh requires constant/polyMesh/$mesh_file[.gz]." >&2
            exit 1
        fi
    done
else
    if [ -f system/blockMeshDict ]; then runApplication -o blockMesh; fi
    if [ -f system/snappyHexMeshDict ]; then
        if [ -f system/surfaceFeatureExtractDict ]; then runApplication -o surfaceFeatureExtract; fi
        runApplication -o snappyHexMesh -overwrite
    fi
fi
# Standard geometry checks plus full topology. -allGeometry is an optional deeper
# diagnostic: it flags even mildly concave polyhedra common in snapped meshes.
runApplication -o checkMesh -allTopology
# checkMesh can return success while reporting failed quality checks.
if ! grep -q 'Mesh OK' log.checkMesh; then
    echo "Error: mesh quality checks failed; inspect log.checkMesh." >&2; exit 1
fi
if [ -f system/setFieldsDict ]; then runApplication -o setFields; fi
touch case.foam
if "$mesh_only"; then
    echo "Mesh and initialization complete. Inspect case.foam in ParaView."
    exit 0
fi
if [ "$cores" -gt 1 ]; then
    runApplication -o decomposePar -force
    runParallel "$solver"
    runApplication -o reconstructPar
else
    runApplication "$solver"
fi
echo "Simulation complete. Open case.foam in ParaView; review solver logs and convergence."
