# Solver & Mesh Controls (01_incompressible/system/)

- blockMeshDict    : 2m x 0.2m x 0.01m channel mesh (80 x 20 x 1 cells).
- controlDict      : Runs simpleFoam for 500 steady-state iterations, writing every 100 steps.
- fvSchemes        : Steady-state time derivative with bounded Gauss linearUpwind convection.
- fvSolution       : GAMG for p, smoothSolver for U, residual target 1e-4, relaxation U=0.9 and p=0.3.
- decomposeParDict : Splits mesh into 2 subdomains using scotch for parallel runs.
