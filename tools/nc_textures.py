"""Night City's colour textures for the menu thumbnails (tools/make_thumbs.py): every harvested prop's mesh uncooked
again by WolvenKit, this time with its materials (the harvest's glbs have none), and each material of the item's
first appearance baked to one 512 px base-colour PNG:
  multilayered.mt     the mlsetup's layers stacked by the mlmask: each layer its mltemplate's colour texture (tiled
                      matTile times) times its colorScale tint, in linear light (microblends, levels, normals ignored)
  metal_base & co     the BaseColor / Diffuse texture times its scale; an emissive one its EmissiveColor where its
                      Emissive texture is lit, at full brightness (Workbench has no glow: lit reads as bright)
  signages / screens  neon and screens: their colour, or their picture, at full brightness
  decals, fx          cut out (alpha 0): a decal's stain is drawn over the real surface in the game
  glass               see-through in its tint; holograms their picture or colour, lit
  hair, skin, eyes    a person's: hair cards in their profile's colour cut by the strands, the scalp's and brows' paint
  speedtree           the DiffuseMap, its alpha cut at 0.5 (leaf cards)
Writes source/thumbs_nc/tex/<depot>/<material>.png and source/thumbs_nc/materials.json:
  {glb: {"submesh_NN": [png, alpha threshold or null(, opacity)]}} - by submesh (the mesh's chunk: the glbs' one material
  "Default" is shared by all), merged into thumb_items' material maps by make_thumbs.py.
Cached by glb (--all: again). WolvenKit's export (~15 MB a mesh, shared surfaces counted again per batch) is deleted
after each batch (--keep: kept in source/thumbs_nc/raw_<n> to look at).
usage: python tools/nc_textures.py [--all] [--keep] [key ...]     (keys: only those items; none: every harvested one)
"""
import colorsys, glob, json, math, os, re, shutil, struct, subprocess, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fo4'))
import budget, paths

HARVEST = os.path.join(paths.work(), 'harvest')
NC = os.path.join(paths.work(), 'thumbs_nc')
TEX = os.path.join(NC, 'tex')
MATS = os.path.join(NC, 'materials.json')
SIZE, BATCH = 512, 40                                        # px of a baked texture; meshes per WolvenKit run


def glb_of(depot): return os.path.join(HARVEST, 'glb', depot[:-5] + '.glb')
def look_glb(depot, look):
    """a mesh the harvest hasn't (a person's, a weapon's: tools/npc_looks.py, make_weapons.py), in one look: its glb,
    kept from the export here (one file per look - links to the same one - since the textures go by glb)"""
    return os.path.join(NC, 'glb', depot[:-5] + '@' + re.sub(r'\W', '_', look) + '.glb')


def items():
    """{glb: [depot, appearance]}: every harvested prop (items.json, items_more.json) by its first appearance, and any
    other harvest glb thumb_items.json renders (the kit's: its default)"""
    out = {}
    for f in ('items.json', 'items_more.json'):
        p = os.path.join(HARVEST, f)
        for h in json.load(open(p)) if os.path.exists(p) else []:
            out.setdefault(glb_of(h['mesh']), [h['mesh'], (h.get('apps') or ['default'])[0], h['key']])
    for f, parts in (('weapons.json', lambda v: [(w['preset'], w['parts']) for w in v]), (os.path.join('survey', 'people_looks.json'), dict.items)):
        p = os.path.join(paths.work(), f)
        for key, ps in parts(json.load(open(p))) if os.path.exists(p) else []:
            for q in ps: out.setdefault(look_glb(q[0], q[1]), [q[0], q[1], key])
    p = os.path.join(paths.work(), 'thumb_items.json')
    pre = os.path.join(HARVEST, 'glb') + os.sep
    for key, parts, *_ in json.load(open(p)) if os.path.exists(p) else []:
        for q in parts:
            if q[0].startswith(pre): out.setdefault(q[0], [q[0][len(pre):-4] + '.mesh', None, key])
    return out


