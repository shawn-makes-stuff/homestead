"""Box colliders for a mesh: voxelize its glb and merge the voxels into few boxes (greedy, best of 6 axis orders).
Fallout's converted models get theirs from model_boxes() (tools/fo4/convert.py's collision stage: from the shapes each
model saved, so a change here redoes only this - the import's 'collision' step - not the whole conversion): fitted to
Fallout's own collision bodies (havok_boxes), voxelized from the render mesh only for a model without them.

Boxes are in mesh space (Z up, the .mesh's own frame): (cx, cy, cz, hx, hy, hz), or turned (cx, cy, cz, hx, hy, hz,
qi, qj, qk, qr: the box's axes in mesh space, as entities.lua colliderOf and LiveNav take them).
usage (check): python tools/colliders.py <mesh name> [pitch]
"""
import itertools, os, sys, warnings
import numpy as np, trimesh
from scipy import ndimage
from scipy.spatial import ConvexHull
sys.path.insert(0, os.path.dirname(__file__))
import meshes
warnings.filterwarnings('ignore')


def load(name):
    """The mesh's triangles in mesh space (the glb is Y-up: x, y, z = gx, -gz, gy)."""
    s = trimesh.load(meshes.find(name)[:-5] + '.glb')
    g = s.dump(concatenate=True) if hasattr(s, 'dump') else s
    v = np.asarray(g.vertices)
    return trimesh.Trimesh(np.c_[v[:, 0], -v[:, 2], v[:, 1]], g.faces, process=False)


def greedy(occ, order):
    occ = occ.transpose(order).copy()
    boxes = []
    n = occ.shape
    for idx in zip(*np.nonzero(occ)):
        if not occ[idx]: continue
        a, b, c = idx
        a1 = a
        while a1 + 1 < n[0] and occ[a1 + 1, b, c]: a1 += 1
        b1 = b
        while b1 + 1 < n[1] and occ[a:a1 + 1, b1 + 1, c].all(): b1 += 1
        c1 = c
        while c1 + 1 < n[2] and occ[a:a1 + 1, b:b1 + 1, c1 + 1].all(): c1 += 1
        occ[a:a1 + 1, b:b1 + 1, c:c1 + 1] = False
        lo, hi = np.array([a, b, c]), np.array([a1 + 1, b1 + 1, c1 + 1])
        inv = np.argsort(order)
        boxes.append((lo[inv], hi[inv]))
    return boxes


def boxes(name, pitch=0.1, extrude=None, minvol=0.0):
    """extrude = axis index (0 x, 1 y, 2 z): flatten the occupancy along it, so a wall becomes full-thickness
    rectangles around its openings. Boxes under minvol m3 (trims, bolts) are dropped."""
    return mesh_boxes(load(name), meshes.info(name)[:2], pitch, extrude, minvol)


def mesh_boxes(m, bounds, pitch=0.1, extrude=None, minvol=0.0):
    """boxes() for a loaded mesh (mesh space) with its bounds (min, max), filled (a room's surfaces only: tight())."""
    vg = trimesh.voxel.creation.voxelize(m, pitch).fill()
    occ = vg.matrix.astype(bool)
    origin = vg.transform[:3, 3] - pitch / 2       # corner of voxel [0,0,0]
    if extrude is not None:
        flat = occ.any(axis=extrude, keepdims=True)
        occ = np.zeros_like(occ); occ[tuple(slice(None) if i != extrude else slice(0, 1) for i in range(3))] = flat
    best = min((greedy(occ, o) for o in itertools.permutations(range(3))), key=len)
    mn, mx = bounds
    out = []
    for lo, hi in best:
        a, b = origin + lo * pitch, origin + hi * pitch
        if extrude is not None:
            a[extrude], b[extrude] = mn[extrude], mx[extrude]
        if np.prod(b - a) < minvol: continue
        out.append(tuple(round(float(x), 3) for x in (*((a + b) / 2), *((b - a) / 2))))
    return out


