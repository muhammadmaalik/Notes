#!/usr/bin/env python3
"""Tessellate STEP using optional Gmsh; output coordinates are in metres."""
import argparse
import math
from pathlib import Path
import sys
import tempfile

from prepare_geometry import normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--size', type=float, required=True, help='Maximum surface triangle size in metres (e.g. 0.005)')
    args = parser.parse_args()
    if args.input.suffix.lower() not in ('.step', '.stp') or not args.input.is_file():
        parser.error('Input must be an existing .step or .stp file')
    if args.output.suffix.lower() != '.stl' or args.output.exists():
        parser.error('Choose a new .stl output path; existing files are never overwritten')
    if not math.isfinite(args.size) or args.size <= 0:
        parser.error('--size must be finite and positive')
    try:
        import gmsh
    except (ImportError, OSError) as error:
        parser.exit(1, f'Gmsh is unavailable ({error}). See docs/geometry.md for installation or FreeCAD export.\n')
    gmsh.initialize()
    try:
        gmsh.option.setString('Geometry.OCCTargetUnit', 'M')
        gmsh.model.add('body')
        gmsh.model.occ.importShapes(str(args.input.resolve()))
        gmsh.model.occ.synchronize()
        if not gmsh.model.getEntities(2):
            raise ValueError('No CAD surfaces found')
        gmsh.option.setNumber('Mesh.MeshSizeMax', args.size)
        gmsh.option.setNumber('Mesh.MeshSizeMin', args.size / 10)
        gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 24)
        gmsh.option.setNumber('Mesh.Binary', 0)
        gmsh.option.setNumber('Mesh.StlOneSolidPerSurface', 0)
        gmsh.model.mesh.generate(2)
        with tempfile.TemporaryDirectory() as temp:
            surface = Path(temp) / 'surface.stl'
            gmsh.write(str(surface))
            normalize(surface, args.output)
    finally:
        gmsh.finalize()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit(f'STEP conversion failed: {error}')
