# Your independent incompressible CAD run

This is a 3D, steady, **laminar external-flow** case using OpenCFD `simpleFoam`.
All inputs and launch scripts are copied here. You can move this folder elsewhere,
edit it, or delete it and generate a fresh run. No links to the templates are used.

## Use this run

1. Drop **one** `.stl`, `.step`, or `.stp` file directly beside this README.
   Uppercase extensions and filenames with spaces work. If you keep several
   geometry files here, set `GEOMETRY_FILE` near the top of `Allrun` explicitly.
2. Edit the copied settings below for the body, fluid and intended conditions.
3. From a terminal inside this folder, run `./Allrun --mesh-only`.
4. Inspect `case.foam` in ParaView and the meshing logs. Check that the retained
   region is fluid outside the body, and the surface and mesh use the right units.
5. Run `./Allrun --existing-mesh` to solve on the inspected mesh.

`./Allrun` also supports a full fresh mesh-and-solve in one command.
`./Allrun --prepare-only` just stages/converts the surface without OpenFOAM.

## Settings you will edit

| File | Edit |
| --- | --- |
| `system/blockMeshDict` | Surrounding box bounds, cell counts and grading. |
| `system/snappyHexMeshDict` | Surface scale, refinement, fluid seed `locationInMesh`, optional wall layers. |
| `0/U` | Inlet velocity vector and initial velocity, both in m/s. |
| `constant/transportProperties` | Kinematic viscosity `nu` in m²/s; the default 0.01 is educational. |
| `constant/turbulenceProperties` | Starts laminar; RAS needs additional fields and numerical settings. |
| `system/controlDict` | Maximum steady iterations and output frequency. |
| `system/decomposeParDict` | Cores; 1 runs serial, more than 1 uses MPI. |
| `system/fvSolution` | Convergence criteria, relaxation and pressure corrections. |

The example box extends from x=-1 to 3 and y,z=-1 to 1 metres. Its seed point
assumes a small closed body near the origin. **Those are example dimensions, not
automatic measurements of your geometry.** Keep the body away from domain boundaries
and choose a fluid seed inside a cell outside the solid.

The field files already match `inlet`, `outlet`, `farField`, and `body.*` patches.
The body is no-slip; outer side faces use slip. Inspect the actual mesh boundary
names if you edit surface naming or import multiple regions. There are no 2D
`empty` conditions. Internal duct/pipe flow requires its own fluid domain, openings,
seed, and boundary setup; this external-flow profile does not infer those from CAD.

## STL and STEP

STL is copied into `constant/triSurface/part.stl`. Its coordinates must match metres;
for a millimetre STL, enable `scale 0.001;` in `snappyHexMeshDict` exactly once.

STEP is converted automatically with **Gmsh on the host**, using its STEP units and
requesting metres. Keep the snappy surface scale at 1 for that path. Gmsh's default
surface tessellation is a starting point: inspect curvature and small features,
then adjust tessellation/refinement for your model. This conversion is surface
triangulation; OpenFOAM still builds the CFD volume mesh afterward. If Gmsh is
unavailable, export STL in CAD and replace the STEP with that STL.
See the [Gmsh manual](https://gmsh.info/doc/texinfo/) for STEP import and meshing options.

OpenFOAM runs natively if its environment is loaded; otherwise the included helper
uses Podman or Docker. `OPENFOAM_RUNTIME` and `OPENFOAM_IMAGE` override the defaults.
You need Bash, a compatible OpenCFD environment/container, and Gmsh only for STEP.
Creating this run and running its launcher do not require Python.

## Start over

Existing results are protected against accidental overwrite. To completely start
over, leave this folder, delete **this run folder only**, and execute the C++
generator again. It recreates the same name from clean inputs. To keep the old
run, change `RUN_NAME` in `new_run.cpp`, rebuild, and execute it to make another.
Editing this folder changes only this run; edit the source template only when you
want a new default for future runs.

For a deliberate restart from a saved time, use the OpenFOAM solver directly with
appropriate restart controls; the included launcher performs a fresh-run workflow.
