# Steady laminar channel

Solver: `simpleFoam` (SIMPLE), with `simulationType laminar`. A 1 × 0.1 × 0.1 m
3D square duct, 40 × 8 × 8 cells. Inlet velocity is 0.01 m/s along +x,
`nu=1e-5 m²/s`, and Reynolds number based on hydraulic diameter is 100.

`0/U` sets the inlet and no-slip walls. The outlet uses
`pressureInletOutletVelocity`. `0/p` sets zero kinematic gauge pressure at
the outlet and zero-gradient conditions elsewhere. Pressure units are
m²/s²; multiply pressure differences by density to obtain Pa.

Edit velocity, viscosity, block dimensions/cell counts, and iteration limit
to suit your problem. Steady `endTime=500` is an iteration limit; `deltaT=1`
is not a physical transient step. Residual controls can stop the solve early.
Inspect residuals and mass balance. Do not use a laminar model for a turbulent
case without revisiting the model and its required fields.

From project root: `./scripts/foam run NAME`.
