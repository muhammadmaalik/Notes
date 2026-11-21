# Initial and boundary conditions

`U`: velocity [m/s]. `T`: absolute temperature [K]. `p`: absolute thermodynamic pressure [Pa]. `p_rgh`: pressure with hydrostatic contribution removed [Pa].

All walls are noSlip; left/right T are 320/280 K and horizontal walls are insulated. `p` boundaries are calculated, while `p_rgh` uses fixedFluxPressure. Both pressure fields are required.

Each field contains inline comments. Patch names must match `system/blockMeshDict`.
