"""Fallout 4's own collision: the Havok bodies inside a .nif (bhkNPCollisionObject -> bhkPhysicsSystem, an hk_2014.1.0
packfile, 64-bit little-endian, no type reflection: the layouts below were read off the files by hand -
docs/havok_collision_research_2026-10-03.md 1). Each body is one shape on one collision layer, placed by the NIF node
its collision object targets (in metres: one Havok unit is one metre, 1/0.0142875 Fallout units). Never the position
stored in the body: the Watchtower's deck would land 11-23 m up.
Shapes, as Fallout made them: convex polytopes (most are 8-corner boxes), compressed meshes (triangles, quads split),
compounds of convex pieces, spheres and capsules (a core point or segment and a radius). Out: per body piece a point
set (convex: its corners, f empty) or a triangle mesh, its convex radius, its layer and its node.
  python tools/fo4/havok.py <model path in the archives>      what a model's collision holds
"""
import os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nif

UNIT = 0.0142875                                            # metres per Fallout unit (convert.py's)
# (the layers - what each body collides with - are the collision stage's to judge: colliders.py LAYERS)


class Pack:
    """a packfile's __data__ section: its pointer fixups (local, global) and its objects' class names"""
    def __init__(self, b):
        self.b = b
        m0, m1, _tag, ver = struct.unpack_from('<IIii', b, 0)
        if (m0, m1) != (0x57E0E057, 0x10C0C010): raise ValueError('not a Havok packfile')
        ns, = struct.unpack_from('<i', b, 0x14)
        pad, = struct.unpack_from('<h', b, 0x3E)
        o, sec = 0x40 + max(pad, 0), []
        for _ in range(ns):
            sec.append((b[o:o + 20].split(b'\0')[0].decode(),) + struct.unpack_from('<7I', b, o + 20))
            o += 0x40 if ver >= 11 else 0x30
        d = next(s for s in sec if s[0] == '__data__')
        self.base, lf, gf, vf, ex = d[1], d[2], d[3], d[4], d[5]
        self.fix = {}
        for k in range(lf, gf - 7, 8):                      # local: (from, to) in this section
            a, c = struct.unpack_from('<II', b, self.base + k)
            if a != 0xFFFFFFFF: self.fix[a] = c
        for k in range(gf, vf - 11, 12):                    # global: (from, section, to)
            a, _s, c = struct.unpack_from('<III', b, self.base + k)
            if a != 0xFFFFFFFF: self.fix.setdefault(a, c)
        self.cls = {}
        for k in range(vf, ex - 11, 12):                    # virtual: an object's offset -> its class name
            a, s, c = struct.unpack_from('<III', b, self.base + k)
            if a != 0xFFFFFFFF: self.cls[a] = b[sec[s][1] + c:].split(b'\0')[0].decode()
    def ptr(self, off): return self.fix.get(off)
    def u(self, fmt, off): return struct.unpack_from('<' + fmt, self.b, self.base + off)
    def arr(self, off):                                     # hkArray: (where its items are, how many)
        return self.ptr(off), self.u('i', off + 8)[0]
    def vec(self, dtype, n, off): return np.frombuffer(self.b, dtype, n, self.base + off) if n else np.zeros(0, dtype)


def convex(p, o):
    """hknpConvexShape and kin: its corners (a relative array of float4 at +48: u16 count, u16 offset) and radius (+20)"""
    n, off = p.u('HH', o + 48)
    return p.vec('<f4', n * 4, o + 48 + off).reshape(-1, 4)[:, :3].astype(np.float64), float(p.u('f', o + 20)[0])


def compressed(p, o):
    """hknpCompressedMeshShape -> (vertices, triangles). Its data (+96): a tree whose sections each hold packed vertices
    (u32: 11/11/10 bits over the section's offset and scale) and indices into the shared ones (u64: 21/21/22 bits over
    the domain); a primitive is four indices, a quad unless the last two match"""
    t = p.ptr(o + 96) + 16
    dom = np.array(p.u('8f', t + 16)).reshape(2, 4)[:, :3]
    (so, ns), (po, npr), (io, ni), (vo, nv), (ho, nh) = (p.arr(t + k) for k in (64, 80, 96, 112, 128))
    prim = p.vec(np.uint8, npr * 4, po).reshape(-1, 4).astype(np.int64)
    sidx = p.vec('<u2', ni, io).astype(np.int64)
    pv = p.vec('<u4', nv, vo).astype(np.int64)
    sv = p.vec('<u8', nh, ho)
    q = np.c_[sv & 0x1FFFFF, (sv >> np.uint64(21)) & np.uint64(0x1FFFFF), sv >> np.uint64(42)].astype(np.float64)
    shared = dom[0] + q * (dom[1] - dom[0]) / np.array([0x1FFFFF, 0x1FFFFF, 0x3FFFFF])
    V, F, base = [], [], 0
    for s in range(ns):
        sec = so + s * 96
        cp = np.array(p.u('6f', sec + 48))
        first, sh, prims = p.u('3I', sec + 72)
        npk, nsh = p.u('BB', sec + 88)
        pk = pv[first:first + npk]
        si = sidx[(sh >> 8):(sh >> 8) + nsh]
        ok = np.r_[np.ones(len(pk), bool), si < len(shared)]   # (an index past the shared vertices: its triangles go)
        v = np.vstack([cp[:3] + cp[3:] * np.c_[pk & 0x7FF, (pk >> 11) & 0x7FF, (pk >> 22) & 0x3FF], shared[np.minimum(si, len(shared) - 1)]])
        pr = prim[(prims >> 8):(prims >> 8) + (prims & 0xFF)]
        pr = pr[(pr[:, 1] != pr[:, 2]) | (pr[:, 2] != pr[:, 3])]   # (a, b, b, b: a custom primitive, not decoded)
        quad = pr[:, 2] != pr[:, 3]
        f = np.vstack([pr[:, :3], pr[quad][:, [0, 2, 3]]])
        f = f[(f < len(v)).all(1)]
        f = f[ok[f].all(1)]
        V.append(v); F.append(f + base); base += len(v)
    F = np.vstack(F) if F else np.zeros((0, 3), np.int64)
    if npr and not len(F): raise ValueError('compressed mesh of custom primitives only')   # (3 static collections:
    return (np.vstack(V) if V else np.zeros((0, 3))), F                                   # the render mesh instead)


