#!/usr/bin/env bash
# Internal driver: executed inside the OpenFOAM environment, from project root.
set -euo pipefail
case_path=${1:?Missing case path}
stage=${2:?Missing stage}
parallel=${3:-1}
cd -- "$case_path"
mkdir -p logs
# Prevent simultaneous mesh/solve commands from corrupting the same case.
exec 9>.workflow.lock
flock -n 9 || { echo "Another workflow is already using this case" >&2; exit 1; }
log_command() {
    local utility=$1
    shift
    local logfile="logs/$(date -u +%Y%m%dT%H%M%S.%N)-$$-$utility.log"
    last_logfile=$logfile
    echo "Running $utility; log: $case_path/$logfile"
    "$@" 2>&1 | tee "$logfile"
}
check_mesh() {
    [[ -f constant/polyMesh/points ]] || { echo "No mesh. Run mesh first." >&2; exit 1; }
    local quality_options=()
    [[ ! -f system/meshQualityDict ]] || quality_options+=(-meshQuality)
    log_command checkMesh checkMesh -allTopology "${quality_options[@]}"
    # Some checkMesh versions return success even when reporting failed checks.
    local latest
    latest=$last_logfile
    if ! grep -q 'Mesh OK\.' "$latest" || grep -Eq 'Failed [1-9][0-9]* mesh checks' "$latest"; then
        echo "Mesh validation failed. Read $latest before solving." >&2
        exit 1
    fi
}
verify_mesh_inputs() {
    [[ -f .mesh-complete && -f .mesh-inputs.sha256 ]] || {
        echo "Incomplete/unmanaged mesh found. Use a fresh run; inspect the meshing logs." >&2
        exit 1
    }
    sha256sum --check --status .mesh-inputs.sha256 || {
        echo "Meshing inputs changed. Use remesh before any results exist, or create a fresh run." >&2
        exit 1
    }
}
mesh() {
    [[ ! -e constant/polyMesh/points ]] || { echo "Mesh already exists. Use remesh before any results exist, or create a fresh run." >&2; exit 1; }
    rm -f -- .mesh-complete .mesh-inputs.sha256
    if [[ -f system/snappyHexMeshDict ]]; then
        [[ -s constant/triSurface/body.stl ]] || { echo "Import geometry first; see docs/geometry.md." >&2; exit 1; }
        log_command surfaceCheck surfaceCheck constant/triSurface/body.stl
    fi
    log_command blockMesh blockMesh
    if [[ -f system/snappyHexMeshDict ]]; then
        log_command surfaceFeatureExtract surfaceFeatureExtract
        log_command snappyHexMesh snappyHexMesh -overwrite
    fi
    check_mesh
    local inputs=(system/blockMeshDict)
    local input
    for input in system/snappyHexMeshDict system/surfaceFeatureExtractDict system/meshQualityDict constant/triSurface/body.stl; do
        [[ ! -f "$input" ]] || inputs+=("$input")
    done
    sha256sum "${inputs[@]}" > .mesh-inputs.sha256
    touch .mesh-complete
    mesh_checked=true
}
results_exist() {
    local directory
    for directory in */; do
        directory=${directory%/}
        if [[ "$directory" =~ ^[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$ && "$directory" != 0 ]]; then
            return 0
        fi
    done
    return 1
}
mesh_checked=false
case "$stage" in
    mesh) mesh; exit ;;
    remesh)
        shopt -s nullglob
        partitions=(processor[0-9]* processors[0-9]*)
        if results_exist || (( ${#partitions[@]} > 0 )); then
            echo "Results/partitions exist. Create a fresh run to change its mesh." >&2; exit 1
        fi
        [[ ! -L constant && ! -L constant/polyMesh ]] || { echo "Refusing to replace symlinked mesh storage" >&2; exit 1; }
        rm -rf -- constant/polyMesh
        mesh
        exit ;;
    check) check_mesh; exit ;;
    run) if [[ ! -f constant/polyMesh/points ]]; then mesh
         else verify_mesh_inputs; echo "Reusing existing mesh"; fi ;;
    solve) verify_mesh_inputs ;;
    *) echo "Invalid pipeline stage" >&2; exit 2 ;;
esac
[[ "$mesh_checked" == true ]] || check_mesh
if results_exist; then
    start_from=$(foamDictionary system/controlDict -entry startFrom -value)
    [[ "$start_from" == latestTime ]] || { echo "Results already exist. Set startFrom latestTime to resume, or create a new run." >&2; exit 1; }
fi
solver=$(foamDictionary system/controlDict -entry application -value)
[[ "$solver" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || { echo "Invalid application in controlDict" >&2; exit 1; }
command -v "$solver" >/dev/null || { echo "Solver not installed: $solver" >&2; exit 1; }
shopt -s nullglob
processors=(processor[0-9]* processors[0-9]*)
[[ ${#processors[@]} == 0 ]] || { echo "Existing processor data found. Use a fresh run for parallel execution (see docs/workflow.md)." >&2; exit 1; }
if (( parallel > 1 )); then
    foamDictionary system/decomposeParDict -entry numberOfSubdomains -set "$parallel"
    log_command decomposePar decomposePar
    log_command "$solver" mpirun -np "$parallel" "$solver" -parallel
    log_command reconstructPar reconstructPar
else
    log_command "$solver" "$solver"
fi
touch case.foam
echo "Finished $case_path. Open case.foam in ParaView. Check solver residuals and physical balances."
