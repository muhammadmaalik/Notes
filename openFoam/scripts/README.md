# Universal Automation Scripts (scripts/)

- new_case.py       : Clones a template from templates/ into cases/ and sets CPU cores
- run_case.sh       : Auto-detects mesh, setFields, solver, and parallel settings to run any case
- clean_case.sh     : Deletes generated time steps, processor folders, meshes, and logs
- plot_residuals.py : Parses log.*Foam and saves a convergence plot as residuals.png
