# Importing CAD and meshes

A STEP file describes CAD geometry. A CFD solver needs cells filling the **fluid
region**. `controlDict` controls the run; it does not import geometry or generate
those cells. These notes and examples target the installed OpenCFD v2512 branch.

```text
STEP CAD ──export triangulated surface──> STL ──snappyHexMesh──> volume cells
STEP CAD ──mesh the fluid volume in Gmsh──────────────────────> MSH ──gmshToFoam──> volume cells
                                                                            ↓
                                                              constant/polyMesh/
                                                                            ↓
                                                  fields + materials + solver settings
```

## Decide what you are meshing

- **External flow:** for a wing or other solid part, the fluid is outside the part,
  inside a surrounding computational box. Keep the outside fluid, not the solid.
- **Internal flow:** for a pipe or duct, mesh its connected internal passage. Wall
  thickness is solid material, not the fluid domain. Inlet/outlet openings need
  well-defined fluid boundaries.
- **Solid–fluid heat transfer:** both regions need meshes and coupling; the single
  fluid-region heat template is not a conjugate heat-transfer case.

Check model scale, orientation, gaps, tiny features, and disconnected regions
before meshing. STL has no reliable unit metadata: a coordinate value of 100 might
mean 100 mm to CAD but 100 m to the CFD case. Inspect the bounding box and convert
once. A physically closed fluid/solid separation is the most straightforward
starting point for these examples.

## Route A: STEP → STL → snappyHexMesh

1. Open the STEP model in your CAD application or an appropriate CAD/meshing tool.
   Export a triangulated STL surface representing the relevant boundary. Set its
   tessellation fine enough to preserve curvature and small features of interest.
2. Clone a physics case. Put the surface at
   `cases/my_part/constant/triSurface/part.stl`.
3. Copy the commented examples in `meshing/` into the working case's `system/`,
   removing the `.example` suffix. They replace the template's simple channel mesh
   with a **3D external-flow box**; they are not automatically suitable for your part.
4. Edit the domain bounds, STL name/scale, refinement levels, and `locationInMesh`.
   This point must be inside the connected fluid region to keep, off the surface
   and off mesh faces. The supplied point assumes a small body near the origin.
5. Mesh and inspect before trying to solve. Layer addition is disabled initially;
   wall-resolved or wall-function studies need deliberate wall spacing/layer design.

From `openFoam/`, after exporting `part.stl`:

```bash
python3 scripts/new_case.py 01_incompressible my_part --cores 1
mkdir -p cases/my_part/constant/triSurface
# Copy your exported part.stl into the directory above.
cp meshing/blockMeshDict.example cases/my_part/system/blockMeshDict
cp meshing/snappyHexMeshDict.example cases/my_part/system/snappyHexMeshDict
cp meshing/surfaceFeatureExtractDict.example cases/my_part/system/surfaceFeatureExtractDict
# EDIT these copies for your actual geometry before proceeding.
cd cases/my_part
../../scripts/run_case.sh --mesh-only
```

That helper runs `blockMesh`, `surfaceFeatureExtract`, `snappyHexMesh -overwrite`,
and `checkMesh`. The resulting topology is in `constant/polyMesh/`. Inspect
`log.snappyHexMesh`, `log.checkMesh`, and `case.foam`. A successful quality check does
not establish adequate resolution or wall-layer coverage.

The example starts with `inlet`, `outlet`, and `farField` box patches, then adds a
`body` wall for a single-region surface. Multi-region surfaces can create additional
patches. Read the actual `constant/polyMesh/boundary` after meshing. Update every
field in `0/` to match those actual names before solving. In particular, remove the
channel's `empty` front/back conditions when making this a 3D case.

For a constant-density laminar external-flow example, `U` might prescribe an inlet
velocity, use zeroGradient at the outlet, slip at the distant side boundaries, and
noSlip on the body. `p` might use a fixedValue outlet datum and zeroGradient on the
other patches. Those choices still need suitable domain placement, flow regime,
and outlet/backflow treatment. The channel's default viscosity is educational;
replace it with your fluid's properties before interpreting aerodynamic results.

Once the mesh and fields are ready, preserve the inspected mesh when solving:

```bash
../../scripts/run_case.sh --existing-mesh
```

## Route B: an existing Gmsh volume mesh → OpenFOAM

Gmsh can import STEP through its OpenCASCADE geometry kernel. Define the actual
fluid volume, name boundary surfaces with **Physical Surface** groups (for example
inlet/outlet/walls), define the **Physical Volume**, and generate a 3D volume mesh.
A surface-only triangulation is not a 3D CFD volume mesh.

