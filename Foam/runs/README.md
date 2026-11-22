# Independent generated runs

From `openFoam/`, compile `new_run.cpp` and execute `./new_run` to create `run1/`.
Change `RUN_NAME` near the top of the C++ source and rebuild to use another name.

Each generated folder contains its own commented inputs and launch scripts.
Drop one STL/STEP in it, edit its settings, and run `./Allrun --mesh-only`, followed
by `./Allrun --existing-mesh` once the mesh has been inspected.

To reset, delete only the generated run folder and execute the generator again.
Existing folders are never overwritten. These working runs are ignored by Git;
this README is retained. Your older working cases under `cases/` are independent.