def tight(m, pitch, minvol=0.0, fill=False):
    """surface boxes: voxelized as trimesh does (subdivided to pitch/2 edges, a cell per vertex), gaps of up to two
    cells closed (between planks, joists, treads: the big shack 4,685 -> 3,216 boxes at 0.1 m; no body fits one),
    merged, then a face with no cell next to it is pulled in to the furthest vertex inside the box + pitch/4. A cell
    overshoots its surface by up to a whole cell: at 0.25 m the shack's stairwell edges stood into the opening and the
    head bumped (user, 2026-10-02). pitch/4: no crack where a surface crosses into a diagonal neighbour (its vertices
    are under pitch/2 apart); faces against a neighbour stay put (no crack in a floor split in two boxes). fill: what
    the surface closes in is solid too (a closed shape: fewer, bigger boxes)."""
    v = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=pitch / 2, max_iter=10)[0]
    hit = np.round(v / pitch).astype(int)
    h0 = hit.min(axis=0) - 1; hit -= h0                     # (a cell of margin: closing reaches the edges)
    occ = np.zeros(hit.max(axis=0) + 2, bool); occ[tuple(hit.T)] = True
    occ |= ndimage.binary_closing(occ, np.ones((3, 3, 3), bool))
    if fill: occ = ndimage.binary_fill_holes(occ)
    origin = h0 * pitch - pitch / 2
    best = min((greedy(occ, o) for o in itertools.permutations(range(3))), key=len)
    lab = np.zeros(occ.shape, np.int32)
    for i, (lo, hi) in enumerate(best): lab[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] = i
    k = lab[tuple(hit.T)]
    vmin = np.full((len(best), 3), np.inf); vmax = np.full((len(best), 3), -np.inf)
    np.minimum.at(vmin, k, v); np.maximum.at(vmax, k, v)
    out = []
    for i, (lo, hi) in enumerate(best):
        a, b = origin + lo * pitch, origin + hi * pitch
        if np.prod(b - a) < minvol: continue
        for ax in range(3 if np.isfinite(vmin[i, 0]) else 0):   # (all closed cells, no vertex: as it is)
            side = [slice(lo[j], hi[j]) for j in range(3)]
            side[ax] = slice(lo[ax] - 1, lo[ax]) if lo[ax] > 0 else slice(0, 0)
            if not occ[tuple(side)].any(): a[ax] = max(a[ax], vmin[i, ax] - pitch / 4)
            side[ax] = slice(hi[ax], hi[ax] + 1)
            if not occ[tuple(side)].any(): b[ax] = min(b[ax], vmax[i, ax] + pitch / 4)
        out.append(tuple(round(float(x), 3) for x in (*((a + b) / 2), *((b - a) / 2))))
    return out


def ground(v, mn, mx):
    """Where a piece touches the ground, in its own space: artists put a prop's floor at z = 0 (anything lower is
    buried), and the footprint is the XY box of what reaches down to that floor. A street lamp's base is its pole, not
    the middle of its arm's bounds."""
    v = np.asarray(v)
    z0 = 0.0 if mn[2] < 0 <= 0.5 * mx[2] and (v[:, 2] > -0.02).any() else mn[2]
    foot = v[(v[:, 2] >= z0 - 0.02) & (v[:, 2] <= z0 + max(0.05, 0.1 * (mx[2] - z0)))]
    if len(foot) < 3: foot = v
    return [round(float((foot[:, 0].min() + foot[:, 0].max()) / 2), 3), round(float((foot[:, 1].min() + foot[:, 1].max()) / 2), 3), round(float(z0), 3)]


BOXES_MAX = 48


def is_wall(size): return sorted(size)[0] < 0.9 and sorted(size)[1] > 1.5


def walkin(mesh):
    """a shape big enough to walk into (1.8 m each way, not a wall): for Fallout's structures, rooms() keeps its inside"""
    size = mesh.bounds[1] - mesh.bounds[0]
    return not is_wall(size) and size.min() >= 1.8


