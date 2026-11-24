# OpenFOAM simulation workspace

Choose a simulation, create a complete case, edit its inputs, and run it. The
standalone C++17 launcher in `src/foamctl.cpp` manages cases; the OpenFOAM
applications perform the CFD calculation. These inputs target **OpenCFD
OpenFOAM v2606**, following the [2606 documentation](https://doc.openfoam.com/2606/)
and [quickstart](https://doc.openfoam.com/2606/quickstart/).

## Start here

Run commands from this project's root directory. On Fedora 44:

```bash
./setup/install_linux.sh --with-paraview
./scripts/foam doctor
./scripts/foam run run1
./scripts/foam view run1
```

The installer needs sudo for host packages. It installs prerequisites and pulls
the pinned official `docker.io/opencfd/openfoam-run:2606` image. The launcher
builds automatically on first use. If prerequisites and the image are already
installed, start with `./scripts/foam doctor`. See [setup](setup/README.md) for
native installations, Docker, and environment options.

**`runs/run1` is already configured:** a small 2D lid-driven cavity using
`icoFoam`, with a 20 × 20 × 1 mesh definition, a 1 m/s moving lid, and viscosity
0.001 m²/s. All input files are present. `blockMesh` generates the actual mesh
automatically on the first run. If this copy already contains a checked mesh,
the launcher reuses it.

## Choose a simulation

| Template name | Solver | Starting problem |
| --- | --- | --- |
| `cavity` | `icoFoam` | 2D transient, laminar cavity; Re = 100 |
| `incomp` | `simpleFoam` | 3D steady, laminar channel; water-like viscosity |
| `transient` | `pimpleFoam` | 3D transient, laminar channel |
| `external-stl` | `simpleFoam` | 3D steady RANS, k-omega SST, flow around a closed solid |

```bash
./scripts/foam list
./scripts/foam new incomp             # creates next unused run2, run3, ...
./scripts/foam new transient pulse    # creates runs/pulse
./scripts/foam new external-stl wing  # creates runs/wing
```

New runs contain independent copies of `0/`, `constant/`, `system/`, a case
README, a `case.foam` ParaView marker, and executable `Allrun`. Existing run
directories are never overwritten. Editing a run does not change the template
or another run. Edit templates only when changing defaults for future cases.

## Edit the case

| File in `runs/NAME/` | What to change |
| --- | --- |
| `0/U` | Initial velocity and inlet/wall velocities [m/s] |
| `0/p` | Initial and boundary **kinematic** pressure [m²/s²] |
| `0/k`, `0/omega`, `0/nut` | Turbulence conditions, in the SST template |
| `constant/transportProperties` | Kinematic viscosity `nu` [m²/s] |
| `constant/turbulenceProperties` | Laminar/RAS model selection |
| `constant/triSurface/body.stl` | Imported surface, in metres |
| `system/blockMeshDict` | Background box, cell counts, patch definitions |
| `system/snappyHexMeshDict` | Surface refinement, fluid seed point, optional layers |
| `system/controlDict` | Solver, end time/iterations, step size, output interval |
| `system/fvSchemes`, `system/fvSolution` | Discretisation, linear solvers, coupling |
| `system/decomposeParDict` | Parallel decomposition (core count set by launcher) |

Patch names in all fields under `0/` must match the generated mesh's
`constant/polyMesh/boundary`. The cavity's front/back patches are `empty`, with
one cell through the thickness. Channel cases are fully 3D. In these
incompressible solvers, convert a kinematic pressure difference to Pa using
`deltaP = rho * delta(p)` with the appropriate constant fluid density.

## Mesh, solve, inspect

```bash
./scripts/foam mesh pulse             # build and validate mesh only
./scripts/foam remesh run1            # rebuild after mesh edits, before results exist
./scripts/foam check pulse            # check existing mesh
./scripts/foam solve pulse            # check and solve that mesh
./scripts/foam run wing               # mesh if needed, check, then solve
./scripts/foam run pulse --parallel 4 # new run: decompose, solve, reconstruct
./scripts/foam view wing              # host ParaView

# Each case also has its own executable entry point:
./runs/run1/Allrun
```

Utilities and solvers write timestamped logs under `runs/NAME/logs/`. The
workflow stops on command failures and on a failed `checkMesh` report. After a
solver finishes, inspect its residuals and continuity errors: reaching
`endTime` alone does not demonstrate convergence. ParaView: open `case.foam`,
click **Apply**, select the latest time, color by **U → Magnitude** or **p**,
then use **Slice**, **Stream Tracer**, or **Plot Over Line**.

For a ready-to-mesh geometry example:

```bash
./scripts/foam new external-stl cube-demo
./scripts/import_geometry.sh cube-demo examples/geometry/cube.stl
./scripts/foam run cube-demo
```

For your own **STEP or STL**, follow [the geometry guide](docs/geometry.md).
It covers conversion, millimetres to metres, alignment, box size, fluid seed
points, surface checks, patches, layers, and internal flow.

## Layout and further reading

```text
src/foamctl.cpp       C++ case creation and command dispatch
scripts/             executable build, geometry, runtime, and case tools
setup/               installation script and platform instructions
templates/           clean, editable simulation inputs
runs/run1/           prepared cavity case; new runs are created alongside it
examples/geometry/   small watertight example STL
docs/                detailed workflow, geometry, and validation notes
cases/               original dictionary examples and syntax notes
build/               generated launcher binary (ignored)
```

- [Setup and environment](setup/README.md)
- [Case lifecycle, restarting, parallel runs, troubleshooting](docs/workflow.md)
- [STEP/STL geometry](docs/geometry.md)
- [Template details and adding other physics](templates/README.md)
- [Validation performed on this workspace](docs/validation.md)

These are small learning/starter cases. Choose material properties, boundary
conditions, turbulence treatment, domain size, mesh resolution, and time steps
for your particular problem. Check mass conservation, mesh/time-step
independence, and relevant experimental or analytical results before using a
result for design.
