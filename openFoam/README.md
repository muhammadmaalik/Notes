# OpenFOAM Cross-Platform Simulation Workspace

Modular OpenFOAM repository built around the ESI-OpenCFD (openfoam.com) release branch.

## Folders
- setup/     : Cross-platform installers (Linux, macOS, Windows)
- scripts/   : Universal case runner, cleaner, cloner, and residual plotter
- templates/ : Clean baseline cases (01_incompressible, 02_compressible, 03_multiphase, 04_heat_transfer)
- cases/     : Working scratchpad for simulation runs (ignored by Git)

## Quick Start
1. Clone a template: python3 scripts/new_case.py 01_incompressible my_run --cores 2
2. Run the case:     cd cases/my_run && ../../scripts/run_case.sh
3. Plot residuals:   python3 scripts/plot_residuals.py cases/my_run
