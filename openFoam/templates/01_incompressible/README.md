# 01 - Incompressible Flow (01_incompressible)

Steady-state 2D laminar channel flow solved with simpleFoam for constant-density fluids (Mach < 0.3).

- 0/        : Initial velocity U (1 m/s inlet, noSlip walls) and kinematic pressure p (0 outlet)
- constant/ : Newtonian kinematic viscosity (nu = 0.01 m^2/s) and laminar turbulence setting
- system/   : 2m x 0.2m channel mesh (80x20x1), 500-step steady controlDict, GAMG/smoothSolver settings, and 2-core scotch decomposition
