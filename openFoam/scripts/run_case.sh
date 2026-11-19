#!/usr/bin/env bash
set -e

if [ -z "$WM_PROJECT_DIR" ]; then
    echo "Error: OpenFOAM environment not loaded. Run: source ~/.zshrc"
    exit 1
fi

if [ ! -f "system/controlDict" ]; then
    echo "Error: system/controlDict not found. Run this from inside a case folder."
    exit 1
fi

. "${WM_PROJECT_DIR}/bin/tools/RunFunctions"

SOLVER=$(getApplication)
echo "=== Starting OpenFOAM Case: $(basename "$PWD") | Solver: $SOLVER ==="

if [ -f "system/blockMeshDict" ]; then
    echo "[1/5] Generating base mesh with blockMesh..."
    runApplication blockMesh
fi

if [ -f "system/snappyHexMeshDict" ]; then
    if [ -f "system/surfaceFeatureExtractDict" ]; then
        echo "[2/5] Extracting CAD surface features..."
        runApplication surfaceFeatureExtract
    fi
    echo "[2/5] Snapping 3D mesh with snappyHexMesh..."
    runApplication snappyHexMesh -overwrite
fi

echo "[3/5] Checking mesh quality..."
runApplication checkMesh

if [ -f "system/setFieldsDict" ]; then
    echo "[4/5] Initializing custom field regions with setFields..."
    runApplication setFields
fi

if [ -f "system/decomposeParDict" ]; then
    echo "[5/5] Decomposing domain and running $SOLVER in parallel..."
    runApplication decomposePar -force
    runParallel "$SOLVER"
    echo "Reconstructing parallel time steps..."
    runApplication reconstructPar
else
    echo "[5/5] Running $SOLVER on single core..."
    runApplication "$SOLVER"
fi

touch case.foam
echo "=== Simulation Complete! Open results with: paraview case.foam ==="
