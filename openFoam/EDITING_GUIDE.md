# Editing and reusing a case

For STEP geometry or an existing volume mesh, see [CAD_IMPORT.md](CAD_IMPORT.md).
It explains how CAD becomes a fluid mesh and includes copyable meshing examples.

## Workflow for a new simulation

1. Choose the closest physics family in `templates/`. From `openFoam/`, run
   `python3 scripts/new_case.py TEMPLATE my_run --cores 1`.
2. Edit `cases/my_run/system/blockMeshDict` for geometry and cell counts.
3. Update **every** field in `cases/my_run/0/` to match the mesh patch names and
   the physical conditions on each patch.
4. Edit material properties, gravity, and the flow model in `constant/`.
5. For shock-tube and dam-break cases, edit `system/setFieldsDict` too: it overrides
   the selected initial internal fields after the mesh is built.
6. Set duration, time step, output frequency, and numerical controls in `system/`.
7. From `cases/my_run/`, run `../../scripts/run_case.sh --mesh-only`. Read
   `log.checkMesh`, and inspect `case.foam` in ParaView, including initialized fields.
8. Run `../../scripts/run_case.sh`, read the solver log, and inspect results.
   Check mass conservation, mesh/time-step sensitivity, and physical plausibility.

Inputs under `cases/` are ignored by Git. To keep a customized reusable baseline,
copy only its input directories and documentation into a new named `templates/`
folder; do not include time directories, logs, `constant/polyMesh`, or processors.

## Which file controls what?

| File | What it controls | Usual edits |
| --- | --- | --- |
| `0/U` | Initial and boundary velocity [m/s] | Inlet vector, moving walls, outlet treatment |
| `0/p` | Kinematic or absolute pressure, depending on solver | Pressure datum or initial thermodynamic state |
| `0/p_rgh` | Pressure with hydrostatic contribution removed [Pa] | Wall flux consistency, open-boundary pressure |
| `0/T` | Absolute temperature [K] | Initial gas temperature, heated/cooled walls |
| `0/alpha.water` | Dimensionless water volume fraction | Incoming phase; initial fill is also in setFields |
| `constant/transportProperties` | Newtonian viscosity; phase density/surface tension in interFoam | Material values and phase names |
| `constant/thermophysicalProperties` | Equation of state, heat capacity, transport, energy variable | Gas properties and thermal model |
| `constant/turbulenceProperties` | Laminar/RAS/LES selection | Requires matching fields and numerics when changed |
| `constant/g` | Gravity [m/s²] | Direction and magnitude |
| `system/blockMeshDict` | Structured geometry, resolution, patch names | Vertices, cell counts, grading, faces |
| `system/setFieldsDict` | Region-based initialization after meshing | Shock location, left/right state, water column |
| `system/controlDict` | Executable, start/stop, time step, output | Duration, write interval, Courant limits |
| `system/fvSchemes` | Spatial and time discretization | Accuracy, boundedness, mesh corrections |
| `system/fvSolution` | Linear solvers, coupling, convergence, relaxation | Tolerances, correctors, stopping criteria |
| `system/decomposeParDict` | Parallel partitioning | `numberOfSubdomains`: 1 serial; >1 parallel |

Only the files needed by a given solver are present. Do not add temperature to an
isothermal case and expect the solver to start transporting heat.

## Reading a field file

```cpp
// OpenFOAM uses seven dimension exponents:
// [mass length time temperature amount electric-current luminous-intensity].
dimensions [0 1 -1 0 0 0 0];  // Velocity: metres / second.
internalField uniform (1 0 0); // Initial value, not a continuing source term.
boundaryField
{
    inlet
    {
        type fixedValue;
        value uniform (1 0 0); // Prescribed inlet velocity in x, y, z [m/s].
    }
}
```

Each patch in the mesh must have a compatible entry in every initial field.
Vectors use `(x y z)`, scalar values use a single number, and dictionary statements
end with `;`. Braces group dictionaries; parentheses group lists. `//` and
`/* ... */` are comments. Physical dimensions must match the solver equation.

