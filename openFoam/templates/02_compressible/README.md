# 02 - Compressible Flow (02_compressible)

Transient 1D Sod shock tube solved with rhoCentralFoam (Kurganov-Tadmor density-based shock-capturing solver).

- 0/        : Initial velocity U, absolute pressure p (10 kPa low side), and temperature T (278.746 K)
- constant/ : Ideal gas thermophysical properties (molWeight 28.96, Cp 1004.5, inviscid mu = 0) and laminar setting
- system/   : 10m shock tube (400x1x1), setFieldsDict for the 100 kPa driver section (x < 0), adaptive time step (maxCo 0.2), and vanLeer reconstruction
