"""Openings (doors, windows) of a 3 m kit wall, as X intervals of the empty columns in its face (voxelized, looked at
along Y). A wall's back must have its openings in the same places, turned 180 degrees about Z (x -> -3 - x).
usage: python tools/openings.py <mesh> [<mesh> ...]"""
import os, sys
import numpy as np
import trimesh
sys.path.insert(0, os.path.dirname(__file__))
import meshes, colliders

P = 0.05


def openings(name, z0=0.3, z1=1.9):
    """[(x0, x1), ...] where nothing is between heights z0 and z1 (a door or window hole), in mesh X. The triangles are
    drawn flat onto the X-Z plane (looking along Y) and the columns with almost nothing drawn in that band are holes."""
    from PIL import Image, ImageDraw
    m = colliders.load(name)
    W, H = int(3 / P), int(4.5 / P)
    img = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(img)
    for tri in m.triangles:
        d.polygon([((x + 3) / P, (4.5 - z) / P) for x, _, z in tri], fill=255)
    a = np.asarray(img) > 0
    band = a[int((4.5 - z1) / P):int((4.5 - z0) / P)]
    empty = band.mean(axis=0) < 0.1
    xs = np.arange(W) * P - 3
    out, start = [], None
    for i, e in enumerate(empty):
        if e and start is None: start = xs[i]
        if not e and start is not None: out.append((round(float(start), 2), round(float(xs[i]), 2))); start = None
    if start is not None: out.append((round(float(start), 2), 0.0))
    return [o for o in out if o[1] - o[0] > 0.3]


def mirrored(ops): return sorted((round(-3 - b, 2), round(-3 - a, 2)) for a, b in ops)


def match(a, b, tol=0.12):
    return len(a) == len(b) and all(abs(x[0] - y[0]) < tol and abs(x[1] - y[1]) < tol for x, y in zip(sorted(a), sorted(b)))


if __name__ == '__main__':
    for n in sys.argv[1:]:
        d, w = openings(n, 0.3, 1.9), openings(n, 1.2, 1.9)
        print('%-56s door-height %s  window-height %s' % (n, d, w))
