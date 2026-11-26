# Transient laminar channel

Solver: `pimpleFoam` (PIMPLE), laminar, same 1 × 0.1 × 0.1 m 3D duct as
`incomp`. Inlet U = 0.01 m/s; `nu=1e-5 m²/s`. Initial fields and wall/outlet
conditions are in `0/`.

The demo uses Euler time discretisation, adaptive time stepping with
`maxCo=0.5`, initial/max `deltaT=0.01 s`, end time 0.2 s, and output every
0.05 s. This short duration exercises the workflow. At this velocity, one
domain flow-through time is about 100 s; select a useful physical duration
and time-resolution study for your application.

Edit `controlDict` and PIMPLE settings in `fvSolution` for temporal controls.
For time-varying inlets, choose a suitable OpenFOAM boundary condition and
provide any required time tables. A transient solver alone does not make a
constant inlet time-varying.

From project root: `./scripts/foam run NAME [--parallel N]`.
