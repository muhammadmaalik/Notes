# Steady natural convection in air

Solver: `buoyantSimpleFoam` (OpenCFD).

Closed 2D cavity, 0.1 × 0.1 × 0.01 m; 40 × 40 × 1 cells. Left wall is 320 K, right wall 280 K, horizontal walls insulated. All walls are no-slip. Ideal-gas air starts at 300 K and 100000 Pa absolute; gravity acts in −y.

## Edit first

- `0/T`: hot/cold wall and initial temperatures in Kelvin.
- `0/p`: initial absolute pressure, setting the initial gas mass; keep 0/p_rgh consistent.
- `constant/thermophysicalProperties`: Cp, dynamic viscosity mu and Pr.
- `system/fvSolution`: steady convergence, relaxation and pressure-correction reference.

## Run controls and scope

Up to 5000 steady iterations, writing every 100. The solver also requires 0/p alongside U/T/p_rgh. pRefValue=0 is a pressure-correction reference, not zero absolute thermodynamic pressure. This is fluid convection/diffusion only; conjugate heat transfer through solids requires a multi-region setup.

All templates start laminar and use one core by default. Read the [editing guide](../../EDITING_GUIDE.md) before switching physics or moving to 3D.

```bash
# From openFoam/: clone this template before editing.
cp -rT templates/04_heat_transfer cases/my_run
cd cases/my_run
../../scripts/run_case.sh --mesh-only
../../scripts/run_case.sh
```
