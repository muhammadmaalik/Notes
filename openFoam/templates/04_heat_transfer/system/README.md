# Buoyant Solver & Mesh Controls (04_heat_transfer/system/)

- blockMeshDict : 0.1m x 0.1m closed 2D cavity (40 x 40 x 1 cells).
- controlDict   : Runs buoyantSimpleFoam for 500 steady-state iterations, writing every 100 steps.
- fvSchemes     : Steady-state derivatives with bounded Gauss linearUpwind for U and enthalpy h.
- fvSolution    : GAMG for p_rgh, smoothSolver for U and h, reference pressure cell at 100,000 Pa, and under-relaxation.
