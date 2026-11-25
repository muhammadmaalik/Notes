#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
compiler=${CXX:-g++}
command -v "$compiler" >/dev/null || { echo "Install a C++17 compiler; see setup/README.md." >&2; exit 1; }
mkdir -p "$root/build"
temp=$(mktemp "$root/build/.foamctl.XXXXXX")
trap 'rm -f -- "$temp"' EXIT
"$compiler" -std=c++17 -O2 -Wall -Wextra -Wpedantic "$root/src/foamctl.cpp" -o "$temp"
chmod +x "$temp"
mv -- "$temp" "$root/build/foamctl"
echo "Built build/foamctl"
