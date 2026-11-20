# 04 - Heat Transfer & Natural Convection (04_heat_transfer)

Steady-state buoyancy-driven natural convection in a closed 2D square cavity solved with buoyantSimpleFoam.

- 0/        : Temperature T (320 K hotWall, 280 K coldWall, insulated topAndBottom), noSlip velocity U, and p_rgh (100 kPa)
- constant/ : Gravity vector g (0 -9.81 0), ideal-gas air properties (mu = 1.8e-5, Pr = 0.71), and laminar setting
- system/   : 0.1m x 0.1m cavity (40x40x1), steady-state controlDict, enthalpy convection schemes, and GAMG/smoothSolver settings
