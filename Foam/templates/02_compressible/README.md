# Transient compressible shock tube

Solver: `rhoCentralFoam` (OpenCFD).

1D inviscid ideal-gas tube from x=−5 to +5 m; 400 × 1 × 1 cells. Gas initially rests on both sides of x=0. The left driver has p=100000 Pa and T=348.432 K; the right state has p=10000 Pa and T=278.746 K. The y and z boundaries are empty.

## Edit first

- `system/setFieldsDict`: diaphragm location and both gas states; overrides internal p/T/U at startup.
- `0/p`, `0/T`, `0/U`: boundary conditions and consistent initial defaults.
- `constant/thermophysicalProperties`: ideal-gas molecular weight, Cp, mu and Pr.
- `system/controlDict`: end time, acoustic Courant limit, and output interval.

## Run controls and scope

Runs to 0.007 s with maxCo=0.2 and writes every 0.001 s. End patches use zeroGradient and are not exact nonreflecting boundaries; stop before waves reach them. mu=0 deliberately removes molecular viscosity and heat diffusion; rework the physics and numerics when modeling real viscous flow.

All templates start laminar and use one core by default. Read the [editing guide](../../EDITING_GUIDE.md) before switching physics or moving to 3D.

```bash
# From openFoam/: clone this template before editing.
cp -rT templates/02_compressible cases/my_run
cd cases/my_run
../../scripts/run_case.sh --mesh-only
../../scripts/run_case.sh
```