ROOM_PITCH = (0.1, 0.125, 0.15, 0.2)


def rooms(ms, cap):
    """a structure's walk-in shapes (rooms, prefabs, towers) as surfaces, so rooms can be entered: all in one grid
    (shapes that touch share boxes), coarser cells a step at a time while over cap, 0.2 m at most. tight() keeps the
    openings' edges and headroom near the mesh whatever the cell. Was shape by shape at 0.1 m, then one 0.25 m pass
    for the lot: the big shack's stairwell lost its headroom (user had to crouch)."""
    m = trimesh.util.concatenate(ms)
    for p in ROOM_PITCH:
        b = tight(m, p, minvol=0.0005)
        if len(b) <= cap: break
    return [list(x) for x in biggest(b, cap)]               # (still over at 0.2 m: its smallest go - it once kept them all)


def biggest(boxes, n):
    """at most n of the boxes, the smallest (trims, bolts) left out; in their order"""
    if len(boxes) <= n: return boxes
    keep = set(sorted(range(len(boxes)), key=lambda i: -float(np.prod(boxes[i][3:6])))[:max(n, 0)])
    return [b for i, b in enumerate(boxes) if i in keep]


# Fallout's collision layers (tools/fo4/havok.py, each body's; niftools' names, 31 and 49 matching their node names)
COLLIDE = {1, 2, 3, 4, 10, 26}                               # static, anim static (doors), transparent (glass), clutter,
                                                             # props, transparent small (fences): colliders
RAMP = 31                                                    # stair helper: the ramp a character walks up a flight on.
                                                             # The rest (12 trigger, 14 trap, 15 non-collidable, 22 and
                                                             # 23 zones, 49 Fallout's navmesh cuts) go


BOX_CAP = 400                                                # collision boxes a prop may have (user, 2026-10-02: the
                                                             # Molecular Beam Emitter's 5,505 cost 20 fps held; placed,
                                                             # 86 collider components and a nav grid rebuild to match)
WALK_CAP = 1500                                              # and a structure (Fallout's Structures menu), all told


def coarsen(per, cap):
    """fewer boxes for a prop with far too many: per shape (or Fallout part) [points, its boxes], the ones with the
    most boxes replaced by one box round their points, most first, until under cap"""
    while sum(len(b) for _, b in per) > cap and any(len(b) > 1 for _, b in per):
        i = max(range(len(per)), key=lambda k: len(per[k][1]))
        per[i][1] = [box_of(per[i][0])]
    return [b for _, bs in per for b in bs]


def heft(shapes, walk):
    """about how many GB model_boxes() needs for these shapes: rooms() grows with the walk-in shapes' area (measured
    2026-10-03, 8 structures: 1.6-10.6 MB a m2 - the big shack's 1,384 m2 took 6.7 GB), everything else little"""
    if shapes and len(shapes[0]) == 4: return 0.3           # (Fallout's bodies: no rooms())
    return 0.3 + 0.008 * sum(m.area for m in (trimesh.Trimesh(v, f, process=False) for v, f in shapes) if walk and walkin(m))


def model_boxes(shapes, walk):
    """a converted model's (or a moving part's) collision from its shapes in metres, its space -> dict(boxes, col):
    Fallout's bodies [(vertices, triangles, layer, radius)] (col 'havok', with ramps: havok_boxes), else the
    render mesh's [(vertices, triangles)] (col 'voxel'): each shape by shape_mesh(), a structure's (walk) walk-in ones
    together as surfaces (rooms); a prop at most BOX_CAP (coarsened), a structure WALK_CAP (never coarsened - its
    smallest boxes left out, if it comes to that)"""
    if shapes and len(shapes[0]) == 4: return havok_boxes(shapes, walk)
    return dict(boxes=voxel_boxes(shapes, walk), col='voxel')


