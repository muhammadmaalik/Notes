# Cavity: transient laminar benchmark

Solver: `icoFoam` (PISO). A 0.1 × 0.1 m square, 0.01 m thick, with
20 × 20 × 1 cells. Top lid moves at 1 m/s along +x; other physical walls are
stationary. Front/back are `empty` in both the mesh and fields, making this
2D. With `nu=0.001 m²/s`, Re = U L / nu = 100.

Edit `0/U` for lid speed, `constant/transportProperties` for viscosity,
`system/blockMeshDict` for dimensions/resolution, and `system/controlDict` for
physical end time and step size. The supplied run covers 0.5 s with a fixed
0.0025 s step. Check the reported Courant number after changes.

All walls use zero-gradient kinematic pressure; `pRefCell`/`pRefValue` in
`fvSolution` set the arbitrary pressure reference. No turbulence fields are
required. The short example demonstrates execution, not a formal benchmark
accuracy or steady-state convergence study.

From the project root: `./scripts/foam run NAME`, or use this case's `Allrun`.
