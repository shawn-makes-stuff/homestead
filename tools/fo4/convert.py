"""Fallout 4 workshop pieces -> Cyberpunk: step 1, the raw files, from the player's own Fallout 4 (nothing here is
shipped). Every object the workshop menu can build (tools/fo4/esm.py: recipes under WorkshopMenuMain, sets unfolded):
per model one .glb (a submesh per material, metres, Cyberpunk's axes, back faces for two-sided materials) and its
materials' textures (colour, normal, roughness; the HD pack's when installed; xbm.py writes them), with its size, ground contact,
connect points and the shapes its collision is made from (<model>.col.npz beside its .glb: Fallout's own collision
bodies, havok.py, each with its layer; the render mesh only for a model without them); then the collision stage
(colliders.model_boxes, from those shapes: its own step, redone alone when colliders.py changes) -> <work>/fo4/pieces.json
(one entry per object) for build.py and the catalog. Kept for re-runs: converted.json (by model, swaps, skeleton; paths
in it relative to the work folder, saved as it goes) and collision.json (by model and structure-or-not).
  python tools/fo4/convert.py [--force] [model substring ...]      (default: everything; what's converted is kept)
  With model substrings only those models are converted (afresh); every other piece comes from the cache as it was.
"""
import hashlib, io, json, math, os, re, struct, sys, time
from multiprocessing import Pool
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (tools/: paths.py)
import paths
import ba2, bgsm, budget, esm, havok, nif

DATA = paths.get('fo4')
WORK = paths.work()
FO4 = os.path.join(WORK, 'fo4')                             # (the import's data: paths.work)
RAW = os.path.join(FO4, 'raw')
DEPOT = 'homestead\\fo4'                                     # where they go in our archive
FORCE = '--force' in sys.argv or 'convert' in os.environ.get('HOMESTEAD_FORCE', '')   # a fresh import: nothing kept
FORCE_COL = FORCE or 'collision' in os.environ.get('HOMESTEAD_FORCE', '')   # (colliders.py changed: every model's boxes)
UNIT = 0.0142875                                            # metres per Fallout unit


class Files:
    """every file of the base game's and the DLCs' archives, by path; the free high-resolution texture pack
    (DLCUltraHighResolution) first when it is installed, so its sharper textures win"""
    def __init__(self):
        self.where = {}
        arcs = [f for f in os.listdir(DATA) if f.lower().endswith('.ba2') and 'voices' not in f.lower()]
        for f in sorted(arcs, key=lambda f: (not f.lower().startswith('dlcultra'), f.lower().startswith('cc'), f.lower())):
            a = ba2.Archive(os.path.join(DATA, f))
            for n in a.names: self.where.setdefault(n, a)
    def read(self, p):
        p = p.lower().replace('/', '\\')
        return self.where[p].read(p) if p in self.where else None


def rel(tex):                                               # a texture's path under textures\, no extension
    return os.path.splitext(tex.replace('/', '\\').lower().lstrip('\\'))[0].replace('textures\\', '', 1) if tex else None


def write_png(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.%d.tmp' % os.getpid()
    img.save(tmp, 'PNG')
    os.replace(tmp, path)                                   # (workers share textures: whole files only)


def texture(files, tex, kind, m):
    """a material's texture: its name under our tex\\ (the Fallout path; roughness named by its smoothness too), None if
    Fallout has no such file. The files themselves are written afterwards by xbm.py, straight from Fallout's blocks."""
    r = rel(tex)
    if not r or 'textures\\' + r + '.dds' not in files.where: return None
    g = rel((m.get('textures') or {}).get('greyscale') or '')
    if kind == 'color' and m.get('palette') and g and 'textures\\' + g + '.dds' in files.where:
        row = int(round(min(1.0, max(0.0, m.get('palette_scale', 1.0))) * 100))   # (greyscale to palette: the grey
        return r + '__pal__' + g.replace('\\', '~') + '__%03d' % row               # coloured by its gradient: xbm.py)
    smooth = round(m.get('smoothness', 1.0), 2)
    return r if kind != 'rough' else r + '_r' + ('' if smooth == 1 else '%03d' % int(smooth * 100))


def tangents(pos, nrm, uv, tri):
    """per-vertex tangents (xyz + handedness) from the UVs: summed per triangle, made orthogonal to the normal"""
    t, b = np.zeros_like(pos), np.zeros_like(pos)
    p0, p1, p2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    w0, w1, w2 = uv[tri[:, 0]], uv[tri[:, 1]], uv[tri[:, 2]]
    e1, e2, d1, d2 = p1 - p0, p2 - p0, w1 - w0, w2 - w0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-12, 1e-12, r)
    st = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
    sb = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    for k in range(3):
        np.add.at(t, tri[:, k], st); np.add.at(b, tri[:, k], sb)
    t = t - nrm * (nrm * t).sum(1, keepdims=True)
    ln = np.linalg.norm(t, axis=1, keepdims=True)
    t = np.where(ln > 1e-8, t / np.maximum(ln, 1e-8), np.array([1.0, 0, 0]))
    w = np.where((np.cross(nrm, t) * b).sum(1) < 0, -1.0, 1.0)
    return np.c_[t, w].astype(np.float32)