| Quantity | OpenFOAM dimensions | Units |
| --- | --- | --- |
| Velocity | `[0 1 -1 0 0 0 0]` | m/s |
| Kinematic pressure in `simpleFoam` | `[0 2 -2 0 0 0 0]` | m²/s² |
| Absolute pressure or these cases' `p_rgh` | `[1 -1 -2 0 0 0 0]` | Pa |
| Temperature | `[0 0 0 1 0 0 0]` | K |
| Kinematic viscosity `nu` | `[0 2 -1 0 0 0 0]` | m²/s |
| Dynamic viscosity `mu` | `[1 -1 -1 0 0 0 0]` | Pa s |
| Volume fraction | `[0 0 0 0 0 0 0]` | Dimensionless |

For a constant-density case, `mu = rho*nu` and a physical pressure difference is
`deltaP = rho*delta(p)`. A zero kinematic gauge pressure at the outlet does not mean
vacuum. Compressible `p` is absolute and must remain positive; temperature is Kelvin.
`p_rgh = p - rho*(g dot position)` removes the hydrostatic contribution; account for
any chosen height/reference conventions when changing the geometry or pressure datum.

## Boundary conditions

| Type | Meaning | Typical use here |
| --- | --- | --- |
| `fixedValue` | Prescribed field value | Channel inlet U, outlet p, hot/cold T |
| `zeroGradient` | Zero normal gradient | Outflow or insulated T, where physically appropriate |
| `noSlip` | Stationary zero velocity | Solid walls |
| `empty` | No solved variation normal to patch | Both faces of a one-cell-thick suppressed direction |
| `fixedFluxPressure` | Pressure gradient consistent with prescribed flux and body forces | Buoyant/VOF impermeable walls |
| `inletOutlet` | Specified value on incoming flow, zero gradient on outgoing flow | Air entering the tank atmosphere |
| `pressureInletOutletVelocity` | Velocity compatible with pressure-driven inflow/outflow | Open tank surface |
| `totalPressure` | Prescribed total pressure | Tank atmospheric pressure datum |
| `calculated` | Boundary values supplied by the model | Derived thermodynamic p in heated cavity |

Changing a mesh patch to `wall` does not itself set no-slip velocity or thermal
conditions. Update the field files too. A simple `zeroGradient` outlet assumes
suitable outgoing flow and is not guaranteed to absorb acoustic waves or handle
strong backflow. A closed pressure system needs a consistent pressure reference.

## Geometry, resolution, and moving to 3D

`blockMeshDict` supplies vertices, hexahedral blocks, cell counts, grading, and
named boundary faces. `scale 1` means vertex coordinates are metres. If using
millimetres, `scale 0.001` converts those coordinates, but initialization boxes in
`setFieldsDict` must still use the resulting metre coordinates.

The channel, tank, and heated cavity suppress z with one cell and `empty` front/back
patches. The shock tube suppresses both y and z. For 3D, add cells in all resolved
directions, replace `empty` mesh patches with physical patches, and replace every
corresponding `empty` field condition. Refine near walls and interfaces, then compare
at least two resolutions. Uniform `simpleGrading (1 1 1)` is the starting setting.

For CAD, create a case-specific `constant/triSurface/` geometry and
`system/snappyHexMeshDict`; use an appropriate background `blockMeshDict` and, if
needed, `surfaceFeatureExtractDict`. The runner recognizes those files, but these
structured templates do not include a generic snappy dictionary: surface names,
refinement distances, layer settings, and the fluid-region selection depend on the
actual part. After meshing, match all generated patch names in `0/`.

## Changing physical models

The channel's viscosity is an educational value (`nu=0.01`), not a claim about water
or air. Its height-based Reynolds number is 20. The shock tube deliberately sets
`mu=0` for an inviscid ideal-gas benchmark. The water-air case has constant-density,
immiscible phases and no heat equation. The heated cavity includes fluid convection
and thermal diffusion; it has no solid region or solid conduction model.

