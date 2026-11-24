# Importing STEP and STL geometry

## What the template simulates

`external-stl` represents **fluid around a closed solid body** inside a box.
The background box supplies inlet, outlet, and far-field boundaries. The
surface becomes the no-slip `body` wall. The solid interior is removed by
`snappyHexMesh`; the connected fluid containing `locationInMesh` is retained.

OpenFOAM's [surface geometry documentation](https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/geometry/)
describes triangulated inputs in `constant/triSurface`. STEP is CAD geometry;
convert it to a surface triangulation before using this workflow. An STL is a
surface, not a volume mesh. `blockMesh` and `snappyHexMesh` create the volume
mesh used by the solver.

## STL: import, scale, position

```bash
./scripts/foam new external-stl my-part
./scripts/import_geometry.sh my-part /absolute/path/to/part.stl
```

For a model exported in millimetres, centered about its bounding box:

```bash
./scripts/import_geometry.sh my-part '/path with spaces/part.stl' --scale 0.001 --center
```

The second example is an alternative to the first: import once into a fresh
run. `--scale 0.001` converts mm to m; `0.01` converts cm to m; `0.0254` converts
inches to m. STL does not encode units. The script prints the resulting
bounding box in metres so you can compare it with the background box.

Optional `--translate X Y Z` moves the centered/scaled model by metres. The
operation order is: center (if selected), scale, then translate. For rotation,
export with the desired orientation from CAD, or transform a separate surface
using OpenFOAM's [surfaceTransformPoints](https://doc.openfoam.com/2606/tools/pre-processing/mesh/manipulation/surfaceTransformPoints/)
before import. This helper accepts ASCII and binary STL and writes one ASCII
solid named `body`. It merges all STL regions into one wall, recomputes facet
normals from vertex order, and rejects empty/non-finite/zero-area geometry.
It does **not** repair holes, inconsistent winding, or intersections.

The imported copy is `runs/my-part/constant/triSurface/body.stl`. The source
model is left intact. An existing destination is never overwritten.

## STEP option 1: CAD export

In FreeCAD or another CAD program:

1. Open the `.step`/`.stp` model; inspect and repair it as a solid.
2. Select the body/surfaces you need for the fluid boundary. Avoid exporting
   duplicate assembly parts, internal details, or construction geometry.
3. Create a surface mesh with a tessellation fine enough to resolve curves,
   gaps, and the smallest relevant feature. Smaller chordal/angular deviation
   increases triangle count. Check the units used by the exporter.
4. Export that mesh as STL. Import it with the helper above using the correct
   coordinate scale. Inspect its printed bounds.