def write_glb(path, subs):
    """a .glb with a mesh (and node) per submesh, named submesh_NN_LOD_1 as WolvenKit wants: positions, normals,
    tangents, UVs, u32 indices, a named material each"""
    bins, views, accs, meshes, nodes, mats = bytearray(), [], [], [], [], []
    def add(arr, typ, comp, target):
        nonlocal bins
        a = np.ascontiguousarray(arr)
        while len(bins) % 4: bins.append(0)
        views.append({'buffer': 0, 'byteOffset': len(bins), 'byteLength': a.nbytes, 'target': target})
        bins += a.tobytes()
        acc = {'bufferView': len(views) - 1, 'componentType': comp, 'count': len(a), 'type': typ}
        if typ == 'VEC3' and comp == 5126: acc['min'], acc['max'] = a.min(0).tolist(), a.max(0).tolist()
        accs.append(acc)
        return len(accs) - 1
    for i, s in enumerate(subs):
        attrs = {'POSITION': add(s['pos'].astype(np.float32), 'VEC3', 5126, 34962), 'NORMAL': add(s['nrm'].astype(np.float32), 'VEC3', 5126, 34962),
                 'TANGENT': add(s['tan'], 'VEC4', 5126, 34962), 'TEXCOORD_0': add(s['uv'].astype(np.float32), 'VEC2', 5126, 34962)}
        idx = add(s['tri'].astype(np.uint32).reshape(-1), 'SCALAR', 5125, 34963)
        mats.append({'name': s['material'], 'pbrMetallicRoughness': {}})
        name = 'submesh_%02d_LOD_1' % i
        meshes.append({'name': name, 'primitives': [{'attributes': attrs, 'indices': idx, 'material': i}]})
        nodes.append({'name': name, 'mesh': i})
    while len(bins) % 4: bins.append(0)
    doc = {'asset': {'version': '2.0', 'generator': 'Homestead fo4 convert'}, 'scene': 0, 'scenes': [{'nodes': list(range(len(nodes)))}],
           'nodes': nodes, 'meshes': meshes, 'materials': mats, 'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(bins)}]}
    js = json.dumps(doc).encode()
    js += b' ' * (-len(js) % 4)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bins)))
        f.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
        f.write(struct.pack('<II', len(bins), 0x004E4942) + bytes(bins))


FILES = None
FILL = None                                                 # rack model -> what fills its slots (fill.json, from main)


_CUTS = {}
def cuts(tex, ref):
    """does an alpha-tested texture cut anything away at Fallout's threshold? Our material cuts at a fixed one (about
    half), so a low-threshold one whose alpha never drops that low (a campfire's bark: threshold 24, alpha 25-241)
    would lose most of itself: alpha testing only where Fallout's would cut"""
    r = rel(tex)
    if (r, ref) not in _CUTS:
        b = FILES.read('textures\\' + r + '.dds') if r else None
        try: _CUTS[r, ref] = b is not None and Image.open(io.BytesIO(b)).getchannel('A').getextrema()[0] < ref
        except Exception: _CUTS[r, ref] = True
    return _CUTS[r, ref]


def filled(n, mp, pose=None, movers=None):
    """a model's shapes plus what a full one shows in its slots (a bobblehead stand's bobbleheads, a magazine rack's
    magazines with their own covers): each item's shapes moved to its slot, its materials swapped as the item's are"""
    global FILL
    if FILL is None:
        f = os.path.join(FO4, 'fill.json')
        FILL = json.load(open(f)) if os.path.exists(f) else {}
    out = n.shapes(pose, movers)
    for node, sub, swaps in FILL.get(mp, []):
        at, b = n.node_transform(node), FILES.read(sub)
        if at is None or b is None: continue
        M, T = at
        for sh in nif.Nif(b).shapes():
            sh['pos'] = sh['pos'] @ M.T + T
            if sh['normal'] is not None: sh['normal'] = sh['normal'] @ M.T
            mat = sh['shader'].get('material')
            if mat and bgsm.path(mat) in swaps: sh['shader']['material'] = swaps[bgsm.path(mat)]
            out.append(sh)
    return out


def swaps_of(g, k):
    """a record's material swaps (MODS -> its MSWP: original material -> replacement), by archive path"""
    out, mods = {}, g.field(k, 'MODS')
    sw = g.ref(k, struct.unpack('<I', mods[:4])[0]) if mods else None
    if sw in g.rec:
        f = g.rec[sw][1]
        for (t1, d1), (t2, d2) in zip(f, f[1:]):
            if t1 == 'BNAM' and t2 == 'SNAM': out[bgsm.path(d1.rstrip(b'\0').decode('cp1252'))] = bgsm.path(d2.rstrip(b'\0').decode('cp1252'))
    return out


NUKA = ['meshes\\props\\nukacolabottlefull.nif', 'meshes\\props\\nukacolabottlecherry.nif', 'meshes\\props\\nukacolabottlequantum.nif',
        'meshes\\dlc04\\props\\dlc04_nukacolabottlegrape.nif', 'meshes\\dlc04\\props\\dlc04_nukacolabottlewild.nif',
        'meshes\\dlc04\\props\\dlc04_nukacolabottlequartz.nif', 'meshes\\dlc04\\props\\dlc04_nukacolabottlevictory.nif',
        'meshes\\dlc04\\props\\dlc04_nukacolabottlevoid.nif']


def fill_list(g):
    """the full versions of Fallout's display racks: which item model (and material swaps) goes on which slot node.
    The bobblehead stand: its 20 dummies, one bobblehead each (S.P.E.C.I.A.L. then the skills); a magazine rack: one
    slot per magazine series, the first issue of each"""
    out = {}
    heads = ['strength', 'perception', 'endurance', 'charisma', 'intelligence', 'agility', 'luck', 'barter', 'bgun', 'energyweapons',
             'explosive', 'lockpicking', 'medicine', 'melee', 'repair', 'science', 'smallgun', 'sneak', 'speech', 'unarmed']
    heads = ['meshes\\setdressing\\bobbleheads\\%s.nif' % h for h in heads]
    heads = [h for h in heads if h in FILES.where]
    series = {}
    for k, (t, _) in g.rec.items():
        ed = g.edid(k) or ''
        if t != 'BOOK' or not ed.lower().startswith('perkmag') or not g.field(k, 'MODL'): continue
        s, num = ed.rstrip('0123456789'), ed[len(ed.rstrip('0123456789')):]
        if s not in series or int(num or 0) < series[s][0]: series[s] = (int(num or 0), k)
    mags = []
    for s in sorted(series):
        k = series[s][1]
        swaps = swaps_of(g, k)
        mags.append(('meshes\\' + g.field(k, 'MODL').rstrip(b'\0').decode('cp1252').lower(), swaps))
    for mp in FILES.where:
        if mp.endswith('bobblehead_stand01.nif'):
            out[mp] = [('BobbleHeadDummy%03d' % (i + 1), h, {}) for i, h in enumerate(heads)]
        elif 'magrackworkshop' in mp and mp.endswith('.nif'):
            out[mp] = [('MagPlacement_%02d' % (i + 1), m, sw) for i, (m, sw) in enumerate(mags[:20])]
        elif mp.endswith('dlc04_nukacolarack.nif'):         # the Nuka-Cola display rack: a bottle of each flavour
            out[mp] = [('BottlePlacement_%02d' % (i + 1), b, {}) for i, b in enumerate(b for b in NUKA if b in FILES.where)]
    return out


