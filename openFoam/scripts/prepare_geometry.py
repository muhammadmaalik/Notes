#!/usr/bin/env python3
"""Normalize an ASCII/binary STL to one ASCII solid, optionally changing units.

This deliberately merges STL regions into the single body wall used by the
external-stl template. It does not repair holes or decide which side is fluid.
"""
import argparse
import math
from pathlib import Path
import struct
import sys


def read_triangles(path):
    data = path.read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from('<I', data, 80)[0]
        if 84 + 50 * count == len(data):
            return [tuple(tuple(v[j:j + 3]) for j in (3, 6, 9))
                    for v in struct.iter_unpack('<12fH', data[84:])]
    # Parse facets, not every third vertex in an arbitrary text file.
    triangles, vertices = [], None
    for line in data.decode('ascii').splitlines():
        words = line.split()
        if not words:
            continue
        key = words[0].lower()
        if key == 'facet':
            if vertices is not None:
                raise ValueError('Nested STL facet')
            vertices = []
        elif key == 'vertex':
            if vertices is None or len(words) != 4:
                raise ValueError('Vertex outside a valid facet')
            vertices.append(tuple(float(v) for v in words[1:]))
        elif key == 'endfacet':
            if vertices is None or len(vertices) != 3:
                raise ValueError('Each STL facet must have three vertices')
            triangles.append(tuple(vertices))
            vertices = None
    if vertices is not None:
        raise ValueError('Unterminated STL facet')
    return triangles


def normalize(source, destination, scale=1.0, center=False, translate=(0., 0., 0.)):
    if source.suffix.lower() != '.stl':
        raise ValueError('Expected .stl. Convert STEP using step_to_stl.py or a CAD tool first.')
    if not math.isfinite(scale) or scale <= 0 or not all(map(math.isfinite, translate)):
        raise ValueError('Scale must be finite and positive; translation must be finite')
    triangles = read_triangles(source)
    if not triangles or not all(math.isfinite(v) for tri in triangles for point in tri for v in point):
        raise ValueError('STL has no triangles or contains non-finite coordinates')
    lo = [min(p[i] for tri in triangles for p in tri) for i in range(3)]
    hi = [max(p[i] for tri in triangles for p in tri) for i in range(3)]
    offset = [(lo[i] + hi[i]) / 2 if center else 0 for i in range(3)]
    transform = lambda p: tuple((p[i] - offset[i]) * scale + translate[i] for i in range(3))
    output = ['solid body']
    for triangle in triangles:
        a, b, c = map(transform, triangle)
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        n = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2], u[0]*v[1] - u[1]*v[0])
        length = math.sqrt(sum(x*x for x in n))
        if not length or not math.isfinite(length):
            raise ValueError('STL has a zero-area or unrepresentable triangle; repair it in CAD')
        fmt = lambda p: ' '.join(f'{x:.12g}' for x in p)
        output += ['  facet normal ' + fmt(tuple(x / length for x in n)), '    outer loop']
        output += ['      vertex ' + fmt(p) for p in (a, b, c)]
        output += ['    endloop', '  endfacet']
    output.append('endsolid body')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: never silently replace an already imported model.
    with destination.open('x', encoding='ascii') as stream:
        stream.write('\n'.join(output) + '\n')
    print(f'Wrote {destination}: {len(triangles)} triangles, one wall region (body)')
    print('Bounding box in metres:', transform(lo), 'to', transform(hi))
    print('Now adjust blockMeshDict and locationInMesh; run surfaceCheck and inspect the mesh.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--scale', type=float, default=1.0, help='Coordinate multiplier; mm to m = 0.001')
    parser.add_argument('--center', action='store_true', help='Center bounding box before scaling/translation')
    parser.add_argument('--translate', nargs=3, type=float, default=(0., 0., 0.), metavar=('X', 'Y', 'Z'), help='Translation AFTER scaling, in metres')
    args = parser.parse_args()
    try:
        normalize(args.input, args.output, args.scale, args.center, args.translate)
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f'Geometry error: {error}\n')


if __name__ == '__main__':
    main()
