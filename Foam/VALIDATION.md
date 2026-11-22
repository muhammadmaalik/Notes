# Local validation

Checked on **November 20, 2026 (America/New_York)** with the installed
`docker.io/opencfd/openfoam-default:latest` image, reporting **OpenCFD v2512**
(build `_87ed40d2-20251219`). `latest` is mutable; these results apply to that
installed build and the supplied defaults.

All solver runs used disposable cloned cases under `/tmp`, preserving reference
inputs and the user's working cases. Final saved dictionaries were used for the
following runs:

| Check | Result |
| --- | --- |
| Incompressible channel, one core | Mesh passed; simpleFoam met its configured residual criteria in 98 iterations. |
| Compressible shock tube, one core | Mesh and setFields passed; rhoCentralFoam reached 0.007 s and ended normally. |
| Water–air dam break, one core | Mesh and setFields passed; interFoam reached 0.5 s and ended normally. |
| Heated cavity, one core | Mesh passed; buoyantSimpleFoam met the configured 1e-4 outer residual criteria in 2053 iterations. |
| Incompressible channel, two cores | Decomposition, MPI solver and reconstruction passed; convergence in 99 iterations. |
| Automatic Podman workflow | Mesh-only run followed by full channel solve completed using automatic container startup. |
| CAD meshing examples | Closed synthetic cube STL: blockMesh, feature extraction and snappyHexMesh completed; 24462 cells; standard geometry and full topology checks passed. |
| Existing-mesh workflow | Checking a pre-existing mesh skipped generation and preserved every mesh file byte for byte. |
| Clone validation | Invalid core counts, path traversal, missing templates and destination overwrite rejected. |
| Cleanup preservation | Generated times/processors/mesh/logs removed; initial fields, dictionaries, similarly named notes and user symlinks preserved. |
| Script checks | Bash syntax and Python parsing passed; git diff whitespace checks passed. |

The CAD mesh had maximum non-orthogonality approximately 28.84 degrees and maximum
skewness approximately 0.351. Extended `checkMesh -allGeometry` additionally reported
600 concave cells; those diagnostics need assessment for a geometry-specific study.
The normal runner uses standard geometry checks plus `-allTopology` and refuses
reported failures. Layer addition was disabled for the CAD mesh test.

These checks establish that the supplied defaults mesh, initialize, and execute in
this installation. They are not mesh-independence, time-step-independence, benchmark
accuracy, or experimental validation studies. The user's STEP geometry was not
provided or imported. Gmsh STEP conversion, other distributions, native installs,
Docker, and non-Linux hosts were not exercised.

## C++ independent-run workflow — November 21, 2026

The new `new_run.cpp` and `05_incompressible_stl` profile were checked separately
using disposable runs under `/tmp` and the same installed OpenCFD v2512 image.

- Compiled as C++17 with `-Wall -Wextra -Wpedantic -Werror`, without warnings.
- Created a complete independent run with executable local launchers and no Python files.
- Confirmed existing runs and their edits are not overwritten; deleting a disposable
  run and executing the generator recreates clean inputs.
- Rejected unsafe names, invalid core counts, dangling destination links, and missing
  inputs. A run name with spaces and a two-core configuration generated correctly.
- Moved a generated folder outside its source workspace; its STL preparation,
  mesh-only workflow, and local solver launcher continued to work.
- Converted a synthetic STEP cube with Gmsh, including an uppercase extension and
  spaces in the filename. Confirmed bounds of ±200 mm became ±0.2 m in the STL.
- Confirmed uppercase STL handling, byte-preserving STL staging, missing/ambiguous
  geometry rejection, and forwarding mesh-only/existing-mesh arguments.
- Meshed the converted synthetic surface, passed standard mesh checks, and ran
  the generated 3D laminar external-flow case to its configured residual criteria
  in **143 iterations**.

The real user STL files and existing `cases/my_part` were preserved. The newly
created `runs/run1/` contains clean inputs and launchers, with no geometry or results.
Testing used a synthetic cube; arbitrary CAD models still require geometry-specific
domain bounds, units, resolution, flow properties, and model selection.