def swap_key(swaps): return hashlib.md5(repr(sorted(swaps.items())).encode()).hexdigest()[:8] if swaps else ''


def ev(x, base):                                             # Fallout's glow strength -> Cyberpunk's emissive EV (6 at
    return round(min(6.0, base + 2 * math.log2(max(float(x), 0.25))), 2)   # most: 8 was a floodlight - user, 2026-10-02)


# Fallout's soft effect cards: halos, light cones, mist, foam, glare, smoke, caustics, swirls, sparks, embers and the
# animated bolts - it blends them in, fading them by the angle they're seen at; drawn here they were flat glowing
# planes ("weird flat lights coming out of it": the beam emitter). Left out; the solid glows stay (bulbs, flames,
# screens, neon, terminal text)
SOFT_FX = re.compile(r'glowsoft|spotlinear|(?<![a-z])mist|foam|glare|smoke|ambientbeam|darkramp|caustic|teleportholes|sparksplat|embers|'
                     r'shockbolt|shocks01|electricbolts', re.I)


def material_for(matp, shapes):
    """a material key (a .bgsm / .bgem path, or 'ts:' + the model's own texture) -> (Fallout settings, our name, glow
    (emissive texture, colour, EV) or None), or None when it can't be made"""
    mb = None if matp.startswith('ts:') else FILES.read(matp)
    glow = None
    if mb is not None and mb.startswith(b'BGSM'):
        m = bgsm.read(mb)
        mname = os.path.splitext(matp.split('\\')[-1])[0].lower()
        if m.get('emit') and m['textures'].get('glow'):                        # a glow map: lit (always: no power)
            glow = (m['textures']['glow'], m['emit_color'], ev(m['emit_mult'], 3))
    elif mb is not None and mb.startswith(b'BGEM'):       # an effect material (neon tubes, glowing signs): its texture,
        e = bgsm.read_bgem(mb)                             # tinted and glowing, cut out by its alpha (a blended one at half:
                                                           # its see-through ground is Fallout's quarter-alpha backing)
        if SOFT_FX.search(e['textures']['base'] or '') and not (e['blend'][0] and e['lit'] and e['textures'].get('envmap')):
            return None                                    # (a soft card: left out, SOFT_FX - never glass)
        m = dict(textures=dict(diffuse=e['textures']['base'], normal=e['textures'].get('normal') or None, smooth_spec=None),
                 alpha_test=True, alpha_ref=e['alpha_ref'] if e['alpha_test'] else 128, two_sided=e['two_sided'], smoothness=1.0,
                 uv=e['uv'], tint=e['color'], effect=True)
        if e['blend'][0] and e['blend'][2] == 7 and e['lit'] and e['textures'].get('envmap'):   # glass (beakers, panes,
            m['glass'] = True                              # a car's windows): lit and blended, not glowing; its texture
        else:                                              # the grime on it, the glass of its own (build.py: glass.mt)
            glow = (e['textures']['base'], e['color'], ev(e['color_scale'], 4))
        mname = 'fx_' + os.path.splitext(matp.split('\\')[-1])[0].lower()
    elif mb is None and not matp.startswith('ts:') and shapes[0]['shader'].get('type') == 'BSEffectShaderProperty':
        return None
    elif matp.startswith('ts:') and matp.endswith('|fx'):  # an effect shader with no .bgem: its settings in the model
        sd = shapes[0]['shader']                           # (a track light's glow, a halo): as a .bgem's
        ts = sd.get('textures') or []
        if not ts or not ts[0] or ts[0].lower().endswith('_n.dds') or SOFT_FX.search(ts[0]): return None
        m = dict(textures=dict(diffuse=ts[0], normal=None, smooth_spec=None), alpha_test=True, alpha_ref=128, two_sided=True,
                 smoothness=1.0, tint=sd['emit'], effect=True)
        glow = (ts[0], sd['emit'], ev(min(sd.get('emit_mult', 1), 4), 4))
        mname = 'fx_' + os.path.splitext(ts[0].replace('/', '\\').split('\\')[-1])[0].lower()
    else:                                                  # the model's texture set, plain material settings
        ts = shapes[0]['shader'].get('textures') or []
        if not ts or not ts[0]: return None
        if ts[0].lower().endswith('_n.dds'): return None   # a normal map as its colour: heat haze over a fire, steam
                                                           # off a pot (refraction; drawn solid it was a square)
        a = shapes[0].get('alpha')                          # its alpha property: tested, or blended (a decal: cut)
        m = dict(textures=dict(diffuse=ts[0], normal=ts[1] if len(ts) > 1 and ts[1] else None, smooth_spec=ts[2] if len(ts) > 2 and ts[2] else None),
                 alpha_test=bool(a and (a[0] or a[1])), alpha_ref=a[2] if a and a[1] else 64, two_sided=False, smoothness=1.0)
        mname = 'ts_' + os.path.splitext(ts[0].replace('/', '\\').split('\\')[-1])[0].lower()
        sd = shapes[0]['shader']
        if matp.endswith('|emit'):                         # Own_Emit: it glows in its emissive colour (a bulb: white,
            glow = (sd.get('glow_map') or ts[0], sd['emit'], ev(min(sd['emit_mult'], 4), 3))   # x10: capped), through
            mname += '_lit'                                # its glow map if it has one, else its own texture
    return m, mname, glow


def save_shapes(path, shapes):
    """a model's collision shapes, as they were posed (metres, its space; float64: the boxes come out as they would
    from the model itself), for the collision stage: Fallout's bodies [(vertices, triangles - none for a convex point
    set, layer, convex radius)], or the render mesh's [(vertices, triangles)]"""
    tmp = path + '.%d.tmp' % os.getpid()
    extra = {'layer': np.array([s[2] for s in shapes]), 'r': np.array([s[3] for s in shapes])} if shapes and len(shapes[0]) == 4 else {}
    with open(tmp, 'wb') as f:
        np.savez(f, **{k: a for i, s in enumerate(shapes) for k, a in (('v%d' % i, s[0]), ('f%d' % i, s[1]))}, **extra)
    os.replace(tmp, path)


