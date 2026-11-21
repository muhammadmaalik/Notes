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

These are editable starting points, not a universal model for every flow. All four
start laminar. Turbulence, CAD meshes, moving meshes, combustion, and coupled
solid–fluid heat transfer need additional case-specific setup. OpenFOAM Foundation
(openfoam.org) releases use different solver/configuration conventions; do not mix
files from the two distributions without checking them.

## Create and run a case

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
- `scripts/`: clone, mesh/check/run, clean, and residual plotting helpers.
- `meshing/`: optional 3D CAD meshing dictionary examples; copy and adapt explicitly.
- `setup/`: existing platform installation helpers; these are not run automatically.

`0/` holds initial/boundary conditions, `constant/` holds material/physical models,
and `system/` holds meshing, numerics, and run controls. Configuration files contain
`//` comments next to the values you are likely to edit.
