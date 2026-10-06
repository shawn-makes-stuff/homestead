"""Which meshes are one-sided: for each axis, the triangle area facing + and - (a closed mesh has both about equal).
usage: python tools/sides.py <mesh name> ...   (default: every catalog mesh)"""
import os, sys, warnings
sys.path.insert(0, os.path.dirname(__file__))
import meshes, colliders
warnings.filterwarnings('ignore')


def sides(name):
    m = colliders.load(name)
    n = m.face_normals * m.area_faces[:, None]
    return [(float(n[:, i].clip(0).sum()), float(-n[:, i].clip(max=0).sum())) for i in range(3)]


def one_sided(name, ratio=0.35):
    """Axes (0 x, 1 y, 2 z) whose weaker side has under `ratio` of the stronger side's area, with the missing side (+1/-1)."""
    out = []
    for i, (p, q) in enumerate(sides(name)):
        hi = max(p, q)
        if hi > 0.05 and min(p, q) < ratio * hi:
            out.append((i, -1 if p > q else 1))
    return out


if __name__ == '__main__':
    names = sys.argv[1:]
    if not names:
        import build_catalog
        names = [it['mesh'] for it in build_catalog.ITEMS]
    meshes.fetch(names)
    for n in names:
        s = sides(n)
        print('%-48s x %6.2f/%6.2f  y %6.2f/%6.2f  z %6.2f/%6.2f   one-sided: %s' % (n, *s[0], *s[1], *s[2], one_sided(n)))