def load_shapes(path):
    with np.load(path) as z:
        n = len([k for k in z.files if k[0] == 'v'])
        if 'layer' in z.files: return [(z['v%d' % i], z['f%d' % i], int(z['layer'][i]), float(z['r'][i])) for i in range(n)]
        return [(z['v%d' % i], z['f%d' % i]) for i in range(n)]


def short(p): return os.path.relpath(p, WORK) if p else p   # (converted.json: the work folder may move)
def full(p): return os.path.join(WORK, p) if p else p


def model(job):
    """one model (its path under meshes\\), as one object has it (its material swaps: an object's colour, a neon
    letter's glyph): .glb, textures, materials, size, connect points, the shapes collision is made from (col: an .npz
    beside the .glb - Fallout's collision bodies, or the render mesh when it has none or they can't be read); None if
    unusable. job: the model path, or (path, swaps, skeleton). Paths in the result are
    relative to the work folder. An animated one (anim.py) is posed in its rest state; each node its sequences move
    becomes a part - its own .glb in that node's space, its own collision shapes (the bodies on that node or under it:
    a door leaf's), and where it is in every kept sequence."""
    mp, swaps, skel = (job, {}, None) if isinstance(job, str) else (tuple(job) + (None,))[:3]
    global FILES
    if FILES is None: FILES = Files()
    import anim
    try:
        b = FILES.read(mp)
        if b is None: return mp, None
        n = nif.Nif(b)
        if skel and FILES.read(skel): n.attach(nif.Nif(FILES.read(skel)))      # (a turret's bones: its race's skeleton)
        seqs = {k: v for k, v in n.sequences().items() if v['tracks'] or v['vis'] or v['sounds']}   # (empty ones: nothing to see or hear)
        if skel and not seqs:                              # a turret, still: its head sweeps (Fallout's is Havok's)
            w = n.node_worlds()
            head = next((b for b in anim.SWEEP if b in w), None)
            if head:
                M = w[head][0] / np.maximum(np.linalg.norm(w[head][0], axis=0, keepdims=True), 1e-9)
                up = M.T @ np.array([0.0, 0.0, 1.0])       # the vertical, in the head's own frame
                seqs = {'Idle': dict(cycle=0, start=0.0, vis={}, sounds=[], stop=anim.SWEEP[head][1],
                                     tracks={head: anim.sweep(n.node_locals()[head][1], tuple(up / np.linalg.norm(up)), *anim.SWEEP[head])})}
        movers = anim.moving(seqs)
        rest = anim.rest_state(seqs)
        locals_ = n.node_locals() if seqs else {}
        pose = {}
        if rest:                                           # the rest state: every node its sequence places
            s = seqs[rest]; tt = anim.rest_time(s)
            for node, tr in s['tracks'].items():
                if node in locals_: pose[node] = anim.local_at(tr, locals_[node], tt)
        groups, fires, part_at = {}, [], {}
        for sh in filled(n, mp, pose, movers):              # by part, then material; a shape with no material (its
            mat = sh['shader'].get('material')             # textures named in the model: a stool's cushion) by texture
            if mat and bgsm.path(mat) in swaps: mat = swaps[bgsm.path(mat)]
            ts = sh['shader'].get('textures') or []
            sd = sh['shader']                              # (glowing by the model's own settings: a bulb, a halo -
            lit = sd.get('effect') and '|fx' or (sd.get('emit') and max(sd['emit']) > 0.01 and sd.get('emit_mult', 0) > 0 and '|emit') or ''   # its own key)
            key = bgsm.path(mat) if mat else ('ts:' + ts[0].lower() + lit) if ts and ts[0] else None
            if sh['shader'].get('type') == 'BSEffectShaderProperty' and 'fire' in (sh['name'] or '').lower():
                c = [round(float(v), 3) for v in sh['pos'].mean(axis=0) * UNIT]   # flames drawn as glow cards: a fire there
                if not any(sum((a - b) ** 2 for a, b in zip(c, f)) < 0.16 for f in fires): fires.append(c)
            elif key and sh['uv'] is not None:
                groups.setdefault((sh.get('part') or '', key), []).append(sh)
                if sh.get('part'): part_at[sh['part']] = sh['part_at']
        if not groups: return mp, None
        try: hk = havok.bodies(n, pose) or None             # Fallout's own collision (at rest), by the part it moves with
        except ValueError: hk = None                       # (none, or unreadable: the render mesh's shapes instead)
        hshapes, up = {}, n.parents() if part_at else {}
        for d in hk or []:
            node = d['node']
            while node and node not in part_at: node = up.get(node)
            hshapes.setdefault(node or '', []).append((d['v'], d['f'], d['layer'], d['r']))
        stem = os.path.splitext(mp)[0].replace('meshes\\', '', 1) + ('__' + swap_key(swaps) if swaps else '')   # (a variant: its own mesh)
        names = [''] + sorted(p for p in part_at)          # '' the static model, then the moving parts
        built, allp = {}, []
        gsubs, gmats = [], []                              # the static model's glowing shapes, lit (its glow mesh)
        for part in names:
            subs, mats, layer, cshapes = [], [], 0, []
            if part:                                        # into the part node's own space (it moves; the mesh with it)
                M, T = part_at[part]
                Rn = M / np.maximum(np.linalg.norm(M, axis=0, keepdims=True), 1e-9)
            for (gp, matp), shapes in sorted(groups.items()):
                if gp != part: continue
                r = material_for(matp, shapes)
                if not r: continue
                m, mname, glow = r
                t = m['textures']
                color = texture(FILES, t['diffuse'], 'color', m)
                if not color: continue
                base = dict(name=mname, alpha_test=bool(m['alpha_test']) and cuts(t['diffuse'], m['alpha_ref']), alpha_ref=m['alpha_ref'], two_sided=m['two_sided'], color=color,
                            normal=texture(FILES, t['normal'], 'normal', m) if t.get('normal') else None,
                            rough=texture(FILES, t['smooth_spec'], 'rough', m) if t.get('smooth_spec') else None,
                            **({'tint': [round(float(c), 3) for c in m['tint']]} if m.get('tint') else {}))
                lit = ({'emissive': texture(FILES, glow[0], 'color', m), 'emissive_color': [round(float(c), 3) for c in glow[1]], 'emissive_ev': glow[2]}
                       if glow and texture(FILES, glow[0], 'color', m) else None)
                own = lit and not part                      # (a moving part's glow stays in it, always lit)
                mats.append(dict(base, **(lit if lit and not own else {})))
                if own: gmats.append(dict(base, name=mname + '_glow', **lit))
                ou, ov, su, sv = m.get('uv') or (0.0, 0.0, 1.0, 1.0)              # the material's UV offset / scale
                pos, uv, nrm, tri, base = [], [], [], [], 0
                for sh in shapes:
                    pw = sh['pos'] * UNIT                  # (where it is, posed: for size and collision)
                    allp.append(pw)
                    p = ((sh['pos'] - T) @ Rn) * UNIT if part else pw   # (rotation only: a node's scale stays in the mesh)
                    nn = sh['normal'] if sh['normal'] is not None else np.tile([0, 0, 1.0], (len(p), 1))
                    if part: nn = nn @ Rn                  # (world normal -> the node's frame: the inverse rotation)
                    pos.append(np.c_[p[:, 0], p[:, 2], -p[:, 1]])                 # Cyberpunk (Z up) -> glTF (Y up)
                    uv.append(sh['uv'] * np.array([su, sv], np.float32) + np.array([ou, ov], np.float32))
                    nrm.append(np.c_[nn[:, 0], nn[:, 2], -nn[:, 1]])
                    tri.append(sh['tri'].astype(np.int64) + base)
                    base += len(p)
                    if len(sh['tri']) and not m.get('effect'): cshapes.append((pw, sh['tri']))   # (collision: not glows)
                P, N, U, Tt = np.vstack(pos), np.vstack(nrm), np.vstack(uv), np.vstack(tri)
                N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-8)
                if m['two_sided']:                           # Cyberpunk's material draws one side: add the back faces
                    k = len(P)
                    P, N, U, Tt = np.vstack([P, P]), np.vstack([N, -N]), np.vstack([U, U]), np.vstack([Tt, Tt[:, ::-1] + k])
                if m.get('glass'):                          # (the glass itself, then the grime on it a hair out: no fighting)
                    G = Tt[:sum(len(t) for t in tri)]           # (one side: Cyberpunk's glass draws both)
                    subs.append(dict(pos=P, nrm=N, uv=U, tri=G, tan=tangents(P, N, U, G), material=mname + '_glass'))
                    mats.insert(len(mats) - 1, dict(name=mname + '_glass', glass=True, tint=mats[-1].get('tint')))
                    P = P + N * 0.001
                elif m.get('decal') or m.get('effect'):     # (a decal, a glow layer, a screen: in the plane of what it's on -
                    layer += 1                              # Fallout draws it with a depth bias; here a hair out, or it
                    P = P + N * 0.001 * layer               # flickers - each one more, the last on top: a TV's black, noise,
                                                            # "please stand by" screens stacked)
                subs.append(dict(pos=P, nrm=N, uv=U, tri=Tt, tan=tangents(P, N, U, Tt), material=mname))
                if own:                                     # (lifted 1.5 mm off it: no fighting the unlit one)
                    Pg = P + N * 0.0015
                    gsubs.append(dict(pos=Pg, nrm=N, uv=U, tri=Tt, tan=tangents(Pg, N, U, Tt), material=mname + '_glow'))
            if not subs: continue
            pstem = stem + ('__p%d' % names.index(part) if part else '')
            out = os.path.join(RAW, DEPOT, pstem)
            write_glb(out + '.glb', subs)
            if hk: cshapes = hshapes.get(part, [])
            if cshapes: save_shapes(out + '.col.npz', cshapes)
            built[part] = dict(mesh=DEPOT + '\\' + pstem + '.mesh', glb=short(out + '.glb'), materials=mats,
                               col=short(out + '.col.npz') if cshapes else None)
        if not built: return mp, None
        glow_part = None
        if gsubs:
            gstem = stem + '__glow'
            write_glb(os.path.join(RAW, DEPOT, gstem + '.glb'), gsubs)
            glow_part = dict(mesh=DEPOT + '\\' + gstem + '.mesh', glb=short(os.path.join(RAW, DEPOT, gstem + '.glb')), materials=gmats)
        allp = np.vstack(allp)
        cps = [dict(name=c['name'], pos=[round(v * UNIT, 4) for v in c['pos']], rot=c['rot']) for c in n.connect_points()]
        origin = next((c['pos'] for c in cps if c['name'] == 'P-WS-Origin'), [0, 0, float(allp[:, 2].min())])
        main = built.get('') or dict(mesh=None, glb=None, materials=[], col=None)
        if hk and '' not in built and hshapes.get(''):      # (nothing drawn but parts: its static bodies still collide)
            save_shapes(os.path.join(RAW, DEPOT, stem + '.col.npz'), hshapes[''])
            main['col'] = short(os.path.join(RAW, DEPOT, stem + '.col.npz'))
        res = dict(fires=fires, mesh=main['mesh'], glb=main['glb'], materials=main['materials'], connect=cps,
                   min=[round(float(v), 3) for v in allp.min(0)], max=[round(float(v), 3) for v in allp.max(0)],
                   base=[round(float(v), 3) for v in origin], col=main['col'], **({'glow': glow_part} if glow_part else {}))
        parts = [p for p in names[1:] if p in built]
        if parts:                                          # the moving parts: where each is, frame by frame
            def frame(pz):
                w = n.node_worlds(pz)
                out = []
                for p in parts:
                    M, T = w[p]
                    q = anim.matq(M / np.maximum(np.linalg.norm(M, axis=0, keepdims=True), 1e-9))
                    out.append([round(float(v) * UNIT, 4) for v in T] + [round(float(v), 5) for v in q])
                return out
            seq_out = {}
            for name, s in seqs.items():
                if name not in anim.PLAY: continue
                nf = max(1, int(round((s['stop'] - s['start']) * anim.RATE)) + 1)
                frames = []
                for fi in range(nf):
                    t = min(s['stop'], s['start'] + fi / anim.RATE)
                    pz = dict(pose)
                    for node, tr in s['tracks'].items():
                        if node in locals_: pz[node] = anim.local_at(tr, locals_[node], t)
                    frames.append(frame(pz))
                seq_out[name] = dict(loop=s['cycle'] == 0, dur=round(s['stop'] - s['start'], 3), frames=frames,
                                     **({'snd': [[round(t, 3), int(pl), e] for t, pl, e in s['sounds']]} if s.get('sounds') else {}))
            res['parts'] = [dict(built[p], node=p, at=frame(pose)[i]) for i, p in enumerate(parts)]
            res['anim'] = dict(rest=rest, seqs=seq_out)
        return mp, res
    except Exception as e:
        import traceback
        return mp, {'error': (repr(e) + ' ' + traceback.format_exc().splitlines()[-2])[:300]}


