# Steady incompressible channel

Solver: `simpleFoam` (OpenCFD).

2D laminar channel, 2 m long × 0.2 m high × 0.01 m thick; 80 × 20 × 1 cells. The inlet velocity is (1 0 0) m/s, walls are stationary, and outlet kinematic gauge pressure is zero. With nu=0.01 m²/s the height-based Reynolds number is 20.

## Edit first

- `0/U`: inlet speed and wall/outlet conditions.
- `constant/transportProperties`: kinematic viscosity nu, not dynamic viscosity mu.
- `system/blockMeshDict`: channel dimensions, 2D patches, and resolution.
- `system/fvSolution`: SIMPLE convergence targets and relaxation.

## Run controls and scope

Up to 1000 steady iterations, writing every 100. Pressure is p/rho in m²/s²; multiply pressure differences by your chosen constant density for Pa. This solver does not model compressibility or temperature.

All templates start laminar and use one core by default. Read the [editing guide](../../EDITING_GUIDE.md) before switching physics or moving to 3D.

```bash
# From openFoam/: clone this template before editing.
cp -rT templates/01_incompressible cases/my_run
cd cases/my_run
../../scripts/run_case.sh --mesh-only
../../scripts/run_case.sh
```
