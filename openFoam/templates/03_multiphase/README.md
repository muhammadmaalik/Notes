# Transient water–air free surface

Solver: `interFoam` (OpenCFD).

2D open tank, 0.584 × 0.584 × 0.01 m; 46 × 46 × 1 cells. A 0.146 m wide × 0.292 m high water column starts at the lower left, with air elsewhere. Gravity acts in −y. Walls are no-slip; the open top admits air and permits outflow.

## Edit first

- `system/setFieldsDict`: initial water shape and fill; alpha.water=1 is water, 0 is air.
- `constant/transportProperties`: both phase densities/viscosities and surface tension.
- `constant/g`: gravity magnitude and direction.
- `0/alpha.water`, `0/U`, `0/p_rgh`: atmosphere and wall conditions.

## Run controls and scope

Runs to 0.5 s with maxCo=maxAlphaCo=0.5 and writes every 0.05 s. The pressure datum at the atmosphere is zero gauge Pa. This model is isothermal and uses incompressible phases; it does not simulate compressible air pockets, phase change, or heat transfer.

All templates start laminar and use one core by default. Read the [editing guide](../../EDITING_GUIDE.md) before switching physics or moving to 3D.

```bash
# From openFoam/: clone this template before editing.
python3 scripts/new_case.py 03_multiphase my_run --cores 1
cd cases/my_run
../../scripts/run_case.sh --mesh-only
../../scripts/run_case.sh
```
