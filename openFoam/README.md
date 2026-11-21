# OpenFOAM simulation workspace

Reusable, commented starter cases for the **OpenCFD / openfoam.com** distribution.
The defaults use SI units and small structured meshes so you can inspect the
workflow before adapting it to your own geometry. See [EDITING_GUIDE.md](EDITING_GUIDE.md)
for what each file does, units, boundary conditions, and an editing checklist.
For STEP/STL or an existing volume mesh, start with [CAD_IMPORT.md](CAD_IMPORT.md)
and the commented [meshing examples](meshing/README.md).

| Template | Solver | Starting problem |
| --- | --- | --- |
| [01_incompressible](templates/01_incompressible/) | `simpleFoam` | Steady 2D laminar channel |
| [02_compressible](templates/02_compressible/) | `rhoCentralFoam` | Transient 1D ideal-gas shock tube |
| [03_multiphase](templates/03_multiphase/) | `interFoam` | Transient 2D water–air dam break |
| [04_heat_transfer](templates/04_heat_transfer/) | `buoyantSimpleFoam` | Steady 2D natural convection in air |
| [05_incompressible_stl](templates/05_incompressible_stl/) | `simpleFoam` | 3D external-flow CAD inputs for the C++ generator |

These are editable starting points, not a universal model for every flow. All five
start laminar. Turbulence, CAD meshes, moving meshes, combustion, and coupled
solid–fluid heat transfer need additional case-specific setup. OpenFOAM Foundation
(openfoam.org) releases use different solver/configuration conventions; do not mix
files from the two distributions without checking them.

## Your C++ run generator

Edit `RUN_NAME` (for example `"run1"` or `"run 2"`) and `CPU_CORES` near the top of
[new_run.cpp](new_run.cpp). From `openFoam/`, build and execute:

```bash
c++ -std=c++17 -Wall -Wextra -Wpedantic new_run.cpp -o new_run
./new_run
```

This creates **`runs/run1/`** with a complete, commented **3D incompressible
external-flow** setup. Drop one STL or STEP directly into that folder. Edit its
copied inputs for your geometry, units, inlet velocity, and fluid viscosity.
Then, from inside the run folder:

```bash
./Allrun --mesh-only       # Prepare geometry, build/check the mesh; inspect case.foam.
./Allrun --existing-mesh   # Solve using the mesh you just inspected.
```

The folder contains its own inputs and launch scripts; it can be moved elsewhere.
STL is staged automatically; STEP is converted to a surface STL with host Gmsh,
requesting metre coordinates. Gmsh is required only for STEP. No Python is needed
for this generator or its generated launcher. Surface conversion and meshing still
need geometry-specific domain size, resolution, and boundary choices.

The generator refuses to overwrite an existing run. To reset, delete that run
folder and execute `./new_run` again. To keep it and make another, change `RUN_NAME`,
rebuild, and execute. The generated run's README explains the editable settings.

For learning C++: the generator demonstrates filesystem paths, file copying,
streams, containers, exceptions, and automatic resource ownership (RAII).
OpenFOAM itself handles the simulation's computational memory.

## Other reference cases

From this `openFoam/` directory:

```bash
python3 scripts/new_case.py 01_incompressible my_channel --cores 1
cd cases/my_channel
# Edit the copied inputs before running.
../../scripts/run_case.sh --mesh-only
# Inspect case.foam in ParaView, then run the full case:
../../scripts/run_case.sh
```

The runner uses a sourced native OpenFOAM environment, or automatically selects
Podman then Docker. Set `OPENFOAM_RUNTIME=docker` to choose Docker explicitly.
Set `OPENFOAM_IMAGE=your-image:tag` to use a fixed compatible container release;
otherwise the existing `opencfd/openfoam-default:latest` default is used. Record the
version printed at startup because `latest` can change. Local validation used
OpenCFD **v2512**; see [VALIDATION.md](VALIDATION.md) for the checks performed.

From `openFoam/`, after the solver completes:

```bash
python3 scripts/plot_residuals.py cases/my_channel
```

Plotting requires `matplotlib`. Explicit shock-capturing updates may not produce
iterative residuals for every conserved field. Inspect the physical fields and
conservation errors as well as any residual plot.

## Workspace layout

- `templates/`: reference inputs; copy these before editing.
- `cases/`: working runs; outputs and local changes here are ignored by Git.
- `runs/`: independent CAD runs created by `new_run.cpp`; ignored by Git.
- `new_run.cpp`: editable C++17 generator; builds the local `new_run` executable.
- `scripts/`: clone, mesh/check/run, clean, and residual plotting helpers.
- `meshing/`: optional 3D CAD meshing dictionary examples; copy and adapt explicitly.
- `setup/`: existing platform installation helpers; these are not run automatically.

`0/` holds initial/boundary conditions, `constant/` holds material/physical models,
and `system/` holds meshing, numerics, and run controls. Configuration files contain
`//` comments next to the values you are likely to edit.
