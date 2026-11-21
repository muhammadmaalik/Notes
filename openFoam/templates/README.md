# Reference simulation templates

Choose a physics family, clone it, and edit the copy. Every template contains
actual OpenFOAM input files in `0/`, `constant/`, and `system/`, with inline comments
explaining the defaults and editable settings. No geometry download is needed.

| Folder | Physics | Dimensions / mesh | Default duration |
| --- | --- | --- | --- |
| `01_incompressible` | Steady laminar channel | 2 × 0.2 × 0.01 m; 80 × 20 × 1 | Up to 1000 iterations |
| `02_compressible` | Inviscid ideal-gas shock tube | x = −5 to +5 m; 400 × 1 × 1 | 0.007 s |
| `03_multiphase` | Water–air free surface | 0.584 × 0.584 × 0.01 m; 46 × 46 × 1 | 0.5 s |
| `04_heat_transfer` | Ideal-gas natural convection | 0.1 × 0.1 × 0.01 m; 40 × 40 × 1 | Up to 5000 iterations |

Steady cases may stop early when their residual targets are reached. Those targets
are numerical stopping criteria, not proof of physical accuracy. Defaults use one
CPU core; `--cores N` while cloning changes decomposition in the new copy.

Read the chosen case README and the workspace [editing guide](../EDITING_GUIDE.md).
These cases target the OpenCFD distribution and were exercised with v2512.