# --- textures -------------------------------------------------------------------------------------------------------
def dds(path):
    """a DDS as RGBA uint8 (PIL's decoders; the uncompressed formats it lacks read here: R8, R8G8, RGBA16F)"""
    try:
        return np.asarray(Image.open(path).convert('RGBA'))
    except Exception:
        b = open(path, 'rb').read()
        h, w = struct.unpack_from('<II', b, 12)
        fmt = struct.unpack_from('<I', b, 128)[0] if b[84:88] == b'DX10' else None
        n = w * h
        if fmt == 61: g = np.frombuffer(b, np.uint8, n, 148).reshape(h, w); return np.dstack([g, g, g, np.full_like(g, 255)])
        if fmt == 49:
            a = np.frombuffer(b, np.uint8, n * 2, 148).reshape(h, w, 2)
            return np.dstack([a[..., 0], a[..., 1], np.zeros_like(a[..., 0]), np.full_like(a[..., 0], 255)])
        if fmt == 10:
            a = np.frombuffer(b, np.float16, n * 4, 148).reshape(h, w, 4).astype(np.float32)
            return (np.clip(a, 0, 1) * 255).astype(np.uint8)
        raise


class Repo:
    """one WolvenKit export: its textures (as linear RGBA float, SIZE px) and JSON resources, read once"""
    def __init__(self, out, repo):
        self.out, self.repo, self.cache = out, repo, {}

    def json(self, depot):
        for base in (self.repo, self.out):
            p = os.path.join(base, depot + '.json')
            if os.path.exists(p): return json.load(open(p, encoding='utf-8-sig'))['Data']['RootChunk']

    def tex(self, depot, size=SIZE):
        """a texture (.xbm depot path, or a file of the export) -> linear RGB + alpha, size x size; None: not there"""
        k = (depot, size)
        if k not in self.cache:
            p = depot if os.path.isabs(depot) else os.path.join(self.repo, depot[:-4] + '.dds')
            if not os.path.exists(p) and not os.path.isabs(depot): p = os.path.join(self.out, depot[:-4] + '.dds')
            try:
                im = Image.fromarray(dds(p)).resize((size, size), Image.BILINEAR)
                a = np.asarray(im, np.float32) / 255
                self.cache[k] = np.dstack([srgb_to_lin(a[..., :3]), a[..., 3]])
            except Exception:
                self.cache[k] = None
        return self.cache[k]


def srgb_to_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin_to_srgb(c): c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
def colour(c):
    """a material's colour -> linear RGB (a Color: sRGB bytes; a Vector4: linear already)"""
    if 'Red' in c: return srgb_to_lin(np.array([c['Red'], c['Green'], c['Blue']], np.float32) / 255)
    return np.array([c.get('X', 1), c.get('Y', 1), c.get('Z', 1)], np.float32)
def path(v): return v if isinstance(v, str) else (v or {}).get('DepotPath', {}).get('$value', '') if isinstance(v, dict) else ''
def name(v): return v.get('$value') if isinstance(v, dict) else v


def lit(c):
    """an emissive colour (linear) at full brightness, its hue kept: Workbench draws no glow"""
    h, l, sat = colorsys.rgb_to_hls(*[float(x) for x in lin_to_srgb(c)])
    r = np.array(colorsys.hls_to_rgb(h, max(l, 0.55), sat), np.float32)
    return srgb_to_lin(r / max(float(r.max()), 1e-3))


def flat(c, a=1.0):
    return np.dstack([np.broadcast_to(np.asarray(c, np.float32), (SIZE, SIZE, 3)), np.full((SIZE, SIZE), a, np.float32)])


