#!/usr/bin/env bash
set -e

if [ ! -f "system/controlDict" ]; then
    echo "Error: system/controlDict not found. Run this script from inside a case folder."
    exit 1
fi

# If OpenFOAM isn't loaded natively in this shell, re-launch inside Podman or Docker automatically
if [ -z "$WM_PROJECT_DIR" ]; then
    if command -v podman &> /dev/null; then
        echo "[Container Mode] Running case inside Podman (opencfd/openfoam-default)..."
        exec podman run --rm --userns=keep-id -v "$PWD:/case:Z" -w /case docker.io/opencfd/openfoam-default:latest bash -c '
            source /usr/lib/openfoam/openfoam*/etc/bashrc 2>/dev/null || source /opt/openfoam*/etc/bashrc
            . "${WM_PROJECT_DIR}/bin/tools/RunFunctions"
            SOLVER=$(getApplication)
            echo "=== Starting OpenFOAM Case: $(basename "$PWD") | Solver: $SOLVER ==="
            [ -f "system/blockMeshDict" ] && echo "[1/5] blockMesh..." && runApplication blockMesh
            if [ -f "system/snappyHexMeshDict" ]; then
                [ -f "system/surfaceFeatureExtractDict" ] && runApplication surfaceFeatureExtract
                echo "[2/5] snappyHexMesh..." && runApplication snappyHexMesh -overwrite
            fi
            echo "[3/5] checkMesh..." && runApplication checkMesh
            [ -f "system/setFieldsDict" ] && echo "[4/5] setFields..." && runApplication setFields
            if [ -f "system/decomposeParDict" ]; then
                echo "[5/5] Running $SOLVER in parallel..."
                runApplication decomposePar -force
                runParallel "$SOLVER"
                runApplication reconstructPar
            else
                echo "[5/5] Running $SOLVER on single core..."
                runApplication "$SOLVER"
            fi
            touch case.foam
            echo "=== Simulation Complete! ==="
        '
    elif command -v docker &> /dev/null; then
        echo "[Container Mode] Running case inside Docker (opencfd/openfoam-default)..."
        exec docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/case" -w /case opencfd/openfoam-default:latest bash -c '
            source /usr/lib/openfoam/openfoam*/etc/bashrc 2>/dev/null || source /opt/openfoam*/etc/bashrc
            . "${WM_PROJECT_DIR}/bin/tools/RunFunctions"
            SOLVER=$(getApplication)
            [ -f "system/blockMeshDict" ] && runApplication blockMesh
            if [ -f "system/snappyHexMeshDict" ]; then
                [ -f "system/surfaceFeatureExtractDict" ] && runApplication surfaceFeatureExtract
                runApplication snappyHexMesh -overwrite
            fi
            runApplication checkMesh
            [ -f "system/setFieldsDict" ] && runApplication setFields
            if [ -f "system/decomposeParDict" ]; then
                runApplication decomposePar -force
                runParallel "$SOLVER"
                runApplication reconstructPar
            else
                runApplication "$SOLVER"
            fi
            touch case.foam
        '
    else
        echo "Error: OpenFOAM is not loaded and neither podman nor docker was found."
        exit 1
    fi
fi

# Native execution path (when WM_PROJECT_DIR is already active)
. "${WM_PROJECT_DIR}/bin/tools/RunFunctions"
SOLVER=$(getApplication)
echo "=== Starting OpenFOAM Case: $(basename "$PWD") | Solver: $SOLVER ==="

[ -f "system/blockMeshDict" ] && echo "[1/5] Generating base mesh..." && runApplication blockMesh
if [ -f "system/snappyHexMeshDict" ]; then
    [ -f "system/surfaceFeatureExtractDict" ] && runApplication surfaceFeatureExtract
    echo "[2/5] Snapping 3D mesh..." && runApplication snappyHexMesh -overwrite
fi
echo "[3/5] Checking mesh quality..." && runApplication checkMesh
[ -f "system/setFieldsDict" ] && echo "[4/5] Initializing fields..." && runApplication setFields

if [ -f "system/decomposeParDict" ]; then
    echo "[5/5] Running $SOLVER in parallel..."
    runApplication decomposePar -force
    runParallel "$SOLVER"
    runApplication reconstructPar
else
    echo "[5/5] Running $SOLVER on single core..."
    runApplication "$SOLVER"
fi

touch case.foam
echo "=== Simulation Complete! Open results with: paraview case.foam ==="