def run(job):                                               # a pool job: (its key, (model, swaps, skeleton)) -> (key, result)
    return job[0], model(job[1])[1]


def collide(job):
    """a pool job of the collision stage: (key, [shapes .npz of the static model, then each part's], structure?) ->
    (key, [the collision of each: colliders.model_boxes])"""
    from colliders import model_boxes
    key, cols, walk = job
    return key, [model_boxes(load_shapes(full(c)), walk) if c else dict(boxes=[]) for c in cols]


def collision(todo):
    """every converted model's boxes, for each way an object uses it ({key: (result, structure?)}): from the shapes it
    saved (colliders.model_boxes), kept in collision.json while those files and colliders.py stay as they were ->
    {key: [the collision of the static model, then each part's]}"""
    path = os.path.join(FO4, 'collision.json')
    old = {} if FORCE_COL or not os.path.exists(path) else json.load(open(path))
    cols = {k: [r.get('col')] + [p.get('col') for p in r.get('parts', [])] for k, (r, _) in todo.items()}
    stamp = lambda k: [[os.path.getsize(full(c)), os.stat(full(c)).st_mtime_ns] if c else None for c in cols[k]]
    out = {k: e['boxes'] for k, e in old.items() if k in todo and e['src'] == stamp(k) and all(isinstance(x, dict) for x in e['boxes'])}
    new = [k for k in todo if k not in out]
    print(len(out), 'collisions kept,', len(new), 'to make', flush=True)
    paths.progress('collision', 0, len(new))
    if new:                                                  # (heaviest first, no more at once than free memory holds:
        from colliders import heft                           # a big shack's rooms take GBs, a chair's MBs)
        est = {k: heft([s for c in cols[k] if c for s in load_shapes(full(c))] if todo[k][1] else [], todo[k][1]) for k in new}
        room, most, busy, n = max(1.0, budget.free_gb() - 1), budget.workers(0.3), {}, 0
        with Pool(most) as pool:
            for k in sorted(new, key=lambda k: -est[k]) + [None]:   # (None: the end - wait for the rest)
                while busy and (k is None or len(busy) >= most or sum(est[x] for x in busy) + est[k] > room):
                    for x in [x for x, a in busy.items() if a.ready()]:
                        out[x], n = busy.pop(x).get()[1], n + 1
                        paths.progress('collision', n, len(new))
                    time.sleep(0.02)
                if k: busy[k] = pool.apply_async(collide, ((k, cols[k], todo[k][1]),))
    save_json(path, {k: dict(src=stamp(k), boxes=b) for k, b in out.items()})
    return out


