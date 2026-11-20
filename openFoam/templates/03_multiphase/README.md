# 03 - Multiphase Free-Surface Flow (03_multiphase)

Transient 2D water-air dam break solved with interFoam using the Volume of Fluid (VOF) method.

- 0/        : Phase fraction alpha.water (0 = air, 1 = water), dynamic pressure p_rgh, and velocity U
- constant/ : Gravity vector g (0 -9.81 0), water/air densities and viscosities, surface tension (0.07 N/m), and laminar setting
- system/   : 0.584m x 0.584m open tank (46x46x1), setFieldsDict water column (0.146m x 0.292m), MULES interface compression, and PIMPLE solver settings
