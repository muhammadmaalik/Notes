# Mesh and numerical controls

    - `blockMeshDict`: dimensions, cell counts, grading, and named boundary faces.
    - `controlDict`: executable, duration, initial/adaptive time step, output frequency.
    - `fvSchemes`: space/time discretization appropriate to this solver.
    - `fvSolution`: equation solvers, coupling controls, convergence and relaxation.
    - `decomposeParDict`: one core by default; the runner uses MPI when greater than one.

Read the inline comments and the case README for defaults and editing dependencies.
