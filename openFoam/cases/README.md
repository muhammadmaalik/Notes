# Dictionary notes (original examples)

The files in this folder are reference snippets, not a complete runnable
case. Complete, mutually consistent inputs are under `templates/` and
`runs/run1/`. Create new cases using `./scripts/foam new TYPE [NAME]`.

## controlDict

The controlDict dictionary is used to specify the main case controls. This includes, e.g. timing information, write format, and optional libraries that can be loaded at run time.

## blockMesh

blockMesh is a strucutred hexahedral mesh generator. It's key features are:

* Strucutred Hex Mesh
* biult using blocks
* supports size grading
* supports curved block edges

It has some contraints:
* requires consitent block-to-block connectivity
* ordering of points is important

Well suited to simple geometries that can be described by a few blocks, but challenging to apply to cases with a large number of blocks due to book-keeping requirements, i.e. the need to manage point connectivity and ordering.