def shape(p, o, M=np.eye(3), T=np.zeros(3)):
    """a shape -> [(vertices, triangles - none for a convex point set, radius, class)] in its body's frame"""
    c = p.cls.get(o, '')
    if c == 'hknpCompressedMeshShape':
        v, f = compressed(p, o)
        return [(v @ M.T + T, f, 0.0, c)] if len(f) else []
    if c in ('hknpDynamicCompoundShape', 'hknpStaticCompoundShape'):
        out, (io, n) = [], p.arr(o + 96)
        for i in range(n):                                  # instances, 128 B: a transform (3 axes, then the position, as
            e = io + i * 128                                # float4 columns), its scale (+64), its shape (+80)
            sub = p.ptr(e + 80)
            if sub is None: continue
            A = np.array(p.u('16f', e)).reshape(4, 4)[:, :3]
            S = np.array(p.u('3f', e + 64))
            out += shape(p, sub, M @ A[:3].T @ np.diag(S), M @ A[3] + T)
        return out
    if c.startswith('hknp') and ('Convex' in c or c in ('hknpSphereShape', 'hknpCapsuleShape')):
        v, r = convex(p, o)
        return [(v @ M.T + T, np.zeros((0, 3), np.int64), r, c)] if len(v) else []
    raise ValueError('unknown Havok shape ' + c)


def worlds(n, pose=None):
    """every node block's (matrix, translation) in the file's space, by block index (names repeat), with a pose's
    nodes as nif.shapes() takes them (an animated model at rest)"""
    out = {}
    def walk(i, M, T):
        typ = n.blocks[i][0]
        if typ not in nif.NODES: return
        name, _x, t, rot, scale, kids = n.node(i)
        L, t2 = n._local(name, t, rot, scale, pose)
        out[i] = (M @ L, M @ t2 + T)
        if typ == 'NiSwitchNode': kids = kids[nif.SWITCH:nif.SWITCH + 1]   # (the state the render takes)
        for k in kids:
            if k >= 0: walk(k, *out[i])
    walk(0, np.eye(3), np.zeros(3))
    return out


def bodies(n, pose=None):
    """a model's collision: [dict(node, layer, v, f, r, cls)] - per body piece its vertices in metres in the model's space
    (the piece space: Fallout's axes x UNIT), its triangles (none: a convex point set), its convex radius; [] when the
    model has none. Raises ValueError when a body can't be read (the caller falls back to the render mesh)"""
    w, packs, out = worlds(n, pose), {}, []
    for typ, o, _ in n.blocks:
        if typ != 'bhkNPCollisionObject': continue
        target, _flags, data, body = struct.unpack_from('<iHiI', n.b, o)
        if target not in w or not (0 <= data < len(n.blocks)) or n.blocks[data][0] != 'bhkPhysicsSystem': continue
        if data not in packs:
            do = n.blocks[data][1]
            packs[data] = Pack(n.b[do + 4:do + 4 + struct.unpack_from('<I', n.b, do)[0]])
        p = packs[data]
        bo, nb = p.arr(64)                                  # hknpPhysicsSystemData: body infos at +64, 96 B each
        if body >= nb: raise ValueError('body %d of %d' % (body, nb))
        b = bo + body * 96
        so = p.ptr(b)
        if so is None: continue
        layer = p.u('I', b + 20)[0] & 0x7F                  # (its collision filter info)
        M, T = w[target]
        for v, f, r, c in shape(p, so):
            out.append(dict(node=n.node(target)[0], layer=layer, v=v @ M.T + T * UNIT, f=f, r=r, cls=c))
    return out


if __name__ == '__main__':
    from convert import Files
    for d in bodies(nif.Nif(Files().read(sys.argv[1]))):
        v = d['v']
        print('layer %2d %-24s %5d verts %5d tris r %.3f  %s..%s' % (d['layer'], d['node'], len(v), len(d['f']), d['r'],
              np.round(v.min(0), 2), np.round(v.max(0), 2)))
