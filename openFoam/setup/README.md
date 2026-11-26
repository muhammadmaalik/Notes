# Setup (OpenCFD OpenFOAM v2606)

The project targets the distribution documented at
[doc.openfoam.com/2606](https://doc.openfoam.com/2606/). OpenFOAM Foundation
releases use different version numbers and can have different dictionaries.
The runtime wrapper verifies `WM_PROJECT_VERSION` before running anything.

## Fedora 44: Podman

```bash
./setup/install_linux.sh --with-paraview
./scripts/foam doctor
./scripts/foam run run1
```

The script installs `gcc-c++`, Python 3, `util-linux` (for `flock`), Podman,
and optionally ParaView through your package manager. It pulls the official
[OpenCFD runtime image tagged 2606](https://hub.docker.com/r/opencfd/openfoam-run/tags).
It does not enable COPR repositories or edit `.bashrc`/`.zshrc`. You can keep
using zsh: executable scripts start their own Bash process.

For an existing installation, the equivalent minimum steps are:

```bash
podman pull docker.io/opencfd/openfoam-run:2606
./scripts/build.sh
FOAM_BACKEND=podman ./scripts/foam doctor
```

Container files are written as your UID/GID, Podman uses `--userns=keep-id`,
and only this project is mounted, at `/workspace`. `--security-opt label=disable`
allows access on SELinux hosts without relabeling your Notes directory. The
container has no graphical display; use **host ParaView** to open `case.foam`.
Mesh generation runs in serial; `--parallel N` parallelizes the solver.

Run Podman as your regular user. If rootless Podman cannot start, inspect
`podman info` and your system's rootless Podman configuration. A permission
error involving `/run/user/...` inside a restricted agent environment may
require running the same command in your regular terminal.

## Ubuntu/Debian, or Docker

The same installer supports Ubuntu/Debian using apt:

```bash
./setup/install_linux.sh --with-paraview
```

If Docker is already installed and accessible to your user:

```bash
./setup/install_linux.sh --backend docker --with-paraview
FOAM_BACKEND=docker ./scripts/foam doctor
FOAM_BACKEND=docker ./scripts/foam run run1
```

The script does not install or configure the Docker daemon. Follow Docker's
installation instructions for your distribution if needed.

## Native OpenFOAM

Install **OpenCFD v2606** using the appropriate instructions linked from the
[official installation page](https://www.openfoam.com/current-release).
Then point the wrapper at that installation's Bash startup file:

```bash
export FOAM_BACKEND=native
export FOAM_BASHRC=/usr/lib/openfoam/openfoam2606/etc/bashrc
./scripts/foam doctor
./scripts/foam run run1
```

Adjust the absolute path for your installation. You do not have to source Bash
startup files into zsh. The wrapper loads them in Bash, checks the version,
then starts the requested utility. A previously sourced, correct native
environment is also recognized. Common `/usr/lib/openfoam` and `/opt` locations
are tried automatically. Missing utilities require the corresponding native
runtime/MPI packages.

## Runtime settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `FOAM_BACKEND` | `auto` | `native`, `podman`, `docker`, or automatic choice |
| `FOAM_BASHRC` | unset | Explicit native `etc/bashrc` |
| `FOAM_VERSION` | `2606` | Required version; changing this is an unvalidated override |
| `FOAM_IMAGE` | `docker.io/opencfd/openfoam-run:2606` | Exact container image/tag or digest |
| `CXX` | `g++` | Compiler executable for the standalone launcher |

`auto` tries a native environment, then Podman, then Docker. It fails if a
loaded native version is incorrect; explicitly select `podman`/`docker` to
bypass that environment. It does not silently fall through to Docker after a
Podman runtime error. Override image and expected version together when
deliberately testing another release. Templates are validated for v2606.

The first container run may download the image if you skipped installation.
Image downloads need network access and local container storage. The runtime
image is sufficient for these cases; OpenFOAM source/build headers are not
required to compile `foamctl`. For third-party solver development or the full
tutorial collection, obtain an official development/source installation.

Optional STEP conversion uses Gmsh; see [geometry](../docs/geometry.md). Python
packages are not needed for ASCII/binary STL import or for launching cases.
