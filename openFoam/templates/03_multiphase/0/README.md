# Initial & Boundary Conditions (03_multiphase/0/)

- alpha.water : Water volume fraction (0 = air, 1 = water) with inletOutlet on the open atmosphere boundary.
- p_rgh       : Dynamic pressure p - rho*g*x (Pa), fixedFluxPressure on walls and totalPressure 0 at atmosphere.
- U           : Velocity field (m/s), noSlip on walls and pressureInletOutletVelocity at atmosphere.
