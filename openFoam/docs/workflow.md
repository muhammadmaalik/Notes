# Case workflow

## Creating and editing

From the project root:

```bash
./scripts/foam new incomp my-channel
```

The C++ executable copies the selected template to `runs/my-channel` and adds
`Allrun` and `case.foam`. Omitting the name selects the next unused `runN`.
Names accept letters, numbers, underscores, and hyphens. Paths and existing
names are rejected. Compilation requires a C++17 compiler, but creating cases
does not need OpenFOAM or a container runtime.

Edit `runs/my-channel/0`, `constant`, and `system`. Use the file table in the
main README. Solvers read these files directly; no source recompilation is
needed for case input changes. To change the solver, use the matching template
so its fields, models, time schemes, and coupling controls are consistent.

The `incomp` channel is 1 × 0.1 × 0.1 m, with 40 × 8 × 8 cells, a 0.01 m/s
inlet, and `nu=1e-5 m²/s`, giving a Reynolds number of about 100 based on the
square duct's hydraulic diameter. This is a laminar starting point. The
transient version ends after only 0.2 s to demonstrate the workflow; a flow
traversal of this channel takes about 100 s. Extend the physical duration for
your study.

## Meshing and running

`mesh` runs `blockMesh` and checks topology/geometry. The STL template first
checks the surface, then runs `blockMesh`, `surfaceFeatureExtract`,
`snappyHexMesh -overwrite`, and `checkMesh -allTopology`. Cases with a
`system/meshQualityDict` also use `-meshQuality` to enforce those explicit
quality limits. The STL template includes that dictionary.

```bash
./scripts/foam mesh my-channel
./scripts/foam solve my-channel
```

`run` performs both stages, reusing a completed mesh. A successful mesh gets a
`.mesh-complete` marker and checksums of the known mesh dictionaries/surface.
Changing those files after meshing stops a solve, so it cannot silently reuse
an outdated mesh. Custom files referenced by your own `#include` directives
also require a new mesh when changed; they are not discovered automatically.
A failed or interrupted meshing attempt does not get
that marker, so the next solve cannot silently use an unfinished background
mesh. Once solution results exist, mesh changes require a fresh run; this
keeps old result fields attached to their original mesh. `check` reruns validation.
Do not copy mesh markers between cases.

Logs are stored under `runs/NAME/logs/`, with utility name, UTC timestamp, and
process ID. A lock prevents simultaneous runs/imports on one case. Different
cases can run at the same time. Both the mesher and solver stream their output
to the terminal. A failed command stops the pipeline; inspect its last log.

## Changing geometry after a run

Before any nonzero-time results or processor partitions exist, you can edit
the meshing dictionaries and run `./scripts/foam remesh NAME`. This discards
only the generated `constant/polyMesh`, rebuilds it, and checks it. For the
prepared `run1`, use this after changing its block dimensions/cell counts.

After results exist, create another run from the same template, copy your desired edited input
files into it, update geometry/mesh settings, and run it. The `mesh` command
refuses to overwrite existing topology. Geometry import also refuses to
replace an existing surface or modify an already meshed case. To discard an
incorrect import before meshing, explicitly remove only
`runs/NAME/constant/triSurface/body.stl` and re-import it.

## Serial restart

If nonzero time directories already exist, the workflow refuses a run starting
from time zero. To continue a completed serial simulation:

1. Set `startFrom latestTime;` in that run's `system/controlDict`.
2. Increase `endTime` beyond the newest saved time/iteration.
3. Run `./scripts/foam solve NAME`.

To start over from zero, create a new run. Never mix fields from one mesh with
another mesh. Native OpenFOAM command-line overrides are available through the
utility wrapper, but the normal workflow reads your edited dictionaries.

## Parallel solve

```bash
./scripts/foam new transient parallel-demo
./scripts/foam run parallel-demo --parallel 4
```

The workflow sets `numberOfSubdomains`, runs `decomposePar`, launches the solver
with `mpirun -np 4 ... -parallel`, then runs `reconstructPar`. The global mesh is
created and checked in serial first. Choose a process count suitable for the
mesh size and your available CPU cores. The small examples rarely benefit from
many processes.

Existing `processor*` directories cause a refusal, to avoid combining stale
partitions with new inputs. Automatic parallel restarts are not implemented.
Use a fresh run for another parallel experiment. If returning to serial after
a successful parallel run, verify reconstruction succeeded and global results
exist before manually removing the processor directories; set `startFrom
latestTime` to resume from reconstructed results. A failed parallel solve may
have newer fields only in its partitions: recover those using native OpenFOAM
tools before removing anything.

## Useful manual commands

The wrapper starts in the project root, with that root mounted as `/workspace`
inside a container. Use **project-relative paths** in wrapper commands:

```bash
./scripts/foam_exec.sh foamDictionary runs/run1/system/controlDict -entry endTime -value
./scripts/foam_exec.sh checkMesh -case runs/run1 -allTopology
./scripts/foam_exec.sh foamToVTK -case runs/run1 -latestTime
./scripts/foam_exec.sh postProcess -case runs/run1 -func 'mag(U)' -latestTime
```

Inputs outside this project are not visible in the container. Import STL files
with the host-side geometry helper first. The helper supports paths containing
spaces. The compiled launcher uses argument vectors rather than shell command
interpolation.

For additional diagnostics, `checkMesh -allGeometry` tests further geometric
properties, including cell concavity. Snappy transition cells can be flagged
by this extra test even when normal checks and the specified mesher quality
limits pass. Inspect flagged cells when relevant to your application; the
standard workflow uses topology checks and the case's explicit quality limits.

## Common problems

| Symptom | Check |
| --- | --- |
| Version mismatch | Set `FOAM_BASHRC` to v2606, or explicitly use the v2606 container |
| Missing compiler | Run the setup script, or install `gcc-c++`/`g++` |
| Missing STL | Use `import_geometry.sh` on an `external-stl` run |
| Missing patch field | Match all `0/*` boundary entries to `constant/polyMesh/boundary` |
| Missing/extra STL patch | Import as one solid, then remesh a new run |
| `locationInMesh` failure | Put the seed strictly inside the fluid and off mesh faces |
| Mesh check failure | Inspect the mesh and quality log; repair geometry or refine locally |
| Divergence/large Courant number | Check units, boundary conditions, viscosity, time step, mesh quality |
| No recent result files | Check `writeInterval` and whether the solver failed before writing |
| Existing results/partitions | Follow the restart instructions or use a fresh run |

The launcher handles file preparation and execution. Mesh adequacy, flow-model
selection, convergence, and physical validity remain case-specific decisions.
