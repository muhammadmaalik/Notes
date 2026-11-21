# Initial and boundary conditions

`U`: shared velocity [m/s]. `p_rgh`: pressure with hydrostatic contribution removed [Pa]. `alpha.water`: dimensionless water fraction.

Walls are noSlip for U, fixedFluxPressure for p_rgh, and zeroGradient for alpha. The open top permits outflow and admits air. `setFieldsDict` sets the water column.

Each field contains inline comments. Patch names must match `system/blockMeshDict`.
