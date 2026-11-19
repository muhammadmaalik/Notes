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

echo "Cleaning generated meshes, processor folders, logs, and time steps..."
cleanCase
rm -f case.foam *.foam residuals.png
echo "Case is clean!"