def multilayer(R, d):
    """the mlsetup's layers over each other by the mlmask's masks (layer i: mask i; layer 0 everywhere)"""
    mask, sp = path(d.get('MultilayerMask'))[:-7], path(d.get('MultilayerSetup'))
    if sp.startswith('engine\\'):                          # (the engine's default: an mlsetup WolvenKit didn't resolve -
        stem = os.path.basename(mask).replace('_masksset', '')   # the mask's folder's whose name begins the mask's, else none)
        near = [f[len(R.repo) + 1:-5] for f in glob.glob(os.path.join(R.repo, os.path.dirname(mask), '*.mlsetup.json'))
                if stem.startswith(os.path.basename(f)[:-13])]
        sp = max(near, key=len) if near else None
    setup = sp and R.json(sp)
    if not setup: return None
    out = np.zeros((SIZE, SIZE, 3), np.float32)
    for i, L in enumerate(setup.get('layers', [])):
        tpl = R.json(path(L.get('material'))) or {}
        tint = next((o['v']['Elements'] for o in (tpl.get('overrides') or {}).get('colorScale', [])
                     if name(o['n']) == name(L.get('colorScale'))), [1.0, 1.0, 1.0])
        tile = max(float(L.get('matTile') or 1), 1e-3)
        s = int(min(SIZE, max(4, round(SIZE / tile))))
        col = R.tex(path(tpl.get('colorTexture')), s)
        col = np.full((s, s, 3), 0.5, np.float32) if col is None else col[..., :3]
        col = np.tile(col, (math.ceil(SIZE / s), math.ceil(SIZE / s), 1))[:SIZE, :SIZE] * np.asarray(tint, np.float32)
        if i == 0:
            out[:] = col; continue
        m = R.tex(os.path.join(R.repo, mask + '_layers', os.path.basename(mask) + '_%d.dds' % i))
        if m is None: continue
        m = lin_to_srgb(m[..., :1]) * float(L.get('opacity', 1))   # (read as colour: back to the mask's own values)
        out = out * (1 - m) + col * m
    return np.dstack([out, np.ones((SIZE, SIZE), np.float32)])


def first(d, *keys):
    for k in keys:
        p = path(d.get(k))
        if p and not re.search(r'editor\\(black|normal)|alpha_empty|default\\black', p): return p


def gradient(R, d, im):
    """a gradient-mapped texture (GradientMap: its grey picks the colour along the map), else as it is"""
    g = first(d, 'GradientMap')
    gm = R.tex(g, 256) if g and im is not None else None
    if gm is None: return im
    i = (lin_to_srgb(im[..., 0]) * 255).astype(int)
    return np.dstack([gm[128, :, :3][i], im[..., 3]])