def save_json(path, d):                                     # (whole or not at all: a stopped run leaves the last one)
    json.dump(d, open(path + '.tmp', 'w'))
    os.replace(path + '.tmp', path)


# turrets are actors: their model is their race's skin (ARMO -> ARMA MOD2), skinned to the race's skeleton (ANAM).
# Several share one body (Fallout gives each its gun through weapon mods on a dummy weapon): one per model, named here.
ACTOR_NAMES = {'turretworkshop.nif': 'Turret', 'turretstanding.nif': 'Machinegun Turret',
               'turretstandingmounted.nif': 'Heavy Machinegun Turret', 'turretspotlightworkshop.nif': 'Spotlight'}


def actor_model(g, x):
    """an actor record's (model path, skeleton path) or (None, None)"""
    def ref(k, name):
        d = g.field(k, name)
        r = g.ref(k, struct.unpack('<I', d[:4])[0]) if d and len(d) >= 4 else None
        return r if r in g.rec else None
    race = ref(x, 'RNAM')
    skin = ref(x, 'WNAM') or (race and ref(race, 'WNAM'))
    if not (race and skin): return None, None
    sk = g.field(race, 'ANAM')
    for d in g.fields(skin, 'MODL'):
        a = g.ref(skin, struct.unpack('<I', d[:4])[0]) if len(d) == 4 else None
        m = g.field(a, 'MOD2') if a in g.rec else None
        if m and b'dummy' not in m.lower():
            path = lambda b: 'meshes\\' + b.rstrip(b'\0').decode('cp1252').lower().replace('/', '\\')
            return path(m), sk and path(sk)
    return None, None


# power armour as display props (user, 2026-10-02): a frame and a set's six pieces, each skinned to the power armour
# skeleton (its bind pose: a natural stand), converted as models of their own and shown as one piece a set
# (power_armor merges them); not workshop objects in Fallout. A set whose files the player hasn't (a DLC's) is left out
PA = 'meshes\\actors\\powerarmor\\characterassets\\'
PA_PARTS = ['frame', 'body', 'helmet', 'larm', 'rarm', 'lleg', 'rleg']
PA_SETS = {                                                  # set -> (name, frame, a part's model: %s the part)
    't45': ('T-45 Power Armor', PA + 'frame.nif', PA + 'mods\\pa_t45_%s.nif'),
    't51': ('T-51 Power Armor', PA + 'frame.nif', PA + 'mods\\pa_t51_%s.nif'),
    't60': ('T-60 Power Armor', PA + 'frame.nif', PA + 'mods\\pa_t60_%s.nif'),
    'x01': ('X-01 Power Armor', PA + 'frame.nif', PA + 'mods\\pa_x1_%s.nif'),
    'raider': ('Raider Power Armor', PA + 'paframe_raider.nif', PA + 'mods\\pa_raider_%s.nif'),
    'overboss': ('Overboss Power Armor', PA + 'frame.nif', 'meshes\\actors\\dlc04\\overbosspowerarmor\\overboss_%s.nif'),   # (Nuka-World)
}