def voxel_boxes(shapes, walk):
    ms = [trimesh.Trimesh(v, f, process=False) for v, f in shapes]
    room = [walk and walkin(m) for m in ms]
    inside = [m for m, r in zip(ms, room) if r]
    boxes = [b for m, r in zip(ms, room) if not r for b in shape_mesh(m)]
    cap = WALK_CAP if walk else BOX_CAP
    if inside: boxes += rooms(inside, max(cap - len(boxes), cap // 2))   # (half the cap at least: it once went negative)
    elif not walk and len(boxes) > cap: boxes = coarsen([[m.vertices, shape_mesh(m)] for m in ms], cap)   # (a lattice prop: the beam emitter had 5,505;
                                                             # never a structure - it took the scaffold watchtower's
                                                             # 1,077 boxes to 58, not walkable)
    return [[round(float(v), 3) for v in b] for b in biggest(boxes, cap)]


# Fallout's own collision -> boxes. Fallout's collision is simple on purpose (a chair: 4 parts) and lines up with the
# snap grid, so boxes fitted to it feel like Fallout and overlap no neighbour (the voxel boxes overhung the grid,
# stood a cell over treads and seats, and a thin sloped porch roof came out a 0.84 m slab). Per connected part of a
# body: closed and convex -> one box round it, grown by its convex radius (most polytopes are 8-corner boxes already),
# turned only when the axis-aligned one would hold over 10% more; closed, not convex (a rail on its posts) -> cut()
# along its own faces, a box a piece; an open sheet (a vault room's walls, a prefab's) or a closed shell round a room
# (Havok collides with surfaces: a vault hall, a boxcar) -> its regions (faces within 15 degrees of a seed face) each
# a thin slab, a few round its holes (a doorway stays open). Layers: COLLIDE ->
# colliders; RAMP (the stair helper a character walks up a flight on) -> boxes too, counted (the catalog makes such a
# piece walkable); the rest left out (49, Fallout's navmesh cuts, too: never a collider). No "fill -> bounds" here.
SLAB = 0.1                                                   # a sheet region's slab: under a floor (over a ceiling), or
                                                             # centred on a wall; thicker if the region bends more
BEND = np.cos(np.radians(15))                                # faces of one sheet region: within 15 degrees of its seed
HMIN = 0.02                                                  # the thinnest half box


def frame(p):
    """the least-volume box round points: (axes as columns, centre, half extents); flat or thinner: by its spread"""
    try:
        T, ext = trimesh.bounds.oriented_bounds(p)
        A = T[:3, :3]
        return A.T, -A.T @ T[:3, 3], np.asarray(ext) / 2
    except Exception:
        m = p.mean(0)
        A = np.linalg.svd(p - m)[2].T
        if np.linalg.det(A) < 0: A[:, 2] *= -1
        q = (p - m) @ A
        lo, hi = q.min(0), q.max(0)
        return A, m + A @ ((lo + hi) / 2), (hi - lo) / 2


def box_of(p, r=0.0):
    """one box round points p grown by r: axis-aligned when that holds under 10% more than the least box round them,
    else turned - its axes reordered and flipped to lie as near x, y, z as they can (a small turn stays small)"""
    p = np.asarray(p, float)
    lo, hi = p.min(0) - r, p.max(0) + r
    if len(p) > 1:
        A, c, h = frame(p)
        h = np.maximum(h + r, HMIN)
        if np.prod(np.maximum(hi - lo, 2 * HMIN)) > 1.1 * np.prod(2 * h):
            k = max(((pm, sg) for pm in itertools.permutations(range(3)) for sg in itertools.product((1, -1), repeat=3)),
                    key=lambda t: np.trace(A[:, t[0]] * t[1]) if np.linalg.det(A[:, t[0]] * t[1]) > 0 else -9)
            A, h = A[:, k[0]] * k[1], h[list(k[0])]
            w, x, y, z = trimesh.transformations.quaternion_from_matrix(np.r_[np.c_[A, np.zeros(3)], [[0, 0, 0, 1]]])
            q = [x, y, z, w] if w >= 0 else [-x, -y, -z, -w]
            box = [round(float(v), 3) for v in (*c, *h)]
            return box if q[3] > 0.99996 else box + [round(float(v), 4) for v in q]   # (under 1 degree: square)
    return [round(float(v), 3) for v in (*((lo + hi) / 2), *np.maximum((hi - lo) / 2, HMIN))]


def hull_volume(p):
    try: return ConvexHull(p).volume
    except Exception: return 0.0                             # (flat, a line, a point)


def clip(polys, n, d):
    """the polygons' parts on the side n.x <= d (Sutherland-Hodgman; no cap: the cut's edges stay in the polygons)"""
    out = []
    for p in polys:
        s, q = p @ n - d, []
        for i in range(len(p)):
            j = (i + 1) % len(p)
            if s[i] <= 0: q.append(p[i])
            if s[i] * s[j] < 0: q.append(p[i] + (p[j] - p[i]) * (s[i] / (s[i] - s[j])))
        if len(q) >= 3: out.append(np.array(q))
    return out


def cut(polys, A, depth=4):
    """a closed shape (its faces as polygons) that isn't a box -> its pieces (each its faces), a box each: cut by the
    plane - one of its own faces', or one halving it along an axis of A - that most shrinks the two halves' boxes (in
    A's frame), again for each half, while a cut saves over 20% (16 pieces at most). Fallout's parts are boxes and
    wedges glued together and their own face planes part them cleanly (voxels stair-stepped every slope: the patio
    chair 65 boxes, now a handful); halving trims a wedge or a gable end. No cap is made: a cut's edges stay in the
    clipped faces, which is all the next cut and the box need. A frame round an opening defeats it (no one cut gains):
    open_area() tells"""
    P = np.unique(np.round(np.vstack(polys), 5), axis=0)
    vol = lambda q: float(np.prod(np.maximum(np.ptp(q @ A, axis=0), 2 * HMIN)))
    v0 = vol(P)
    if depth and v0 > 1e-3:
        E = np.array([e for p in polys for e in zip(p, np.roll(p, -1, 0))])
        planes = {}
        for p in polys:
            nn = np.cross(p[1] - p[0], p[2] - p[0])
            ln = np.linalg.norm(nn)
            if ln > 1e-9: planes.setdefault(tuple(np.round(np.r_[nn / ln, nn @ p[0] / ln], 3)), (nn / ln, nn @ p[0] / ln))
        Q = P @ A
        for k in range(3): planes[k] = (A[:, k], (Q[:, k].min() + Q[:, k].max()) / 2)
        best = None
        for n, d in planes.values():
            s = P @ n - d
            if not ((s < -1e-4).any() and (s > 1e-4).any()): continue
            se = E @ n - d
            x = se[:, 0] * se[:, 1] < 0
            X = E[x, 0] + (E[x, 1] - E[x, 0]) * (se[x, 0] / (se[x, 0] - se[x, 1]))[:, None]
            v = vol(np.vstack([P[s <= 1e-4], X])) + vol(np.vstack([P[s >= -1e-4], X]))
            if best is None or v < best[0]: best = (v, n, d)
        if best and best[0] < 0.8 * v0:
            return cut(clip(polys, best[1], best[2]), A, depth - 1) + cut(clip(polys, -best[1], -best[2]), A, depth - 1)
    return [polys]


def covered(T, g):
    """which of the points g (n x 2) lie in one of the triangles T (m x 3 x 2)"""
    occ = np.zeros(len(g), bool)
    for a, b, c in T:
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12: continue
        l1 = ((b[1] - c[1]) * (g[:, 0] - c[0]) + (c[0] - b[0]) * (g[:, 1] - c[1])) / d
        l2 = ((c[1] - a[1]) * (g[:, 0] - c[0]) + (a[0] - c[0]) * (g[:, 1] - c[1])) / d
        occ |= (l1 >= -1e-6) & (l2 >= -1e-6) & (l1 + l2 <= 1 + 1e-6)
    return occ


def grid(half, pitch):
    """the middles of a rectangle's cells (its half sides, centred), and how many each way"""
    nx, ny = np.ceil(2 * np.asarray(half) / pitch).astype(int)
    g = np.meshgrid((np.arange(nx) + 0.5) * pitch - half[0], (np.arange(ny) + 0.5) * pitch - half[1], indexing='ij')
    return np.stack(g, -1).reshape(-1, 2), nx, ny


def open_area(polys):
    """how much of the box round a piece (its faces), seen along the box's thinnest side, nothing of it covers, in m2
    (0.1 m cells): a doorway left in a wall's box, a gable's overhang"""
    P = np.vstack(polys)
    A, c, h = frame(P)
    k = int(np.argmin(h))
    i, j = [x for x in range(3) if x != k]
    T = (np.array([(p[0], p[t], p[t + 1]) for p in polys for t in range(1, len(p) - 1)]) - c) @ A[:, [i, j]]
    g, _, _ = grid(h[[i, j]], 0.1)
    return float((~covered(T, g)).sum()) * 0.01


def regions(m):
    """an open sheet's faces in regions: grown from a seed face over neighbours within 15 degrees of it"""
    nb = [[] for _ in range(len(m.faces))]
    for a, b in m.face_adjacency: nb[a].append(b); nb[b].append(a)
    left, out = np.ones(len(m.faces), bool), []
    for seed in np.argsort(-m.area_faces):
        if not left[seed]: continue
        n0, todo, reg = m.face_normals[seed], [seed], []
        left[seed] = False
        while todo:
            f = todo.pop(); reg.append(f)
            for g in nb[f]:
                if left[g] and m.face_normals[g] @ n0 >= BEND: left[g] = False; todo.append(g)
        out.append(reg)
    return out


def hull_area(q):
    try: return ConvexHull(q).volume
    except Exception: return 0.0                             # (a line, a point)


def patches(F, V2, area):
    """a flat region's triangles (their vertex indices F, the vertices in its plane V2, their areas) -> convex patches
    (lists of triangles): grown from the biggest over shared edges while the patch stays about convex (its hull within
    12% of its area: 2% left a vault hall's flattened curves 50% more boxes, 25% closed an arched doorway's top). A
    wall round a doorway: its two jambs and the lintel; a frame of braces: each brace"""
    by, nb = {}, [[] for _ in F]
    for t, f in enumerate(F):
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])): by.setdefault((min(a, b), max(a, b)), []).append(t)
    for ts in by.values():
        for x in ts: nb[x] += [y for y in ts if y != x]
    left, out = np.ones(len(F), bool), []
    for seed in np.argsort(-area):
        if not left[seed]: continue
        left[seed] = False
        patch, pts, a, todo = [seed], set(F[seed]), area[seed], list(nb[seed])
        while todo:
            t = todo.pop()
            if left[t] and hull_area(V2[list(pts | set(F[t]))]) <= 1.12 * (a + area[t]):
                left[t] = False
                patch.append(t); pts |= set(F[t]); a += area[t]; todo += nb[t]
        out.append(patch)
    return out


