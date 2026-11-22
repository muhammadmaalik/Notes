# CAD and mesh import

Use [new_run.cpp](new_run.cpp) to create a run. It copies the active mesh settings
from `templates/05_incompressible_stl/system/` and provides matching 3D fields.
There is one CAD run-generation workflow; the steps below explain its inputs.

## Drop in an STL or STEP

1. Edit `RUN_NAME` in `new_run.cpp`, compile, and execute it from `openFoam/`:

   ```bash
   c++ -std=c++17 new_run.cpp -o new_run
   ./new_run
   ```

2. Drop one `.stl`, `.step`, or `.stp` directly in `runs/run1/` (or your chosen name).
3. Edit that run's domain bounds, refinement, fluid seed, inlet velocity, and viscosity.
4. From inside the run, use `./Allrun --mesh-only`; inspect the mesh and logs.
5. Use `./Allrun --existing-mesh` to solve on the inspected mesh.

The run's README contains the settings and units. Original CAD files remain in
its top level. The launcher stages a surface as `constant/triSurface/part.stl`.
STEP conversion uses host Gmsh and requests metres. STL coordinates must already
match the mesh scale; apply a millimetre conversion only once when necessary.
`./Allrun --prepare-only` performs just that staging/conversion.

## What gets meshed?

The supplied CAD profile is **external flow**: a solid body sits inside a surrounding
box, and cells fill the fluid outside it. `locationInMesh` must lie inside the fluid
to keep, away from mesh faces and body surfaces. The example box assumes a small
closed body near the origin; adapt it to your part.

Internal pipe/duct flow needs its actual connected fluid passage, correctly defined
inlet/outlet openings, and a seed inside that passage. The external-flow defaults
do not infer those from CAD. Coupled solid-fluid heat transfer needs multiple regions.

A STEP or STL is geometry, not a CFD volume mesh. The usual path is:

```text
STEP --Gmsh--> STL --blockMesh + snappyHexMesh--> constant/polyMesh/ --solver--> results
               ^
          or your own STL
```

## Which settings do what?

| File | Controls |
| --- | --- |
| `system/blockMeshDict` | Background box bounds, cell counts, patch names. |
| `system/surfaceFeatureExtractDict` | Sharp edges of the staged surface. |
| `system/snappyHexMeshDict` | Refinement, snapping, fluid selection, optional wall layers. |
| `system/controlDict` | Solver, duration/iterations, time step, saved output. |
| `system/fvSchemes` and `fvSolution` | Discretization, equation solves and convergence. |
| `0/U`, `0/p` | Initial values and conditions on the actual mesh patches. |
| `constant/transportProperties` | Fluid kinematic viscosity. |

The CAD profile already matches `inlet`, `outlet`, `farField`, and `body.*` patches.
Recheck names if you modify the surface regions or naming. Inspect units, retained
fluid region, cell quality, resolution and near-wall spacing before interpreting
results. The laminar model and educational default viscosity require review for
your actual flow regime.

## An existing volume mesh

For a Gmsh volume mesh, define the fluid volume and named physical boundary groups
in Gmsh. Export a linear ASCII MSH 2.2 mesh, copy it to the generated run, and in an
OpenFOAM shell run:

```bash
gmshToFoam fluid.msh
checkMesh -allTopology
touch case.foam
```

After checking scale and matching field boundary names, use the run's
`./Allrun --existing-mesh` launcher. This skips blockMesh/snappy and preserves
`constant/polyMesh/`. Keep the source mesh for reimporting after a reset.

## References

These inputs target OpenCFD v2512. Your installed `$FOAM_TUTORIALS` provides
release-matched references. The [Foundation development repository](https://github.com/OpenFOAM/OpenFOAM-dev)
is useful for concepts, but its solver conventions differ from this installation.

- [OpenCFD snappyHexMesh](https://doc.openfoam.com/2312/tools/pre-processing/mesh/generation/snappyhexmesh/)
- [Gmsh manual: STEP and surface/volume meshing](https://gmsh.info/doc/texinfo/)
- [Local validation and its limits](VALIDATION.md)