def power_armor_objects():
    out = []
    for s, (name, frame, part_model) in PA_SETS.items():
        for part in PA_PARTS:
            out.append(dict(rec=None, edid='pa_%s_%s' % (s, part), name=name, menu=['Decorations', 'Power Armor'], order=10 ** 6 + len(out), kind='STAT',
                            model=frame if part == 'frame' else part_model % part, skeleton=PA + 'skeleton.nif', swaps={}))
    return out


def power_armor(pieces):
    """each set's converted models as one piece: the frame the model, the armour its parts at rest; a set short of
    its frame or body is left out"""
    out = [p for p in pieces if not p['key'].startswith('fo4_pa_')]
    for s in PA_SETS:
        pa = {p['key']: p for p in pieces if p['key'].startswith('fo4_pa_%s_' % s)}
        main = pa.get('fo4_pa_%s_frame' % s)
        rest = [pa[k] for k in ('fo4_pa_%s_%s' % (s, x) for x in PA_PARTS[1:]) if k in pa]
        if not main or not any(k.endswith('_body') for k in pa): continue
        out.append(dict(main, key='fo4_pa_' + s, edid='pa_' + s,
                        parts=[dict(mesh=p['mesh'], glb=p['glb'], materials=p['materials'], boxes=p['boxes'], at=[0, 0, 0, 1, 0, 0, 0]) for p in rest],
                        min=[min(p['min'][i] for p in [main] + rest) for i in range(3)], max=[max(p['max'][i] for p in [main] + rest) for i in range(3)]))
    return out


def objects(g):
    """every object the workshop menu builds: (record key, edid, name, menu path, kind, model path)"""
    paths, out, seen = esm.menu_paths(g), [], set()
    order = {tuple(v): i for i, v in enumerate(paths.values())}       # the menu's own order of its folders
    for k, (t, _) in g.rec.items():
        if t != 'COBJ': continue
        fn, cn = g.field(k, 'FNAM'), g.field(k, 'CNAM')
        if not (fn and cn): continue
        cats = [paths[g.ref(k, struct.unpack_from('<I', fn, i)[0])] for i in range(0, len(fn), 4) if g.ref(k, struct.unpack_from('<I', fn, i)[0]) in paths]
        o = g.ref(k, struct.unpack('<I', cn)[0])
        if not cats or o not in g.rec: continue
        objs = [g.ref(o, struct.unpack('<I', d)[0]) for d in g.fields(o, 'LNAM')] if g.rec[o][0] == 'FLST' else [o]
        for x in objs:
            if x not in g.rec or x in seen: continue
            if g.rec[x][0] == 'NPC_':                        # a turret
                model, skel = actor_model(g, x)
                if not model or (skel, model) in seen: continue
                seen.add(x); seen.add((skel, model))
                name = ACTOR_NAMES.get(model.split('\\')[-1], g.full(x) or g.edid(x))
                if 'mountedlight' in (skel or ''): name = 'Wall ' + name
                out.append(dict(rec=x, edid=g.edid(x), name=name, menu=cats[0], order=order[tuple(cats[0])], kind='NPC_',
                                model=model, skeleton=skel, swaps={}))
                continue
            m = g.field(x, 'MODL')
            if not m: continue
            seen.add(x)
            out.append(dict(rec=x, edid=g.edid(x), name=g.full(x) or g.edid(x), menu=cats[0], order=order[tuple(cats[0])], kind=g.rec[x][0],
                            model='meshes\\' + m.rstrip(b'\0').decode('cp1252').lower().replace('/', '\\'), swaps=swaps_of(g, x)))
    return out + power_armor_objects()


CACHE = 2                                                    # converted.json's layout: {format, models: {job key: result}}
                                                             # (no boxes - the collision stage's -, paths relative)


VBOX = dict(WorkshopOverrideXYBounds='xy', WorkshopOverrideXBoundMin='x0', WorkshopOverrideXBoundMax='x1', WorkshopOverrideYBoundMin='y0',
            WorkshopOverrideYBoundMax='y1', WorkshopOverrideZBoundMin='z0', WorkshopOverrideZBoundMax='z1')
