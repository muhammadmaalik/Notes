# Simulation templates

`./scripts/foam new TYPE [NAME]` copies one complete case into `runs/NAME`.
Files here are clean inputs; generated meshes, logs, and solution directories
belong in runs. Template edits affect future copies only.

| Type | Physics | Initial fields | Mesh |
| --- | --- | --- | --- |
| `cavity` | Transient laminar incompressible, `icoFoam` | U, p | 2D blockMesh, 400 cells |
| `incomp` | Steady laminar incompressible, `simpleFoam` | U, p | 3D square duct, 2,560 cells |
| `transient` | Transient laminar incompressible, `pimpleFoam` | U, p | Same 3D duct |
| `external-stl` | Steady incompressible RANS SST, `simpleFoam` | U, p, k, omega, nut | blockMesh + snappyHexMesh |

See the main README's file table and [geometry guide](../docs/geometry.md).
Properties and solver duration are starting values, not a universal setup for
arbitrary fluids or shapes. The external template needs an imported STL.

## Adding a simulation type

For another channel/cavity variant, copy a suitable template, adjust inputs,
and add a registry entry to `src/foamctl.cpp`. Build with `scripts/build.sh`.
The new template's `controlDict/application` determines which solver runs.
Supply every required field, consistent boundary patches, transport/model
properties, and matching schemes/coupling settings. A solver-name change alone
does not define new physics.

The pre-existing `comp/`, `heat/`, and `multiphase/` directories are documented
extension areas, not selectable runnable templates. For compressibility,
thermal flow, or multiple phases, start from the **matching official v2606
tutorial** and retain its initialization/meshing steps. For a native/full
OpenFOAM tutorial installation, for example:

```bash
# Run in a Bash shell with the native OpenFOAM environment loaded.
find "$FOAM_TUTORIALS" -maxdepth 3 -type d
# Copy your chosen complete tutorial to a new directory before editing.
# Read and execute that tutorial's Allrun; steps differ by physics.
```

The pinned runtime container used here does not include the full tutorial
collection. Obtain the source/tutorial archive or an official development
installation through the [release page](https://www.openfoam.com/current-release).
Use the tutorial's own runner until its extra steps have been integrated into
`scripts/case_pipeline.sh`; this starter pipeline handles blockMesh, optional
single-body snappy, and single-region incompressible solvers.
