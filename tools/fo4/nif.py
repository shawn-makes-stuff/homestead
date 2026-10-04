"""Fallout 4 .nif meshes (20.2.0.7, BS 130): the geometry, texture sets / materials and workshop connect points of
static pieces. Unknown blocks are skipped by their size. Layout: FO4_RESEARCH.md, section 2 (niftools nif.xml).
  python tools/fo4/nif.py <mesh path in Meshes.ba2>      summary of shapes, materials and connect points
"""
import os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class R:
    def __init__(self, b, o=0): self.b, self.o = b, o
    def u(self, fmt):
        v = struct.unpack_from('<' + fmt, self.b, self.o); self.o += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]
    def sized(self):                                    # u32 length + chars
        n = self.u('I'); s = self.b[self.o:self.o + n].decode('cp1252'); self.o += n; return s
    def export(self):                                   # u8 length (incl. null) + chars
        n = self.u('B'); s = self.b[self.o:self.o + n].rstrip(b'\0').decode('cp1252'); self.o += n; return s


NOT_LOOPS = ('ProjectileNode',)                         # looping controllers that are no part (a mortar's shot)
def skin_pos(sh, w):
    """a skinned shape's vertices where the bones w {name: (matrix, translation)} hold them (Fallout keeps them in
    skin space: each bone's BoneData takes them to the bone, the bone's place to the file's space), weights blended;
    None when a bone is missing"""
    sk = sh.get('skin')
    if not sk or not sh['bones']: return None
    canon = {k.lower(): k for k in w}
    bs = [canon.get((b or '').lower()) for b in sh['bones']]
    if len(sk['xf']) < len(bs) or None in bs: return None
    A = np.stack([w[b][0] @ sk['xf'][i][0] for i, b in enumerate(bs)])
    c = np.stack([w[b][0] @ sk['xf'][i][1] + w[b][1] for i, b in enumerate(bs)])
    ix = np.minimum(sk['ix'], len(bs) - 1)
    wt = sk['w'] / np.maximum(sk['w'].sum(axis=1, keepdims=True), 1e-6)
    v = sh['pos'].astype(np.float64)
    p = np.zeros_like(v)
    for k in range(4):
        p += wt[:, k:k + 1] * (np.einsum('nij,nj->ni', A[ix[:, k]], v) + c[ix[:, k]])
    if sh.get('normal') is not None:                     # its normals the same way (weights blended, made unit again)
        n = np.zeros_like(v)
        for k in range(4): n += wt[:, k:k + 1] * np.einsum('nij,nj->ni', A[ix[:, k]], sh['normal'].astype(np.float64))
        sh['normal'] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    sh['bones'] = bs
    return p


SWITCH = 0                                              # which child of a switch node shapes() takes
def mat_quat(M):                                       # rotation matrix -> quaternion (w, x, y, z), as the file stores it
    w = np.sqrt(max(0.0, 1 + M[0, 0] + M[1, 1] + M[2, 2])) / 2
    x = np.copysign(np.sqrt(max(0.0, 1 + M[0, 0] - M[1, 1] - M[2, 2])) / 2, M[2, 1] - M[1, 2])
    y = np.copysign(np.sqrt(max(0.0, 1 - M[0, 0] + M[1, 1] - M[2, 2])) / 2, M[0, 2] - M[2, 0])
    z = np.copysign(np.sqrt(max(0.0, 1 - M[0, 0] - M[1, 1] + M[2, 2])) / 2, M[1, 0] - M[0, 1])
    return (w, x, y, z)


def quat_mul(a, b):
    aw, ax, ay, az = a; bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


NODES = ('NiNode', 'BSFadeNode', 'BSLeafAnimNode', 'BSMultiBoundNode', 'NiSwitchNode', 'BSOrderedNode', 'NiBillboardNode')


