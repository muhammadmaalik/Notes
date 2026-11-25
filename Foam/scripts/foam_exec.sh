#!/usr/bin/env bash
# Run one command in a checked native v2606 environment or a pinned container.
set -eo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$root"
[[ $# -gt 0 ]] || { echo "Usage: scripts/foam_exec.sh COMMAND [ARGS...]" >&2; exit 2; }
backend=${FOAM_BACKEND:-auto}
version=${FOAM_VERSION:-2606}
image=${FOAM_IMAGE:-docker.io/opencfd/openfoam-run:2606}
[[ "$version" =~ ^[0-9]{4}$ ]] || { echo "Invalid FOAM_VERSION" >&2; exit 2; }

load_native() {
    if [[ -n ${FOAM_BASHRC:-} ]]; then
        [[ -f "$FOAM_BASHRC" ]] || { echo "FOAM_BASHRC does not exist: $FOAM_BASHRC" >&2; return 1; }
        source "$FOAM_BASHRC" || return 1
    elif ! command -v blockMesh >/dev/null; then
        local rc
        for rc in /usr/lib/openfoam/openfoam"$version"/etc/bashrc \
                  /opt/openfoam"$version"/etc/bashrc /opt/OpenFOAM/OpenFOAM-v"$version"/etc/bashrc; do
            if [[ -f "$rc" ]]; then source "$rc" || return 1; break; fi
        done
    fi
    command -v blockMesh >/dev/null
}
check_version() {
    if [[ ${WM_PROJECT_VERSION#v} != "$version" ]]; then
        echo "Expected OpenCFD OpenFOAM v$version, found '${WM_PROJECT_VERSION:-unknown}'. See setup/README.md." >&2
        return 1
    fi
}
case "$backend" in
    auto|native)
        if load_native; then
            check_version
            exec "$@"
        fi
        [[ "$backend" != native ]] || { echo "Native OpenFOAM not found. Set FOAM_BASHRC or install it." >&2; exit 1; }
        [[ -z ${FOAM_BASHRC:-} ]] || { echo "Could not load FOAM_BASHRC" >&2; exit 1; }
        if command -v podman >/dev/null; then backend=podman
        elif command -v docker >/dev/null; then backend=docker
        else echo "OpenFOAM and container runtime missing. Read setup/README.md." >&2; exit 1; fi
        ;;
    podman|docker) ;;
    *) echo "FOAM_BACKEND must be auto, native, podman, or docker" >&2; exit 2 ;;
esac
command -v "$backend" >/dev/null || { echo "$backend is not installed" >&2; exit 1; }
options=(run --rm --security-opt label=disable --user "$(id -u):$(id -g)"
         -e "FOAM_EXPECTED_VERSION=$version" -e HOME=/tmp
         -v "$root:/workspace:rw" -w /workspace --entrypoint /bin/bash)
[[ "$backend" != podman ]] || options+=(--userns=keep-id)
# Do not relabel the user's Notes directory on SELinux hosts. Do not mount home.
exec "$backend" "${options[@]}" "$image" -c '
    set -eo pipefail
    foam_command_args=("$@")
    # OpenFOAM bashrc interprets positional arguments as environment overrides.
    set --
    version=$FOAM_EXPECTED_VERSION
    for rc in /usr/lib/openfoam/openfoam"$version"/etc/bashrc \
              /opt/openfoam"$version"/etc/bashrc /opt/OpenFOAM/OpenFOAM-v"$version"/etc/bashrc; do
        if [[ -f "$rc" ]]; then
            source "$rc" || { echo "Could not load $rc" >&2; exit 1; }
            break
        fi
    done
    command -v blockMesh >/dev/null || { echo "OpenFOAM missing in container" >&2; exit 1; }
    [[ ${WM_PROJECT_VERSION#v} == "$version" ]] || { echo "Container version mismatch: ${WM_PROJECT_VERSION:-unknown}" >&2; exit 1; }
    exec "${foam_command_args[@]}"
' bash "$@"
