# Optional CAD meshing examples

These OpenCFD dictionaries build a 3D external-flow mesh around a closed STL body.
Copy them to a working case's `system/` directory and remove `.example` from each
filename. Put your triangulated surface in `constant/triSurface/part.stl`.

- `blockMeshDict.example`: 3D background box, inlet/outlet/farField patches.
- `surfaceFeatureExtractDict.example`: extract sharp edges from `part.stl`.
- `snappyHexMeshDict.example`: refine near the body, retain the outside fluid,
  snap to the STL, use release-matched quality limits. Wall layers start disabled.

Edit the dimensions, scale, seed point, filenames, and refinement for your part.
After meshing, match every field in `0/` to the actual generated boundary patches.
These are meshing inputs, not a standalone physics case. The workspace's laminar
2D field files must be adapted before solving a new 3D model.

Read [CAD_IMPORT.md](../CAD_IMPORT.md) for the complete STEP/STL and Gmsh workflows.
Validation used a synthetic closed cube, not the user's CAD geometry. Standard
geometry and full topology checks passed; extended `checkMesh -allGeometry`
reported mildly concave cells in the snapped mesh. Inspect those diagnostics and
tune quality/resolution for the actual geometry before a production analysis.
