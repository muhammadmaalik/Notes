# Supporting scripts

**Create runs with the C++ generator in the workspace root:**

```bash
# If your terminal is currently in openFoam/scripts/:
cd ..
c++ -std=c++17 new_run.cpp -o new_run
./new_run
```

Edit `RUN_NAME` and `CPU_CORES` near the top of [new_run.cpp](../new_run.cpp).
Each generated run has its own commented inputs, `Allrun`, and `run_case.sh`.
Drop one STL/STEP in it, edit its geometry/flow settings, then use:

```bash
./Allrun --mesh-only
./Allrun --existing-mesh
```

The files in this directory support that workflow:

| File | Purpose |
| --- | --- |
| `run_geometry.sh` | Copied as `Allrun`: stage an STL or convert STEP with host Gmsh, then launch the local case runner. |
| `run_case.sh` | Mesh/check/initialize/solve; supports mesh-only and existing-mesh modes. |
| `clean_case.sh` | Optional cleanup for manually copied cases; preserves inputs and requires Python 3. |
| `plot_residuals.py` | Optional plotting utility, unrelated to run generation; requires Python 3 and matplotlib. |

The launchers use a loaded native OpenFOAM environment or Podman/Docker. Override
container selection with `OPENFOAM_RUNTIME` and `OPENFOAM_IMAGE`. They refuse
previous solver output to avoid accidentally reusing old results. For the usual
reset workflow, delete only your generated run folder and run the C++ generator
again. See [the workspace README](../README.md) for details.