class Nif:
    def __init__(self, b):
        r = R(b)
        end = b.index(b'\n')
        self.header = b[:end].decode()
        r.o = end + 1
        self.version, _endian, self.user, n = r.u('IBII')
        self.bs = r.u('I')
        r.export()                                      # author
        if self.bs > 130: r.u('I')
        if self.bs < 131: r.export()                    # process script
        self.export_script = r.export()
        if self.bs >= 103: r.export()                   # max path
        types = [r.sized() for _ in range(r.u('H'))]
        idx = [r.u('H') for _ in range(n)]
        sizes = [r.u('I') for _ in range(n)]
        nstr, _mx = r.u('II')
        self.strings = [r.sized() for _ in range(nstr)]
        for _ in range(r.u('I')): r.u('I')
        self.blocks, o = [], r.o
        for i in range(n):
            self.blocks.append((types[idx[i]], o, sizes[i]))
            o += sizes[i]
        self.b = b

    def s(self, i): return self.strings[i] if 0 <= i < len(self.strings) else None

    def av(self, r):                                    # NiObjectNET + NiAVObject (BS >= 130: no properties)
        name = self.s(r.u('i'))
        extra = [r.u('i') for _ in range(r.u('I'))]
        r.u('i')                                        # controller
        flags = r.u('I')
        t = np.array(r.u('3f')); rot = np.array(r.u('9f')).reshape(3, 3); scale = r.u('f')
        r.u('i')                                        # collision
        return name, extra, t, rot, scale

    def node(self, i):
        typ, o, _ = self.blocks[i]
        r = R(self.b, o)
        name, extra, t, rot, scale = self.av(r)
        kids = [r.u('i') for _ in range(r.u('I'))] if typ in NODES else []
        return name, extra, t, rot, scale, kids

    def trishape(self, i):
        typ, o, _ = self.blocks[i]
        r = R(self.b, o)
        name, extra, t, rot, scale = self.av(r)
        r.u('4f')                                       # bounding sphere
        _skin, shader, alpha = r.u('iii')
        desc = r.u('Q'); ntri = r.u('I'); nv = r.u('H'); size = r.u('I')
        if not size: return None
        stride, flags = (desc & 0xF) * 4, desc >> 44
        full = bool(flags & 0x400)
        raw = np.frombuffer(self.b, np.uint8, nv * stride, r.o).reshape(nv, stride)
        pos = raw[:, :12].copy().view('<f4') if full else raw[:, :6].copy().view('<f2').astype(np.float32)
        uvo = ((desc >> 8) & 0xF) * 4
        uv = raw[:, uvo:uvo + 4].copy().view('<f2').astype(np.float32) if flags & 2 else None
        no = ((desc >> 16) & 0xF) * 4
        nrm = raw[:, no:no + 3].astype(np.float32) / 255 * 2 - 1 if flags & 8 else None
        tri = np.frombuffer(self.b, '<u2', ntri * 3, r.o + nv * stride).reshape(ntri, 3)
        bones, vbone, skin = None, None, None
        if flags & 0x40 and 0 <= _skin < len(self.blocks) and self.blocks[_skin][0] == 'BSSkin::Instance':
            so = ((desc >> 28) & 0xF) * 4                    # skinning: 4 half weights, 4 byte bone indices a vertex
            w = raw[:, so:so + 8].copy().view('<f2').astype(np.float32)
            ix = raw[:, so + 8:so + 12].astype(np.int64)
            vbone = ix[np.arange(nv), np.argmax(w, axis=1)].astype(np.int32)   # the bone with the most weight
            sr = R(self.b, self.blocks[_skin][1])
            _root, bd = sr.u('ii')                       # skeleton root, bone data
            refs = [sr.u('i') for _ in range(sr.u('I'))]
            bones = [self.node(k)[0] if 0 <= k < len(self.blocks) and self.blocks[k][0] in NODES else None for k in refs]
            if 0 <= bd < len(self.blocks) and self.blocks[bd][0] == 'BSSkin::BoneData':
                br = R(self.b, self.blocks[bd][1])       # per bone: bounds, then skin space -> bone space
                xf = []
                for _ in range(br.u('I')):
                    br.u('4f'); rot = np.array(br.u('9f')).reshape(3, 3); t = np.array(br.u('3f')); sc = br.u('f')
                    xf.append((rot * sc, t))
                skin = dict(w=w, ix=ix, xf=xf)
        return dict(name=name, t=t, rot=rot, scale=scale, pos=pos, uv=uv, normal=nrm, tri=tri, shader=shader, alpha=alpha, lod=typ,
                    bones=bones, vbone=vbone, skin=skin)

    def alpha(self, i):
        """NiAlphaProperty: (blends, tests, threshold 0-255), or None"""
        if not (0 <= i < len(self.blocks)) or self.blocks[i][0] != 'NiAlphaProperty': return None
        r = R(self.b, self.blocks[i][1])
        r.u('i'); [r.u('i') for _ in range(r.u('I'))]; r.u('i')     # name, extra data, controller
        f, thr = r.u('H'), r.u('B')
        return bool(f & 1), bool(f & 0x200), thr

    def shader(self, i):
        """BSLightingShaderProperty: its material (.bgsm) path and texture set"""
        typ, o, _ = self.blocks[i]
        r = R(self.b, o)
        if typ == 'BSEffectShaderProperty':               # glow tubes, halos: their .bgem is the name (no shader type
            name = self.s(r.u('i'))                        # field); without one, its settings are here: its texture
            for _ in range(r.u('I')): r.u('i')             # and how it glows
            r.u('i'); f1, f2 = r.u('II'); r.u('4f')
            src = r.sized(); r.u('4B'); r.u('4f')
            ec, em = r.u('4f'), r.u('f')
            return {'type': typ, 'material': name, 'textures': [src] if src else [], 'emit': (ec[0], ec[1], ec[2]),
                    'emit_mult': em, 'effect': True}
        if typ != 'BSLightingShaderProperty': return {'type': typ}
        r.u('I'); name = self.s(r.u('i'))
        for _ in range(r.u('I')): r.u('i')
        r.u('i'); f1, f2 = r.u('II'); r.u('4f')
        ts = r.u('i')
        ec, em = r.u('3f'), r.u('f')                       # (Own_Emit, flags 1 bit 22: it glows in that colour; Glow_Map,
        tex = []                                           # flags 2 bit 6: through its glow map, texture slot 4)
        if 0 <= ts < len(self.blocks) and self.blocks[ts][0] == 'BSShaderTextureSet':
            rr = R(self.b, self.blocks[ts][1])
            tex = [rr.sized() for _ in range(rr.u('I'))]
        own = bool(f1 >> 22 & 1)
        return {'type': typ, 'material': name, 'textures': tex, 'emit': ec if own else None, 'emit_mult': em,
                'glow_map': (tex[4] if bool(f2 >> 6 & 1) and len(tex) > 4 and tex[4] else None)}

    def connect_points(self):
        """workshop snap points in the file's space: each is stored in its parent node's space (a door's or a conveyor's
        WorkshopConnectPoints node can be moved and turned), so it is carried through that node"""
        out, nodes = [], {}
        for typ, o, _ in self.blocks:
            if typ != 'BSConnectPoint::Parents': continue
            r = R(self.b, o)
            r.u('i')
            for _ in range(r.u('I')):
                parent, name = r.sized(), r.sized()
                q = r.u('4f'); t = r.u('3f'); sc = r.u('f')
                if parent not in nodes: nodes[parent] = self.node_transform(parent) if parent else None
                nt = nodes[parent]
                if nt is not None:
                    M, T = nt
                    s = np.cbrt(abs(np.linalg.det(M))) or 1.0
                    t = tuple(M @ np.array(t) + T)
                    q = quat_mul(mat_quat(M / s), q)
                out.append(dict(parent=parent, name=name, rot=tuple(float(v) for v in q), pos=tuple(float(v) for v in t), scale=sc))
        return out

    def node_transform(self, want):
        """a named node's (rotation-scale matrix, position) in the file's space, or None: a lamp's AttachLight, a
        rack's slot for a bobblehead"""
        found = []
        def walk(i, M, T):
            typ = self.blocks[i][0]
            if typ in NODES:
                name, extra, t, rot, scale, kids = self.node(i)
                M2, T2 = M @ (rot * scale), M @ t + T
                if (name or '').lower() == want.lower(): found.append((M2, T2))
                for k in kids:
                    if k >= 0: walk(k, M2, T2)
        walk(0, np.eye(3), np.zeros(3))
        return found[0] if found else None

    def addons(self):
        """Fallout's add-on nodes (BSValueNode "AddOnNode<n>"): (the ADDN record's index n, position in the file's
        space, rotation-scale matrix) - where the game attaches a light, a fire or smoke effect"""
        out = []
        def walk(i, M, T):
            typ, o, _ = self.blocks[i]
            if typ in NODES or typ == 'BSValueNode':
                r = R(self.b, o)
                name, extra, t, rot, scale = self.av(r)
                kids = [r.u('i') for _ in range(r.u('I'))]
                M2, T2 = M @ (rot * scale), M @ t + T
                if typ == 'BSValueNode': out.append((r.u('i'), T2, M2))   # (index, where, its turn: a spotlight's aim)
                if typ == 'NiSwitchNode': kids = kids[SWITCH:SWITCH + 1]
                for k in kids:
                    if k >= 0: walk(k, M2, T2)
        walk(0, np.eye(3), np.zeros(3))
        return out

    # --- animation: NiControllerSequence (a named state or transition: Open, Close, On, TripTransition...) ---------
    def _keygroup(self, r, width):
        """KeyGroup<float or Vector3>: [(time, value)], the interpolation type (1 linear, 2 quadratic, 3 TBC, 5 const)"""
        n = r.u('I')
        if not n: return [], 0
        kt = r.u('I')
        out = []
        for _ in range(n):
            t = r.u('f')
            v = r.u('%df' % width) if width > 1 else (r.u('f'),)
            if kt == 2: r.u('%df' % (2 * width))        # forward / backward tangents (played as linear)
            elif kt == 3: r.u('3f')                      # tension, bias, continuity
            out.append((t, v if width > 1 else v[0]))
        return out, kt

    def _transform_data(self, i):
        """NiTransformData: rotation keys (quaternions w,x,y,z; or XYZ euler groups), translations, scales"""
        typ, o, _ = self.blocks[i]
        r = R(self.b, o)
        rot, euler = [], None
        n = r.u('I')
        if n:
            kt = r.u('I')
            if kt != 4:
                for _ in range(n):
                    t = r.u('f'); q = r.u('4f')
                    if kt == 3: r.u('3f')
                    rot.append((t, q))
            else:                                        # XYZ rotation: three float groups (radians)
                euler = [self._keygroup(r, 1)[0] for _ in range(3)]
        trans = self._keygroup(r, 3)[0]
        scale = self._keygroup(r, 1)[0]
        return dict(rot=rot, euler=euler, trans=trans, scale=scale)

    def sequences(self):
        """{name: {cycle (0 loop, 1 reverse, 2 clamp), start, stop, tracks: {node: {pose: (t, q, s) or None, rot,
        euler, trans, scale}}, vis: {node: [(time, shown)]}}} - Fallout's own keys, as stored"""
        out = {}
        for typ, o, _ in self.blocks:
            if typ != 'NiControllerSequence': continue
            r = R(self.b, o)
            name = self.s(r.u('i'))
            nb = r.u('I'); r.u('I')                      # controlled blocks, array grow by
            blocks = []
            for _ in range(nb):
                interp, _ctrl = r.u('ii')
                r.u('B')                                 # priority
                node, prop, ctype, cid, iid = (self.s(r.u('i')) for _ in range(5))
                blocks.append((interp, node, ctype))
            _w, _text = r.u('f'), r.u('i')
            cycle, _freq, start, stop = r.u('I'), r.u('f'), r.u('f'), r.u('f')
            seq = dict(cycle=cycle, start=start, stop=stop, tracks={}, vis={}, sounds=[])
            if 0 <= _text < len(self.blocks) and self.blocks[_text][0] == 'NiTextKeyExtraData':   # its cues: sounds
                tr = R(self.b, self.blocks[_text][1]); tr.u('i')                                # started, stopped
                for _ in range(tr.u('I')):
                    tk, v = tr.u('f'), self.s(tr.u('i')) or ''
                    if v.startswith(('SoundPlay.', 'SoundStop.')): seq['sounds'].append((max(0.0, tk - start), v[5:9] == 'Play', v[10:]))
            for interp, node, ctype in blocks:
                if interp < 0 or interp >= len(self.blocks) or not node: continue
                it, io, _ = self.blocks[interp]
                ir = R(self.b, io)
                if it == 'NiTransformInterpolator':
                    t = ir.u('3f'); q = ir.u('4f'); s = ir.u('f'); data = ir.u('i')
                    pose = None if abs(t[0]) > 1e30 or abs(q[0]) > 1e30 else (t, q, s)   # (FLT_MAX: not set)
                    tr = dict(pose=pose, rot=[], euler=None, trans=[], scale=[])
                    if 0 <= data < len(self.blocks) and self.blocks[data][0] in ('NiTransformData', 'NiKeyframeData'):
                        tr.update(self._transform_data(data))
                    seq['tracks'][node] = tr
                elif it == 'NiBoolInterpolator' and ctype == 'NiVisController':
                    val = ir.u('B'); data = ir.u('i')
                    keys = [(start, bool(val))]
                    if 0 <= data < len(self.blocks) and self.blocks[data][0] == 'NiBoolData':
                        dr = R(self.b, self.blocks[data][1])
                        n = dr.u('I')
                        if n:
                            kt = dr.u('I'); keys = []
                            for _ in range(n):
                                tk = dr.u('f'); v = dr.u('B')
                                if kt == 3: dr.u('3f')
                                keys.append((tk, bool(v)))
                    seq['vis'][node] = keys
            out[name] = seq
        # a node's own keyframe controller, no sequence: it just runs (a windmill's propeller) - as a looping 'Idle'
        import anim                                      # (and a Havok-driven spinner, from anim.SPIN's recipe)
        idle = dict(cycle=0, start=1e9, stop=-1e9, tracks={}, vis={}, sounds=[])
        line = dict(start=1e9, stop=-1e9, tracks={})         # clamped ones: one timeline
        taken = {n for s in out.values() for n in s['tracks']}
        for bi, (typ, o, _) in enumerate(self.blocks):
            if typ not in NODES: continue
            r = R(self.b, o)
            name = self.s(r.u('i')); [r.u('i') for _ in range(r.u('I'))]; c = r.u('i')
            if name in taken or name in NOT_LOOPS: continue
            if (name or '').lower() in anim.SPIN and not (0 <= c < len(self.blocks) and self.blocks[c][0] == 'NiTransformController'):
                idle['tracks'][name] = anim.spin(anim.matq(self.node(bi)[3]), *anim.SPIN[name.lower()])
                idle['start'], idle['stop'] = min(idle['start'], 0.0), max(idle['stop'], idle['tracks'][name]['rot'][-1][0])
                continue
            if not (0 <= c < len(self.blocks)) or self.blocks[c][0] != 'NiTransformController': continue
            cr = R(self.b, self.blocks[c][1])
            cr.u('i'); flags = cr.u('H'); _f, _p, start, stop = cr.u('4f'); cr.u('i'); interp = cr.u('i')
            if not (0 <= interp < len(self.blocks)) or self.blocks[interp][0] != 'NiTransformInterpolator': continue
            ir = R(self.b, self.blocks[interp][1])
            ir.u('3f'); ir.u('4f'); ir.u('f'); data = ir.u('i')
            if not (0 <= data < len(self.blocks)) or self.blocks[data][0] not in ('NiTransformData', 'NiKeyframeData'): continue
            tr = dict(pose=None, rot=[], euler=None, trans=[], scale=[])
            tr.update(self._transform_data(data))
            to = line if (flags >> 1) & 3 else idle
            to['tracks'][name] = tr
            to['start'], to['stop'] = min(to['start'], start), max(to['stop'], stop)
        if idle['tracks'] and 'Idle' not in out: out['Idle'] = idle
        # a clamped timeline Havok's behaviour graph plays: on a door or gate (a rolling garage door, a powered gate)
        # it is closed -> open -> closed, so it splits where it's furthest open into Open and Close
        if line['tracks'] and not out and any(w in n.lower() for n in line['tracks'] for w in ('door', 'gate')):
            import anim
            loc = self.node_locals()
            def away(t):                                 # how far the moving nodes are from where they start
                d = 0.0
                for n, tr in line['tracks'].items():
                    if n not in loc: continue
                    a, b = anim.local_at(tr, loc[n], line['start']), anim.local_at(tr, loc[n], t)
                    d += sum((x - y) ** 2 for x, y in zip(a[0], b[0])) + 100 * (1 - abs(sum(x * y for x, y in zip(a[1], b[1])))) ** 2
                return d
            ts = [line['start'] + (line['stop'] - line['start']) * i / 200 for i in range(201)]
            ds = [away(t) for t in ts]
            top = max(ds)
            if top > 1e-6:
                far = [t for t, d in zip(ts, ds) if d >= 0.99 * top]
                out['Open'] = dict(cycle=2, start=line['start'], stop=far[0], tracks=line['tracks'], vis={}, sounds=[])
                out['Close'] = dict(cycle=2, start=far[-1], stop=line['stop'], tracks=line['tracks'], vis={}, sounds=[])
        return out

    def _local(self, name, t, rot, scale, pose):
        """a node's local rotation-scale matrix and translation, or its pose's (anim.py: translation, quaternion
        w,x,y,z, scale) when it has one"""
        if pose and name in pose:
            pt, pq, ps = pose[name]
            w, x, y, z = pq
            R3 = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                           [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                           [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
            return R3 * ps, np.array(pt, float)
        return rot * scale, t

    def shapes(self, pose=None, movers=None):
        """every drawable shape with its vertices in the file's space (the node chain applied); editor markers
        skipped. pose: {node: (t, q, s)} replacing those nodes' own transforms (an animation's rest state). movers:
        node names that animate - each shape gets `part` (its nearest moving node, None if static) and `part_at`
        (that node's (matrix, translation) in the file's space)"""
        out, bind, up = [], {}, {}
        def mover(b):                                    # the bone, or its nearest moving parent (a turret's gun: its head)
            if not up: up.update(self.parents())
            while b and b not in movers: b = up.get(b)
            return b
        def worlds():
            if not bind: bind.update(self.node_worlds(pose))
            return bind
        def skinned(sh):                                 # (skin_pos, with this pose's bones)
            p = skin_pos(sh, worlds())
            if p is None: return False
            sh['pos'] = p
            return True
        def split(sh):
            """a shape skinned to moving bones -> one piece per bone (each triangle with its first vertex's bone with the
            most weight): rigid parts that move with their bone; the bone's (posed) place is the part's frame"""
            worlds()
            tb = sh['vbone'][sh['tri'][:, 0]]
            pieces = []
            for bi in np.unique(tb):
                bn = sh['bones'][bi] if bi < len(sh['bones']) else None
                tris = sh['tri'][tb == bi]
                used = np.unique(tris)
                remap = np.full(len(sh['pos']), -1, np.int64); remap[used] = np.arange(len(used))
                sub = dict(sh, pos=sh['pos'][used], uv=sh['uv'][used] if sh['uv'] is not None else None,
                           normal=sh['normal'][used] if sh['normal'] is not None else None, tri=remap[tris].astype(np.uint16))
                mv = mover(bn)
                moving = mv is not None and mv in bind
                sub['part'], sub['part_at'] = (mv, bind[mv]) if moving else (sh['part'], sh['part_at'])
                pieces.append(sub)
            return pieces
        def walk(i, M, T, part):
            typ = self.blocks[i][0]
            if typ in ('BSTriShape', 'BSMeshLODTriShape', 'BSSubIndexTriShape'):
                sh = self.trishape(i)
                if sh and not (sh['name'] or '').lower().startswith('editormarker'):
                    if not skinned(sh):
                        Rm = M @ sh['rot']
                        sh['pos'] = (sh['pos'] * sh['scale']) @ Rm.T + (M @ sh['t'] + T)
                        if sh['normal'] is not None:          # (normals turn with it: lit wrong, a rotated door leaf
                            nn = sh['normal'] @ Rm.T          # flickered as V moved)
                            sh['normal'] = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
                    sh['shader'] = self.shader(sh['shader']) if sh['shader'] >= 0 else {}
                    sh['alpha'] = self.alpha(sh['alpha'])
                    sh['part'], sh['part_at'] = part if part else (None, None)
                    if movers and sh.get('bones') and any(mover(b) for b in sh['bones']): out.extend(split(sh))
                    else: out.append(sh)
            elif typ in NODES:
                name, extra, t, rot, scale, kids = self.node(i)
                L, t2 = self._local(name, t, rot, scale, pose)
                M2, T2 = M @ L, M @ t2 + T
                if movers and name in movers: part = (name, (M2, T2))
                if typ == 'NiSwitchNode': kids = kids[SWITCH:SWITCH + 1]   # one state (a crop: full, or harvested)
                for k in kids:
                    if k >= 0: walk(k, M2, T2, part)
        walk(0, np.eye(3), np.zeros(3), None)
        return out

    skel = None

    skel_first = False

    def attach(self, skel):
        """another file's nodes as this one's (an actor's skeleton: the bones its skinned model hangs on). Where both
        have a bone, the one that agrees with the skin wins: at bind, bone x skin-to-bone is the same for every bone
        (a workshop turret's own bones are right, a standing turret's are the skeleton's)"""
        self.skel = skel
        moved = []
        for first in (False, True):                      # (at bind, skinning leaves the vertices where they're stored)
            self.skel_first, d = first, 0.0
            w = self.node_worlds()
            for i, (typ, o, _) in enumerate(self.blocks):
                if typ not in ('BSTriShape', 'BSMeshLODTriShape', 'BSSubIndexTriShape'): continue
                sh = self.trishape(i)
                p = sh and skin_pos(sh, w)
                if p is not None: d += float(np.abs(p - sh['pos']).mean())
            moved.append(d)
        self.skel_first = moved[1] < moved[0]

    def parents(self):
        """every named node's parent's name. With a skeleton attached its hierarchy rules: a model's own copy of a bone
        sits loose under the model's root (a turret's "gun"), the skeleton has it under the head that turns ("Gun")"""
        out = {}
        def walk(i, up):
            if self.blocks[i][0] not in NODES: return
            name, extra, t, rot, scale, kids = self.node(i)
            if name and name not in out: out[name] = up
            for k in kids:
                if k >= 0: walk(k, name)
        walk(0, None)
        if self.skel:
            sp = self.skel.parents()
            canon = {k.lower(): k for k in sp}
            for k in list(out):
                if k.lower() in canon: out[k] = sp[canon[k.lower()]]
            for k, v in sp.items(): out.setdefault(k, v)
        return out

    def node_worlds(self, pose=None):
        """every named node's (matrix, translation) in the file's space, with pose overrides as in shapes()"""
        out = {}
        def walk(i, M, T):
            typ = self.blocks[i][0]
            if typ in NODES:
                name, extra, t, rot, scale, kids = self.node(i)
                L, t2 = self._local(name, t, rot, scale, pose)
                M2, T2 = M @ L, M @ t2 + T
                if name and name not in out: out[name] = (M2, T2)
                if typ == 'NiSwitchNode': kids = kids[SWITCH:SWITCH + 1]
                for k in kids:
                    if k >= 0: walk(k, M2, T2)
        walk(0, np.eye(3), np.zeros(3))
        if self.skel:                                    # the skeleton's bones: over this file's copies, or besides them
            sk = self.skel.node_worlds(pose)
            if self.skel_first: out = {k: v for k, v in out.items() if k.lower() not in {x.lower() for x in sk}}
            have = {k.lower() for k in out}
            for k, v in sk.items():
                if k.lower() not in have: out[k] = v
        return out

    def node_locals(self):
        """every named node's own local (translation, quaternion w,x,y,z, scale); with a skeleton attached, its bones
        by the same rule as node_worlds (a sweep's rest turn must be the bone the worlds walk)"""
        import anim
        out = {}
        for i, (typ, o, _) in enumerate(self.blocks):
            if typ in NODES:
                name, extra, t, rot, scale, kids = self.node(i)
                if name and name not in out: out[name] = (tuple(float(v) for v in t), anim.matq(rot), float(scale))
        if self.skel:
            sk = self.skel.node_locals()
            if self.skel_first: out = {k: v for k, v in out.items() if k.lower() not in {x.lower() for x in sk}}
            have = {k.lower() for k in out}
            for k, v in sk.items():
                if k.lower() not in have: out[k] = v
        return out


if __name__ == '__main__':
    import ba2
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import paths
    a = ba2.Archive(os.path.join(paths.get('fo4'), 'Fallout4 - Meshes.ba2'))
    n = Nif(a.read(sys.argv[1]))
    print(n.header, 'user', n.user, 'bs', n.bs, n.export_script, '|', len(n.blocks), 'blocks:', sorted({b[0] for b in n.blocks}))
    for sh in n.shapes():
        p = sh['pos']
        print('shape %-24s %5d verts %5d tris  x %.0f..%.0f y %.0f..%.0f z %.0f..%.0f  %s %s' % (sh['name'], len(p), len(sh['tri']), p[:, 0].min(), p[:, 0].max(),
              p[:, 1].min(), p[:, 1].max(), p[:, 2].min(), p[:, 2].max(), sh['shader'].get('material'), (sh['shader'].get('textures') or [''])[:2]))
    for c in n.connect_points(): print('connect %-22s at %s' % (c['name'], tuple(round(v, 1) for v in c['pos'])))