def snap_props(g, k):
    """what Fallout4.exe reads off a record for snapping (docs/snap_families_research_2026-10-03.md): `snapR` its query
    radius (WorkshopSnapPointRadius, AV 0x33E; m, when > 0), `ovl` its WorkshopItemOverlap (AV 0x337; m), `must`
    (WorkshopMustBeSnapped: a keyword, or its AV on one piece), `ignoreOcc` (WorkshopIgnoreNonRefOccupiedSnap),
    `vbox` the box its snapped pose is tested with (WorkshopOverride*Bound*: xy a side, x0..z1; m)"""
    out, kws = {}, g.field(k, 'KWDA') or b''
    if any(g.edid(g.ref(k, f)) == 'WorkshopMustBeSnapped' for f in struct.unpack('<%dI' % (len(kws) // 4), kws) if g.ref(k, f) in g.rec):
        out['must'] = True
    for d in g.fields(k, 'PRPS'):
        for i in range(0, len(d) - 7, 8):
            fid, v = struct.unpack_from('<If', d, i)
            r = g.ref(k, fid)                                # (0x33E and 0x337 have no record: the exe's own)
            n = g.edid(r) if r in g.rec else r
            if n == ('Fallout4.esm', 0x33E) and v > 0: out['snapR'] = round(v * UNIT, 4)
            elif n == ('Fallout4.esm', 0x337): out['ovl'] = round(v * UNIT, 4)
            elif n == 'WorkshopMustBeSnappedAV' and v: out['must'] = True
            elif n == 'WorkshopIgnoreNonRefOccupiedSnap' and v: out['ignoreOcc'] = True
            elif n in VBOX and v: out.setdefault('vbox', {})[VBOX[n]] = round(v * UNIT, 4)   # (the snap veto's box: 0 = unset)
    return out


def placed(r, c):
    """a kept result as pieces.json has it: full paths, and in place of its shapes file its collision c
    (colliders.model_boxes: boxes, and what of col - havok or voxel -, ramps it has)"""
    out = {k: full(v) if k == 'glb' else v for k, v in r.items() if k != 'col'}
    if 'col' in r: out.update(boxes=c['boxes'], **{k: v for k, v in c.items() if k != 'boxes' and v})
    return out


def main():
    budget.gentle()                                         # (a player's PC: below normal priority, sized workers)
    g = esm.Game()
    objs = objects(g)
    want = [a.lower() for a in sys.argv[1:] if not a.startswith('--')]   # (model names to convert alone; not --from-game)
    walk = lambda o: o['menu'][0] == 'Structures'            # (walk-in collision - rooms, prefabs - for structures only)
    jobkey = lambda o: o['model'] + ('|' + swap_key(o['swaps']) if o['swaps'] else '') + ('|' + o['skeleton'] if o.get('skeleton') else '')
    jobs = {jobkey(o): (o['model'], o['swaps'], o.get('skeleton')) for o in objs}
    models = sorted(jobs)
    print(len(objs), 'objects,', len({o['model'] for o in objs}), 'models,', len(jobs), 'with their variants', flush=True)
    global FILES
    if FILES is None: FILES = Files()
    json.dump(fill_list(g), open(os.path.join(FO4, 'fill.json'), 'w'), indent=0)   # (the workers read it)
    # models converted before are kept (their results in converted.json, their files on disk) unless --force; a
    # partial run - model names given - redoes just those: the cache, pieces.json and what follows keep every other
    # piece as it was (it once wrote pieces.json, and with --force converted.json, with only the named ones)
    cache_path = os.path.join(FO4, 'converted.json')
    c = {} if FORCE and not want or not os.path.exists(cache_path) else json.load(open(cache_path))
    # (models no object uses now dropped; an older layout - boxes inside, full paths - converted again)
    cache = {m: r for m, r in c.get('models', {}).items() if m in jobs} if c.get('format') == CACHE else {}
    files = lambda r: [r.get('glb'), r.get('col'), (r.get('glow') or {}).get('glb')] + [x for pt in r.get('parts', []) for x in (pt['glb'], pt.get('col'))]
    named = lambda m: any(w in jobs[m][0] for w in want)
    done = {m: r for m, r in cache.items() if all(os.path.exists(full(x)) for x in files(r) if x) and not (want and named(m))}
    new = [m for m in models if m not in done and (not want or named(m))]
    print(len(done), 'models kept,', len(new), 'to convert', flush=True)
    paths.progress('models', 0, len(new))
    with Pool(budget.workers(1.2)) as pool:                 # (measured 2026-10-02: ~1.1 GB a worker)
        for i, (mp, res) in enumerate(pool.imap_unordered(run, [(m, jobs[m]) for m in new], chunksize=4)):
            done[mp] = res
            if res and 'error' not in res: cache[mp] = res  # (failures are tried again next time)
            paths.progress('models', i + 1, len(new))
            if i % 100 == 99:                               # (saved as it goes: a stopped run picks up from here)
                print(i + 1, len(new), flush=True); save_json(cache_path, dict(format=CACHE, models=cache))
    save_json(cache_path, dict(format=CACHE, models=cache))
    ok = lambda o: (r := done.get(jobkey(o))) and 'error' not in r
    ckey = lambda o: jobkey(o) + ('|walk' if walk(o) else '')
    boxes = collision({ckey(o): (done[jobkey(o)], walk(o)) for o in objs if ok(o)})
    pieces, bad = [], []
    key = lambda o: 'fo4_' + (o['edid'] or o['model']).lower()
    for o in objs:
        r = done.get(jobkey(o))
        if not ok(o): bad.append((o['edid'], o['model'], (r or {}).get('error'))); continue
        b = boxes[ckey(o)]
        row = placed(r, b[0])
        if r.get('parts'): row['parts'] = [placed(pt, pb) for pt, pb in zip(r['parts'], b[1:])]
        if 'col' not in row and (c := next((pt['col'] for pt in row.get('parts', []) if pt.get('col')), None)): row['col'] = c   # (a door: its leaf's)
        if r.get('glow'): row['glow'] = placed(r['glow'], None)
        if o['rec'] and g.field(o['rec'], 'NVNM'): row['nvnm'] = True   # (Fallout's own walk surface: people walk it)
        if o['rec']: row.update(snap_props(g, o['rec']))
        pieces.append(dict(key=key(o), name=o['name'], menu=o['menu'], order=o['order'], kind=o['kind'], edid=o['edid'], **row))
    pieces = power_armor(pieces)
    pp = os.path.join(FO4, 'pieces.json')
    if want and os.path.exists(pp):                         # a partial run: only the named objects' rows replaced
        pa = lambda k: re.sub(r'^(fo4_pa_[^_]+)_.*', r'\1', k)   # (a power armour part: its set's row)
        redo = {pa(key(o)) for o in objs if jobkey(o) in new}
        now = {p['key']: p for p in pieces if p['key'] in redo}
        pieces = [now.pop(p['key'], p) if p['key'] in redo else p for p in json.load(open(pp))] + list(now.values())
        bad = [x for x in bad if any(w in x[1] for w in want)]
    json.dump(pieces, open(pp, 'w'))
    json.dump(bad, open(os.path.join(FO4, 'skipped.json'), 'w'), indent=0)
    print(len(pieces), 'pieces,', len(bad), 'skipped (source/fo4/skipped.json)')
    if not pieces:                                          # (never an empty archive installed over a good one)
        raise SystemExit('no Fallout 4 workshop pieces found in %s - nothing imported' % paths.get('fo4'))
    import xbm, lights, sounds, furniture
    made = [r for m in new if (r := done.get(m)) and 'error' not in r]   # (a partial run: its own textures only)
    if made or not want: xbm.main(made if want else pieces)
    lights.patch(g, FILES)                                  # lamps: their light, into pieces.json
    sounds.patch(g, FILES)                                  # doors, machines, fires: their sounds (Audioware)
    furniture.patch(g)                                      # chairs, beds, counters: where people use them


if __name__ == '__main__':
    main()