def bake(R, m):
    """one material -> [linear RGBA image, alpha threshold or None], or None (grey: nothing to go by)"""
    mt, d = (m.get('MaterialTemplate') or m.get('BaseMaterial') or '').lower(), m.get('Data') or {}
    base = os.path.basename(mt)
    aref = float(d.get('AlphaThreshold') or 0.5) if m.get('EnableMask') or 'speedtree' in base else None
    if 'multilayered' in base: return [multilayer(R, d), None]
    if base.startswith('hair'):                             # hair cards: the profile's colour along the strand ids, cut
        hp = R.json(path(d.get('HairProfile'))) or {}       # by the strands' alpha
        es = sorted((e['value'], colour(e['color'])) for e in hp.get('gradientEntriesID') or [])
        g, a = R.tex(first(d, 'Strand_Gradient') or ''), R.tex(first(d, 'Strand_Alpha') or '')
        if not es or a is None: return [flat([0, 0, 0], 0), 0.5]
        v = lin_to_srgb(g[..., 1]) if g is not None else np.full((SIZE, SIZE), 0.5, np.float32)
        col = np.dstack([np.interp(v, [e[0] for e in es], [e[1][k] for e in es]) for k in range(3)])
        return [np.dstack([col, lin_to_srgb(a[..., 0])]), 0.25]
    if re.search(r'mesh_decal_(gradientmap_recolor|double_diffuse)', base) and re.search(r'cap|brow|beard', (m.get('BaseMaterial') or '') + m['Name'], re.I):
        t = R.tex(first(d, 'DiffuseTexture') or '')         # the scalp's hair, brows, stubble: painted on, cut by its alpha
        if t is None: return [flat([0, 0, 0], 0), 0.5]
        im = gradient(R, d, t) if 'gradientmap' in base else np.dstack([flat(colour(d['DiffuseColor']))[..., :3], t[..., 3]])
        mk = R.tex(first(d, 'MaskTexture') or '')
        return [np.dstack([im[..., :3], t[..., 3] * (lin_to_srgb(mk[..., 0]) if mk is not None else 1)]), 0.3]
    if 'hologram' in base:                                  # a hologram sign: its picture, else its colour, lit
        t = R.tex(first(d, 'Diffuse') or '')
        if t is not None and t[..., :3].max() > 0.02: return [np.dstack([t[..., :3] / float(t[..., :3].max()), t[..., 3]]), None]
        return [flat(lit(colour(d['SurfaceColor'])) if 'SurfaceColor' in d else np.ones(3)), None]
    if 'glass' in base:                                     # glass: see-through, in its tint (a bottle, a tank: else nothing to see)
        c = colour(d['TintColor']) if 'TintColor' in d else np.ones(3, np.float32)
        return [flat(0.5 + 0.5 * c), None, 0.5]
    if re.search(r'decal|window|invisible|fx_|particle|volumetric|blackwall|eye_shadow|eye_gradient', mt) or             path(d.get('BaseColor')).endswith('alpha_empty.xbm'):
        return [flat([0, 0, 0], 0), 0.5]
    if re.search(r'signages|neon_tubes|device_diode|lights_interactive', base):   # neon, diodes: their colour, lit
        c = next((colour(d[k]) for k in ('ColorOneStart', 'color', 'Color', 'EmissiveColor', 'EmissiveColor1') if k in d), np.ones(3))
        return [flat(lit(c)), None]
    if re.search(r'screen|_ui\.|billboard|television|neon_parallax', base) and 'speedtree' not in base:
        t = first(d, 'ParalaxTexture', 'AdTexture', 'MainTexture', 'DiffuseTexture', 'BaseColor')
        im = gradient(R, d, R.tex(t) if t else None)         # a screen or a lit sign: its picture, lit
        if im is not None: return [np.dstack([im[..., :3] / max(float(im[..., :3].max()), 1e-3), im[..., 3]]), aref]
        return [flat(lit(colour(d['Color'])) if 'Color' in d else srgb_to_lin(np.full(3, 0.12))), None]
    t = first(d, 'BaseColor', 'DiffuseTexture', 'DiffuseMap', 'Diffuse', 'Albedo', 'ColorTexture', 'MainTexture')
    im = gradient(R, d, R.tex(t) if t else None)
    tint = np.ones(3, np.float32)
    for k in ('BaseColorScale', 'DiffuseColor'):
        if k in d: tint = tint * colour(d[k])
    if im is None:
        if 'TintColor' in d: tint = tint * colour(d['TintColor'])   # (a plain layer: its tint is all there is)
        elif 'DiffuseColor' not in d and 'BaseColorScale' not in d: return None
        im = flat(tint)
    else:
        im = np.dstack([im[..., :3] * tint, im[..., 3]])
    e, ec = first(d, 'Emissive'), d.get('EmissiveColor')
    if e and ec and float(d.get('EmissiveEV', 1)) > 0 and colour(ec).max() > 0.01:   # lit where its Emissive is
        em = R.tex(e)
        w = (em[..., :3].max(2) if em is not None else np.ones(im.shape[:2]))[..., None]
        im = np.dstack([im[..., :3] * (1 - w) + lit(colour(ec)) * w, im[..., 3]])
    return [im, aref]


