# External STL: steady RANS SST

Solver: `simpleFoam`; model: `kOmegaSST`. Background box spans x=-2..6 m,
y,z=-1..1 m. Inlet U=1 m/s, air-like `nu=1.5e-5 m²/s`, 5% example inlet
turbulence. The single body is a no-slip wall; four box sides are individual
symmetry planes, inlet is on -x, and pressure outlet is on +x.

From project root:

```bash
./scripts/import_geometry.sh NAME /path/to/model.stl --scale 0.001 --center
./scripts/foam mesh NAME
./scripts/foam view NAME
./scripts/foam solve NAME
```

Use scale 0.001 only for coordinates in millimetres. STEP must first be
tessellated; see `docs/geometry.md`. Import flattens STL regions to one `body`
wall. No surface is preselected in this template; an example cube is supplied
at `examples/geometry/cube.stl` in metres.

Fit the background box and change `snappyHexMeshDict/locationInMesh` to a point
in your fluid, outside the solid. Update all five initial fields if patches
change. Layer addition is initially disabled. Tune layers and y+ for your
model and intended measurements. The coarse demonstration mesh is not a
validated drag-prediction mesh.

`system/forces` is an optional function-object include; set density/reference
point and include it inside `functions {}` in `controlDict` to enable forces.
