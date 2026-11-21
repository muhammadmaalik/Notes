# Case helper scripts

The primary drop-in CAD workflow is now the C++ generator [new_run.cpp](../new_run.cpp).
It copies `run_geometry.sh` as `Allrun` and `run_case.sh` into each `runs/RUN_NAME/`
folder. From that folder, `./Allrun --mesh-only` prepares a dropped STL/STEP and
meshes it; `./Allrun --existing-mesh` solves on the inspected mesh. No Python is
needed for that path. The Python clone command below remains available for the
other reference cases.

Run clone/plot commands from `openFoam/`. Run mesh/solve/clean commands from inside
an individual working case. Use Python 3 and Bash (WSL on Windows).

| Script | Usage and behavior |
| --- | --- |
| `new_case.py` | `python3 scripts/new_case.py 01_incompressible my_run --cores 2`: copy template, set positive core count, refuse overwrite/path traversal. Default: one core. |
| `run_geometry.sh` | Copied as `Allrun`: detect one root-level STL/STEP, stage/convert it, call the local run helper. STEP conversion uses host Gmsh and requests metres. |
| `run_case.sh` | From the copy: `../../scripts/run_case.sh`; mesh, check quality, initialize, run serial or MPI, reconstruct, create `case.foam`. |
| `run_case.sh --mesh-only` | Mesh, check, initialize, create `case.foam`, stop before solver. Full run can follow this check. |
| `run_case.sh --existing-mesh` | Preserve `constant/polyMesh/` from an importer or prior meshing. Skip blockMesh/snappy; check, initialize and solve. Combine with `--mesh-only` to stop before solving. |
| `clean_case.sh` | From the case: remove generated output and mesh, preserve `0/` and dictionaries. Archive wanted results first. Requires Python 3. |
| `plot_residuals.py` | `python3 scripts/plot_residuals.py cases/my_run` or pass a solver-log path; writes `residuals.png`. Requires matplotlib. |

The runner sources native `RunFunctions` when OpenFOAM is loaded; otherwise it uses
Podman, or Docker if Podman is not installed. Override via `OPENFOAM_RUNTIME` and
`OPENFOAM_IMAGE`. Container execution uses the same runner as native execution.
It stops on failed commands or mesh checks and refuses old solver output to prevent
silently reusing previous logs. This is a fresh-run helper, not a restart tool.

Cleanup preserves existing initial fields, including changes made by `setFields`.
The next fresh run applies `setFieldsDict` again. Read [the editing guide](../EDITING_GUIDE.md)
before changing initialization or restarting a saved calculation.
