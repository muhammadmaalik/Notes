#!/usr/bin/env bash
# Install host prerequisites, then fetch a versioned OpenCFD runtime image.
# Does not edit shell startup files or enable third-party COPRs.
set -euo pipefail
backend=podman
visualization=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend) backend=${2:?Choose podman or docker}; shift 2 ;;
        --with-paraview) visualization=true; shift ;;
        --help|-h)
            echo "Usage: setup/install_linux.sh [--backend podman|docker] [--with-paraview]"
            echo "Installs a C++ compiler, Python, util-linux, and Podman (or uses existing Docker)."
            echo "Pulls docker.io/opencfd/openfoam-run:2606; does not run simulations."
            exit ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done
[[ "$backend" == podman || "$backend" == docker ]] || { echo "Choose podman or docker. Native setup: setup/README.md" >&2; exit 2; }
[[ -f /etc/os-release ]] || { echo "Cannot identify Linux distribution" >&2; exit 1; }
source /etc/os-release
privilege=()
if (( EUID != 0 )); then privilege=(sudo); fi
case "$ID" in
    fedora|rhel|centos|rocky|almalinux)
        packages=(gcc-c++ python3 util-linux)
        [[ "$backend" != podman ]] || packages+=(podman)
        [[ "$visualization" != true ]] || packages+=(paraview)
        "${privilege[@]}" dnf install -y "${packages[@]}"
        ;;
    ubuntu|debian)
        packages=(g++ python3 util-linux)
        [[ "$backend" != podman ]] || packages+=(podman)
        [[ "$visualization" != true ]] || packages+=(paraview)
        "${privilege[@]}" apt-get update
        "${privilege[@]}" apt-get install -y "${packages[@]}"
        ;;
    *) echo "Install a C++17 compiler, Python 3, util-linux, and $backend using your distro's package manager." >&2 ;;
esac
command -v "$backend" >/dev/null || { echo "Install/configure $backend, then rerun this script." >&2; exit 1; }
image=${FOAM_IMAGE:-docker.io/opencfd/openfoam-run:2606}
"$backend" pull "$image"
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
"$root/scripts/build.sh"
echo "Setup complete. Verify with: FOAM_BACKEND=$backend ./scripts/foam doctor"