def slabs(m, faces, span=None):
    """a sheet region (its faces) -> thin slabs: SLAB thick (more if it bends), under a floor (its faces up), over a
    ceiling, centred on anything steeper than 45 degrees (or across span, along its normal: a plate's thickness); one
    slab when it fills 90% of its least rectangle, else one per convex patch of it (a wall round a doorway: jambs and
    lintel, the doorway open), a patch that fills its rectangle under 80% (a gable) its prism cut()"""
    n = (m.face_normals[faces] * m.area_faces[faces, None]).sum(0)
    n /= max(np.linalg.norm(n), 1e-12)
    e1 = np.cross(n, [1.0, 0, 0] if abs(n[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1)
    E = np.c_[e1, np.cross(n, e1)]                           # (axes in its plane)
    F, area = m.faces[faces], m.area_faces[faces]
    h = m.vertices[np.unique(F)] @ n
    a, b = span or (h.min(), h.max())
    t = max(SLAB, b - a)
    lo, hi = (b - t, b) if abs(n[2]) > 0.7 and not span else ((a + b - t) / 2, (a + b + t) / 2)   # (along n)
    w = m.vertices - (m.vertices @ n)[:, None] * n           # (every vertex flattened into the plane through 0)
    V2 = w @ E
    def slab(tris):
        idx = np.unique(F[tris])
        if area[tris].sum() >= 0.8 * np.prod(trimesh.bounds.oriented_bounds_2D(V2[idx])[1]):
            return [box_of(np.vstack([w[idx] + n * lo, w[idx] + n * hi]))]
        e, k = np.unique(np.sort(F[tris][:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1), axis=0, return_counts=True)
        polys = [w[f] + n * lo for f in F[tris]] + [w[f[::-1]] + n * hi for f in F[tris]] + \
                [np.array([w[i] + n * lo, w[j] + n * lo, w[j] + n * hi, w[i] + n * hi]) for i, j in e[k == 1]]   # (its prism)
        A2 = trimesh.bounds.oriented_bounds_2D(V2[idx])[0][:2, :2]
        return [box_of(np.vstack(q)) for q in cut(polys, np.c_[E @ A2.T, n])]
    if area.sum() >= 0.9 * np.prod(trimesh.bounds.oriented_bounds_2D(V2[np.unique(F)])[1]): return slab(np.arange(len(F)))
    return [x for pt in patches(F, V2, area) for x in slab(np.array(pt))]


def convex_boxes(p, r, walk, m=None):
    """a convex part (its points; its mesh, else its hull) -> one box round it; a structure's (walk) big one (over a
    metre) that box would overfill by a third (a roof's wedge: a box's top was 0.65 m over the eaves) -> its faces as
    sheets, a slope a turned slab: Havok collides with its surface, never its inside (a prop's: a statue, a jukebox -
    one box, as Fallout's chair is four)"""
    b, hull = box_of(p, r), hull_volume(p)
    if not walk or max(b[3:6]) < 0.5 or not hull or 8 * np.prod(b[3:6]) <= 1.35 * hull: return [b]
    m = m or trimesh.convex.convex_hull(p)
    return [x for f in regions(m) for x in slabs(m, f)]


def part_boxes(c, r, walk):
    """one connected part of a body (a mesh) -> its boxes. An open one that is small (under 25 cm: a lounge chair's
    leg) or a thin shell with no hole (a booth's curved back: thinner than a slab, the faces looking one way covering
    85% of its box's face - both ways would pass a wall round a doorway) is one box too. A structure's (walk) closed
    part is carved round its openings (a prop's: as cut() leaves it - a statue isn't walked through)"""
    if c.is_watertight:
        hull = hull_volume(c.vertices)
        if abs(c.volume) >= 0.95 * hull: return convex_boxes(c.vertices, r, walk, c)
        pieces = cut(list(c.triangles), frame(c.vertices)[0]) if hull < 1 or abs(c.volume) >= 0.5 * hull else None
        if pieces and (not walk or c.extents.max() < 1 or all(open_area(q) < 0.3 for q in pieces)): return [box_of(np.vstack(q), r) for q in pieces]
        # (else a shell round a room - a vault hall, a boxcar - or a piece whose box would shut an opening - a wall
        # round its doorway, a railing's panel: Havok collides with a mesh's surface, never its inside, so its faces
        # go as sheets - a thin plate's front alone, a slab its thickness each; cut into 16 pieces a hall's were solid
        # boxes filling it, the Watchtower's railings solid panels)
        A, _, h = frame(c.vertices)
        k = int(np.argmin(h))
        front, d = np.nonzero(c.face_normals @ A[:, k] > 0.5)[0], c.vertices @ A[:, k]
        if walk and 2 * h[k] <= 0.3 and len(front): return slabs(c, front, (d.min(), d.max()))
    else:
        A, _, h = frame(c.vertices)
        k = int(np.argmin(h))
        f = (c.face_normals @ A[:, k]) * c.area_faces
        if h.max() < 0.125 or 2 * h[k] <= 1.5 * SLAB and max(f[f > 0].sum(), -f[f < 0].sum()) >= 0.85 * 4 * np.prod(np.delete(h, k)):
            return [box_of(c.vertices, r)]
    return [b for f in regions(c) for b in slabs(c, f)]


def parts(v, f):
    """a body's connected parts: [(their points, their mesh - None for a convex point set)] (welded to the mm:
    compressed mesh sections meet exactly)"""
    if not len(f): return [(v, None)]
    return [(c.vertices, c) for c in trimesh.Trimesh(np.round(v, 3), f).split(only_watertight=False, engine='scipy')]   # (scipy: the frozen importer has no networkx)


def havok_boxes(shapes, walk):
    """Fallout's bodies [(vertices, triangles, layer, radius)] -> dict(boxes, col='havok', ramps), at most
    WALK_CAP boxes for a structure (walk; its smallest left out) or BOX_CAP for a prop (its busiest parts coarsened)"""
    def fit(p, c, r):                                        # (a part that trips the fitting: one box round it, not a
        try: return convex_boxes(p, r, walk) if c is None else part_boxes(c, r, walk)   # failed import)
        except Exception: return [box_of(p, r)]
    per, ramps = [], []
    for v, f, layer, r in shapes:
        if layer in COLLIDE: per += [[p, fit(p, c, r)] for p, c in parts(v, f)]
        elif layer == RAMP: ramps += [b for p, c in parts(v, f) for b in fit(p, c, r)]
    cap = WALK_CAP if walk else BOX_CAP
    boxes = coarsen(per, cap - len(ramps)) if not walk else [b for _, bs in per for b in bs]
    return dict(boxes=biggest(boxes, cap - len(ramps)) + ramps, col='havok', ramps=len(ramps))


def shape_mesh(mesh):
    """Collision boxes ([cx, cy, cz, hx, hy, hz], ...) for a mesh in Cyberpunk's space. A wall-like mesh (one thin
    axis, up to 0.9 m) is voxelized flat along that axis, so a doorway stays open; a hollow one in 3D; a solid one is
    its bounds; up to BOXES_MAX boxes. (A structure's walk-in shapes go to rooms() instead.)"""
    lo, hi = mesh.bounds
    size = hi - lo
    bb = [[round(float((lo[i] + hi[i]) / 2), 3) for i in range(3)] + [round(float(max(size[i], 0.04) / 2), 3) for i in range(3)]]
    if size.max() < 0.4: return []
    wall = is_wall(size)
    thin = int(np.argmin(size)) if wall else None
    if not wall:
        pitch = max(0.12, float(size.max()) / 16)
        vg = trimesh.voxel.creation.voxelize(mesh, pitch).fill()
        fill = float(vg.matrix.sum()) * pitch ** 3 / max(float(np.prod(np.maximum(size, pitch))), 1e-9)
        if fill > 0.55: return bb
    pitch = max(0.1, float(size.max()) / 40) if wall else max(0.12, float(size.max()) / 16)
    best = None
    for _ in range(6):
        b = mesh_boxes(mesh, (lo.tolist(), hi.tolist()), pitch, extrude=thin, minvol=0.0 if wall else 0.005)
        if b and (best is None or len(b) < len(best)): best = b
        if 0 < len(b) <= BOXES_MAX: return [list(x) for x in b]
        pitch *= 1.3
    return [list(x) for x in best[:BOXES_MAX * 2]] if best else bb


if __name__ == '__main__':
    name = sys.argv[1]
    pitch = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
    ext = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '-' else None
    minvol = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    meshes.fetch([name])
    b = boxes(name, pitch, ext, minvol)
    print(len(b), 'boxes; mesh bounds', meshes.info(name)[:2])
    for x in b[:40]: print(x)
