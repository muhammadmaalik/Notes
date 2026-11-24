# Validation record

Checked on **23 November 2026**, on Fedora 44, using rootless Podman and the
official `docker.io/opencfd/openfoam-run:2606` image. The runtime reported
`WM_PROJECT_VERSION=v2606` and `/usr/lib/openfoam/openfoam2606`.

## Actual OpenFOAM runs

| Case | Execution | Observed result |
| --- | --- | --- |
| Cavity (`run1`) | blockMesh → checkMesh → icoFoam | 400 cells; Mesh OK; reached 0.5 s; final maximum Co ≈ 0.4083 |
| Steady channel | blockMesh → checkMesh → simpleFoam | 2,560 cells; Mesh OK; residual controls met in 65 iterations |
| Transient channel | blockMesh → checkMesh → decomposePar → two-process pimpleFoam → reconstructPar | Reached 0.2 s; reconstructed global fields successfully |
| External cube STL | STL normalization → surfaceCheck → blockMesh → surfaceFeatureExtract → snappyHexMesh → checkMesh → simpleFoam SST | Closed body patch; 7,984 cells; explicit mesh-quality checks passed; residual controls met in 82 iterations |
| Remesh | `foam remesh run1`, with no solution outputs | Rebuilt and checked the 400-cell mesh successfully |
| STEP conversion | Gmsh 4.15.2 → STEP → `step_to_stl.py` | A 500 mm cube became a 542-triangle STL with bounds -0.25 to +0.25 m on each axis |

For the cube, final maximum non-orthogonality was about 28.17° and maximum
skewness about 0.3434. All configured face-quality error counts were zero.
An exploratory `checkMesh -allGeometry` flagged 448 concave cells. The normal
workflow instead runs `-allTopology` and, for the STL case, `-meshQuality` using
the explicit `system/meshQualityDict` limits. That diagnostic difference is
documented in `docs/workflow.md`; it is not an accuracy certification. Layers
remain disabled in the starter STL case.

These are execution and consistency checks, not a mesh-independence study,
experimental validation, or proof that these settings fit your geometry.
Temporary validation runs were removed. `runs/run1` retains its checked mesh
and editable initial inputs; generated solution time directories were removed
so it is ready to run from zero.

To repeat the principal checks on fresh cases:

```bash
./scripts/foam doctor
./scripts/foam new cavity check-cavity
./scripts/foam run check-cavity
./scripts/foam new incomp check-steady
./scripts/foam run check-steady
./scripts/foam new transient check-transient
./scripts/foam run check-transient --parallel 2
./scripts/foam new external-stl check-stl
./scripts/import_geometry.sh check-stl examples/geometry/cube.stl
./scripts/foam run check-stl
```

## Launcher and geometry checks

The C++17 launcher builds with `-Wall -Wextra -Wpedantic`. All shell scripts
pass `bash -n`. Eight host-side integration tests pass:

- Independent, complete case creation, automatic numbering, executable Allrun,
  and refusal to overwrite an edited case.
- Rejection of unknown simulation types, path traversal, and invalid options.
- Binary STL with a `solid` header, scaling from millimetres, and normalized
  single-region ASCII output.
- Rejection of degenerate geometry without creating a destination.
- Refusal to import new geometry into an already meshed case.
- Use of the current checkMesh log, and refusal of failed checks even when
  checkMesh exits with status zero.
- Refusal to remesh a case with saved solution results.
- Detection of changed meshing inputs before solving.

```bash
./scripts/build.sh
python3 -m unittest discover -s tests -v
```

The tests use temporary projects under `/tmp`, leaving your run inputs intact.
