#!/usr/bin/env bash
# Copied as Allrun into each generated run. Works independently of the workspace.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Normally leave empty: automatically select ONE STL/STEP in this run's top level.
# If keeping several source files here, select one explicitly, e.g. "wing.STL".
GEOMETRY_FILE=""

prepare_only=false
existing_mesh=false
arguments=()
for option in "$@"; do
    case "$option" in
        --prepare-only) prepare_only=true ;;
        --mesh-only) arguments+=("$option") ;;
        --existing-mesh) existing_mesh=true; arguments+=("$option") ;;
        -h|--help)
            echo "Usage: ./Allrun [--mesh-only] [--existing-mesh] [--prepare-only]"
            echo "Drop one STL or STEP in this folder. STEP conversion requires host Gmsh."
            echo "--prepare-only stages/converts the surface without starting OpenFOAM."
            echo "--existing-mesh preserves the inspected mesh and skips surface staging."
            exit 0 ;;
        *) echo "Unknown option: $option" >&2; exit 1 ;;
    esac
done
if "$existing_mesh" && "$prepare_only"; then
    echo "Choose either --existing-mesh or --prepare-only." >&2
    exit 1
fi

if ! "$existing_mesh"; then
    if [ -z "$GEOMETRY_FILE" ]; then
        shopt -s nullglob nocaseglob
        candidates=()
        for file in *.stl *.step *.stp; do
            if [ -f "$file" ]; then candidates+=("$file"); fi
        done
        if [ "${#candidates[@]}" -ne 1 ]; then
            echo "Drop exactly ONE STL or STEP into this run folder, or set GEOMETRY_FILE in Allrun." >&2
            exit 1
        fi
        GEOMETRY_FILE=${candidates[0]}
    fi
    # Absolute path also prevents geometry names beginning with '-' being options.
    geometry_dir=$(cd -- "$(dirname -- "$GEOMETRY_FILE")" && pwd -P)
    geometry="$geometry_dir/$(basename -- "$GEOMETRY_FILE")"
    if [ ! -s "$geometry" ]; then
        echo "Geometry is missing or empty: $geometry" >&2; exit 1
    fi
    mkdir -p constant/triSurface
    staged=$(mktemp constant/triSurface/.part.XXXXXX.stl)
    trap 'rm -f -- "$staged"' EXIT
    case "${geometry,,}" in
        *.stl)
            cp -- "$geometry" "$staged"
            echo "Staged STL. Coordinates must match your mesh's metre scale." ;;
        *.step|*.stp)
            if ! command -v gmsh >/dev/null 2>&1; then
                echo "STEP conversion requires Gmsh on the host. Alternatively export STL from CAD and replace the STEP in this folder." >&2
                exit 1
            fi
            # Set units BEFORE import: Gmsh reads STEP metadata and converts to metres.
            # A single STL solid gives consistent body patch naming in snappyHexMesh.
            gmsh -setstring Geometry.OCCTargetUnit M "$geometry" -2 -format stl \
                -setnumber Mesh.StlOneSolidPerSurface 0 -o "$staged" > log.stepToStl 2>&1 || {
                echo "STEP conversion failed; inspect log.stepToStl." >&2; exit 1;
            }
            echo "Converted STEP surface to STL in metres; inspect log.stepToStl." ;;
        *) echo "Supported geometry formats: .stl, .step, .stp." >&2; exit 1 ;;
    esac
    if [ ! -s "$staged" ]; then
        echo "No surface triangles produced; inspect the source geometry/conversion log." >&2
        exit 1
    fi
    mv -- "$staged" constant/triSurface/part.stl
    trap - EXIT
fi
if "$prepare_only"; then
    echo "Prepared constant/triSurface/part.stl. No mesh or solver was started."
    exit 0
fi
exec bash ./run_case.sh "${arguments[@]}"