The [FreeCAD manual](https://www.freecad.org/manual/a-freecad-manual.pdf)
describes importing CAD and exporting mesh formats. STL removes the original
CAD face names; this starter importer deliberately treats the whole model as
one wall patch.

## STEP option 2: command-line Gmsh conversion

The optional Python converter uses Gmsh's OpenCASCADE STEP importer. Install
Gmsh into a local virtual environment (host-side; independent of OpenFOAM):

```bash
python3 -m venv .venv-cad
.venv-cad/bin/python -m pip install gmsh
.venv-cad/bin/python scripts/step_to_stl.py /path/to/part.step examples/geometry/my-part.stl --size 0.005

./scripts/foam new external-stl my-cad-case
./scripts/import_geometry.sh my-cad-case examples/geometry/my-part.stl
```

`--size` is the maximum surface triangle size in **metres**, here 5 mm. The
converter sets `Geometry.OCCTargetUnit` to `M` before STEP import, so the output
is already in metres. **Do not apply the millimetre conversion again.** STEP
units must be correctly encoded in the source. Check the printed bounds. Gmsh
may require host OpenGL/GLU libraries; an import error reports missing shared
libraries. Use your distribution's Gmsh package or CAD export if preferred.
See the [Gmsh API and unit documentation](https://gmsh.info/doc/texinfo/).

This creates a single-region STL. It does not generate a ready-to-solve
OpenFOAM volume mesh or assign inlet/outlet patches. For an assembly, remove
overlapping/internal surfaces in CAD first; surface meshing an entire assembly
does not automatically produce a valid union of solids.

## Fit the fluid domain

Before meshing, edit these files in your new run:

1. **`system/blockMeshDict`:** default box is x = -2 to 6 m and y,z = -1 to 1 m,
   with 40 × 10 × 10 cells. Fit the box around your scaled body. Leave enough
   clearance upstream, downstream, and laterally to test sensitivity to domain
   blockage and wake length. Change vertex coordinates and cell counts together.
2. **`system/snappyHexMeshDict`:** `body.stl` is already referenced.
   `refinementSurfaces/body/level (2 2)` halves the background cell size twice.
   Increase refinement where needed; cell count grows rapidly.
3. **`locationInMesh`:** choose a point strictly inside the background mesh,
   outside the solid body, and in the connected fluid region you want to keep.
   Avoid points on surfaces or mesh faces. The default `(-1.73 0.13 0.17)` is
   chosen for the included cube and is not universal. See
   [castellation controls](https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/castellation/).
4. **`0/U`:** set inlet and initial velocity (flow is along +x by default).
   The default is 1 m/s. Set the outlet's initial value consistently.
5. **`constant/transportProperties`:** default air-like `nu=1.5e-5 m²/s`.
   Set your fluid's viscosity at the relevant conditions.
6. **`0/k`, `0/omega`:** choose inlet turbulence quantities for your flow. The
   example `k=0.00375 m²/s²` corresponds to 5% intensity at 1 m/s using
   `k=1.5*(U*I)^2`. With mixing length 0.05 m and `Cmu=0.09`,
   `omega=sqrt(k)/(Cmu^0.25*L)` is about 2.24 s⁻¹. Recalculate after changing U.

## Check and mesh

```bash
./scripts/foam mesh my-part
./scripts/foam view my-part
./scripts/foam solve my-part
```

The pipeline follows the documented
[snappyHexMesh sequence](https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/):
surface check → background mesh → sharp-feature extraction → refinement and
snapping → volume-mesh check. Review the `surfaceCheck` log for boundary edges,
non-manifold edges, disconnected components, and topology. Review meshing logs
and the final `checkMesh` report. A successful command exit is not a guarantee
that arbitrary surfaces represent the intended fluid volume. View the mesh
before running a long solve.

The template supplies `U`, `p`, `k`, `omega`, and `nut` conditions for inlet,
outlet, the four far-field planes, and `body`. If you preserve multiple STL
regions manually, update **every** initial field to match the resulting patch
names in `constant/polyMesh/boundary`; do not use this single-region importer
when distinct wall conditions are required.

## Boundary layers and forces

Layer addition is disabled for the initial mesh (`addLayers false`). Optional
layer controls are included, but the default coarse mesh is a workflow demo.
For wall shear, drag, or heat-transfer studies, design the near-wall mesh for
your turbulence model and target y+, then verify layer coverage and achieved
y+ in the solution. The [turbulence guide](https://doc.openfoam.com/2606/tools/processing/models/turbulence/)
and [layer controls](https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/layers/)
describe the relevant requirements.

For optional forces, add to the run's `controlDict`:

```foam
functions
{
    #include "forces"
}
```

Edit `system/forces`: set density `rhoInf` and moment reference `CofR`. Results
are written under `postProcessing/forcesOnBody`. Validate mesh, near-wall
resolution, and convergence before interpreting force values. `checkMesh`
cannot establish that a mesh is sufficiently resolved for your physics.

## Internal pipe/duct flow

A pipe's metal solid and the **fluid volume inside it** are different regions.
The supplied STL case is configured for external flow. For an internal-flow
case, prepare a closed fluid envelope with distinct inlet, outlet, and wall
surface regions; use a seed point **inside that fluid volume**; define those
regions in snappy and all `0/*` fields. Inlet/outlet faces must be patches with
flow conditions rather than no-slip walls. Do not flatten those regions with
the single-wall importer. Start with the supplied `incomp`/`transient` channel
for a simple duct, or adapt an official internal-flow snappy tutorial for your
CAD geometry.
