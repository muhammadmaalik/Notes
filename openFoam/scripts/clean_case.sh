#!/usr/bin/env bash
set -e

if [ ! -f "system/controlDict" ]; then
    echo "Error: system/controlDict not found. Run this script from inside a case folder."
    exit 1
fi

echo "Cleaning generated meshes, processor folders, logs, and time steps..."
rm -rf [1-9]* 0.* processor* postProcessing dynamicCode constant/polyMesh log.* case.foam *.foam residuals.png
echo "Case is clean!"
