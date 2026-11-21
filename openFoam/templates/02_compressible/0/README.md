# Initial and boundary conditions

`U`: initial velocity [m/s]. `p`: absolute pressure [Pa]. `T`: absolute temperature [K].

Ends use zeroGradient; transverse patches are empty in y and z (one cell in each). `setFieldsDict` initializes the two internal gas states after meshing.

Each field contains inline comments. Patch names must match `system/blockMeshDict`.
