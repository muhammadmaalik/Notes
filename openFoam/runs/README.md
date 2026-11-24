# Runs

`run1/` is a prepared 2D laminar cavity. Use `./scripts/foam run run1` from
the project root or `./runs/run1/Allrun` from any directory.

Create additional independent cases with `./scripts/foam new TYPE [NAME]`.
Each run contains editable inputs, its own mesh, logs, and results. Templates
remain clean. Generated meshes and results are ignored by Git; if cloning
this workspace, the first run regenerates the mesh from the included inputs.

See the main README and `docs/workflow.md` for execution and restarting.