For turbulence, first choose a suitable solver/model and wall treatment for your
Reynolds number and mesh. OpenCFD RAS commonly uses `simulationType RAS` and a `RAS`
dictionary with `RASModel kOmegaSST`, `turbulence on`, and `printCoeffs on`. That change
also requires physically initialized `k`, `omega`, and `nut` fields with suitable
wall/inlet conditions, plus model-specific schemes and linear solvers; thermal
models may also require `alphat`. Use the installed solver's matching RAS tutorial
as a complete reference. Do not switch the keyword alone or reuse laminar wall
spacing without checking the wall treatment and y+.

## Time stepping and convergence

Steady `simpleFoam` and `buoyantSimpleFoam` use `steadyState` discretization:
`deltaT=1` advances iteration labels, not physical time. `endTime` is an iteration
limit; `residualControl` can stop earlier. Under-relaxation in `fvSolution` damps
iteration updates. Smaller factors often help stability but slow convergence.

Transient solvers use seconds. Adaptive stepping is enabled, with a maximum time
step and Courant limit; the VOF case additionally limits the interface Courant
number. rhoCentralFoam must account for acoustic propagation even if U starts at
zero. Refined cells, faster waves, surface tension, or stronger forcing can require
smaller steps. Reduce the time step and compare results to establish sensitivity.

Linear-solver `tolerance` and `relTol` control individual equation solves;
`residualControl` controls the steady outer iterations. Neither establishes physical
accuracy by itself. Monitor continuity, pressure/temperature bounds, phase fraction
bounds, and the quantity you actually care about (flow rate, drag, heat flux, etc.).
Optional function objects belong in `controlDict/functions`; select their patches,
field names, units, and sampling locations for the actual geometry.

## Reruns, restarts, and cleanup

`run_case.sh` is a **fresh-run** tool. It remeshes, checks the mesh, runs setFields
when present, decomposes if cores > 1, solves, and reconstructs parallel output.
It refuses existing solver logs, processor output, or nonzero time directories.
After `--mesh-only`, a full fresh run is allowed and rebuilds the preprocessing.
For an imported or already inspected mesh, `--existing-mesh` skips mesh generation
and checks/initializes that mesh. This still starts the solver fresh; it is not a
restart flag. It can be combined with `--mesh-only`.

To rerun from the edited initial state, archive wanted results, then from the case
run `../../scripts/clean_case.sh`. This deletes generated times, processors, mesh,
logs, and post-processing output, while retaining `0/` and input dictionaries.
`setFields` modifies `0/`; changing only `0/p` or `0/alpha.water` may be overwritten
by the next initialization. Edit `setFieldsDict` to change those initial regions.

For a deliberate restart, retain the existing mesh and fields, set
`startFrom latestTime` in `controlDict`, and invoke the solver directly in the same
OpenFOAM environment. For parallel restarts, preserve consistent processor data and
use the correct MPI command. Do not use the fresh-run helper to resume a solution.

## Reference documentation

- [OpenCFD case structure and quickstart](https://doc.openfoam.com/2312/quickstart/)
- [simpleFoam inputs](https://doc.openfoam.com/2312/tools/processing/solvers/rtm/incompressible/simpleFoam/)
- [rhoCentralFoam inputs](https://doc.openfoam.com/2312/tools/processing/solvers/rtm/compressible/rhoCentralFoam/)
- [interFoam](https://doc.openfoam.com/2312/tools/processing/solvers/rtm/multiphase/interFoam/)
- [buoyantSimpleFoam inputs](https://doc.openfoam.com/2312/tools/processing/solvers/rtm/heat-transfer/buoyantSimpleFoam/)

Those links explain the solver families. Configuration was cross-checked against
the installed v2512 tutorials and tested locally; consult your installed release's
`$FOAM_TUTORIALS` when changing models or running another release.