def mesh(R, depot, app):
    """one mesh's appearance -> {submesh_NN: [png, alpha threshold]}"""
    mj = os.path.join(R.out, depot[:-5] + '.Material.json')
    if not os.path.exists(mj): return {}
    doc = json.load(open(mj, encoding='utf-8-sig'))
    mats = {m['Name']: m for m in doc.get('Materials', [])}
    apps = list(doc.get('Appearances', {}).items())
    chunks = next((v for i, (k, v) in enumerate(apps) if app and k == app + str(i)), apps[0][1] if apps else [])
    out, done = {}, {}
    folder = os.path.join(TEX, depot[:-5])
    for i, mn in enumerate(chunks):
        if mn not in done:
            done[mn] = None
            r = bake(R, mats[mn]) if mn in mats else None
            if r and r[0] is not None:
                os.makedirs(folder, exist_ok=True)
                png = os.path.join(folder, re.sub(r'[^\w.-]', '_', mn)[:80] + '.png')
                a = r[0]
                Image.fromarray((np.dstack([lin_to_srgb(a[..., :3]), np.clip(a[..., 3], 0, 1)]) * 255).round().astype(np.uint8), 'RGBA').save(png)
                done[mn] = [png, *r[1:]]                    # (colour, alpha threshold or None(, how see-through))
        if done[mn]: out['submesh_%02d' % i] = done[mn]
    return out


# --- the export -----------------------------------------------------------------------------------------------------
def batch(job):
    """one WolvenKit uncook of a batch of meshes (with materials), baked -> {glb: {submesh: [png, aref]}}"""
    n, todo, keep = job
    budget.gentle()
    raw = os.path.join(NC, 'raw_%d' % n)
    shutil.rmtree(raw, ignore_errors=True)
    out, repo = os.path.join(raw, 'out'), os.path.join(raw, 'repo')
    os.makedirs(repo)
    arch = os.path.join(paths.get('cp2077'), 'archive', 'pc')
    rx = '^(' + '|'.join(re.escape(d) for _, d, _ in todo) + ')$'
    subprocess.run([paths.get('wolvenkit'), 'uncook', os.path.join(arch, 'content'), os.path.join(arch, 'ep1'), '-r', rx,
                    '-o', out, '--mesh-export-material-repo', repo, '--gamepath', paths.get('cp2077'), '--uext', 'dds',
                    '--mesh-export-lod-filter', '-v', 'Minimal'], env=paths.wk_env(), capture_output=True)
    R = Repo(out, repo)
    res = {}
    for g, depot, app in todo:
        try: res[g] = mesh(R, depot, app)
        except Exception as e: print('  failed', depot, e, flush=True); res[g] = {}
        src = os.path.join(out, depot[:-5] + '.glb')
        if not os.path.exists(g) and os.path.exists(src):   # (not the harvest's: the export's own mesh kept)
            os.makedirs(os.path.dirname(g), exist_ok=True)
            first = next((h for h, d, _ in todo if d == depot and h != g and os.path.exists(h)), None)
            os.link(first, g) if first else shutil.copy(src, g)
    if not keep: shutil.rmtree(raw, ignore_errors=True)
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    have = json.load(open(MATS)) if os.path.exists(MATS) else {}
    every = items()
    todo = [[g, d, a] for g, (d, a, k) in every.items() if (not args or k in args) and ('--all' in sys.argv or g not in have)]
    print(len(todo), 'meshes to texture', flush=True)
    jobs = [(n, todo[i:i + BATCH], '--keep' in sys.argv) for n, i in enumerate(range(0, len(todo), BATCH))]
    with Pool(budget.workers(2.5, 4)) as pool:
        for k, res in enumerate(pool.imap_unordered(batch, jobs)):
            have.update(res)
            os.makedirs(NC, exist_ok=True)
            json.dump(have, open(MATS, 'w'), indent=0)       # (saved as it goes: a stopped run resumes)
            print('batch', k + 1, len(jobs), flush=True)
    print(len(have), 'meshes,', sum(len(v) for v in have.values()), 'submeshes textured')


if __name__ == '__main__':
    main()