For the OpenCFD `gmshToFoam` path, use linear elements and export ASCII MSH 2.2 for a
simple interoperable starting format. Surface/volume entity IDs depend on your CAD:
there is no universal numbering to paste into a general template. Confirm all
required cells and boundary groups are exported; inspect conversion warnings.

Copy the mesh to the working case as `fluid.msh`. From inside that case, in a shell
with OpenFOAM loaded:

```bash
gmshToFoam fluid.msh
checkMesh -allTopology -allGeometry
touch case.foam
```

Conversion populates `constant/polyMesh/`. Check mesh units, patch names/types,
connectivity and cell quality, then match every field boundary in `0/`. If the mesh
was exported in millimetres, convert its coordinates to metres before solving;
do not scale both the mesher export and the imported mesh.

Run the solver with the imported mesh preserved:

```bash
../../scripts/run_case.sh --existing-mesh --mesh-only  # Check and initialize only.
../../scripts/run_case.sh --existing-mesh              # Check, initialize, solve.
```

Without `--existing-mesh`, a remaining `blockMeshDict` triggers remeshing. Also,
`clean_case.sh` deletes `constant/polyMesh`: keep the original `.msh` so you can
reimport it. Region initialization boxes in `setFieldsDict` must match the new
geometry and metre coordinates.

## Using individual OpenFOAM commands with your container

The run helper starts the container automatically. Commands such as `gmshToFoam`
or `surfaceCheck` need an OpenFOAM shell. From a working case on the host:

```bash
podman run --rm -it --userns=keep-id -v "$PWD:/case:Z" -w /case \
  --entrypoint /bin/bash docker.io/opencfd/openfoam-default:latest
# Now inside the installed v2512 container:
source /usr/lib/openfoam/openfoam2512/etc/bashrc
surfaceCheck constant/triSurface/part.stl  # For the STL route.
# Or: gmshToFoam fluid.msh                # For the volume-mesh route.
exit
```

The source path above matches the installed image; adjust it if you choose another
release. Your case files persist through the mounted directory. CAD conversion and
Gmsh meshing can happen on the host; the container supplies OpenFOAM utilities.

## The dictionaries in plain language

| File | Its job |
| --- | --- |
| `blockMeshDict` | Make a structured mesh, often the background box for CAD meshing. |
| `surfaceFeatureExtractDict` | Detect sharp edges on an STL/OBJ surface. |
| `snappyHexMeshDict` | Refine/cut/snap volume cells to the surface and optionally add wall layers. |
| `constant/polyMesh/` | The actual mesh produced by a mesher/importer. |
| `controlDict` | Choose the solver, start/stop time or iterations, time steps and output frequency. |
| `fvSchemes` | Choose how derivatives/fluxes are approximated on those cells. |
| `fvSolution` | Choose equation solvers, pressure–velocity coupling, tolerances and relaxation. |
| `0/` | Set initial values and conditions on each mesh boundary. |

## About the GitHub repository you linked

[OpenFOAM/OpenFOAM-dev](https://github.com/OpenFOAM/OpenFOAM-dev) is the OpenFOAM
**Foundation development** repository. Its [README](https://github.com/OpenFOAM/OpenFOAM-dev/blob/master/README.org)
and [tutorials](https://github.com/OpenFOAM/OpenFOAM-dev/tree/master/tutorials) are
useful references. The current tutorials include modular solver families such as
`incompressibleFluid`, `fluid`, and `shockFluid`, as well as mesh tutorials.

Your installed `opencfd/openfoam-default` image and these templates are from the
**OpenCFD/openfoam.com** distribution. Use your installed `$FOAM_TUTORIALS` as the
first source of runnable dictionaries; adapt concepts from Foundation examples
while checking names, model files, syntax and solver entry points. The linked
repository's development branch is not the exact release tested here.

References:

- [OpenCFD snappyHexMesh workflow](https://doc.openfoam.com/2312/tools/pre-processing/mesh/generation/snappyhexmesh/)
- [Supported surface geometry and its location](https://doc.openfoam.com/2312/tools/pre-processing/mesh/generation/snappyhexmesh/geometry/)
- [Meshing controls](https://doc.openfoam.com/2312/tools/pre-processing/mesh/generation/snappyhexmesh/quick-reference/)
- [Gmsh reference manual, including STEP/OpenCASCADE and mesh formats](https://gmsh.info/doc/texinfo/gmsh.pdf)

The example dictionaries are a tested meshing starting point for a synthetic closed
surface. Your STEP model has not been imported or tested; its domain, units,
boundary names, refinement and physics must be configured for that particular model.
