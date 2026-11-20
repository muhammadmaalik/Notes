# VOF Solver & Water Column Setup (03_multiphase/system/)

- blockMeshDict : 0.584m x 0.584m open tank (46 x 46 x 1 cells) with walls and open atmosphere top.
- setFieldsDict : Sets alpha.water = 1 in the initial 0.146m x 0.292m left water column.
- controlDict   : Runs interFoam to endTime 0.5s with adaptive time stepping (maxCo 0.5, maxAlphaCo 0.5).
- fvSchemes     : Van Leer interface advection with linearUpwind momentum convection.
- fvSolution    : MULES interface compression (cAlpha = 1), PCG/DIC pressure solver, and 3 PIMPLE correctors.
