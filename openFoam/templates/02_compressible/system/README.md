# Solver, Mesh & Shock Setup (02_compressible/system/)

- blockMeshDict : 10m shock tube from x = -5m to x = +5m (400 x 1 x 1 cells).
- setFieldsDict : Sets p = 100,000 Pa and T = 348.432 K for x in [-5, 0] (diaphragm at x = 0).
- controlDict   : Runs rhoCentralFoam to endTime 0.007s with adaptive time stepping (maxCo 0.2).
- fvSchemes     : Kurganov flux splitting with vanLeer TVD slope limiters.
- fvSolution    : Explicit diagonal updates for density, momentum, and energy.
