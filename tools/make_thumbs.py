"""Menu thumbnails (dev time: Blender, the pieces' own textures). Every item in <work>/thumb_items.json
(build_catalog.py writes it when run here, with the meshes) rendered in Blender - a 3/4 view, textured, transparent
background - and packed into atlases of 16 x 16 cells of CELL px (2048 x 2048), shipped with the mod (the importer's
data: the player renders nothing). <work> is paths.work() (ours: source/); Blender is paths.get('blender'). Renders
are cached in <work>/thumbs_raw by key (delete one, or --all, to render again). Writes:
  <work>/raw/homestead/ui/thumbs_<n>.png          the atlases (premultiplied alpha, as the game's UI wants)
  <work>/json/homestead/ui/thumbs_<n>.xbm         the same as game textures (fo4/xbm.py ui_atlas: BC3)
  <work>/json/homestead/ui/thumbs_<n>.inkatlas.json   one part per item (tools/import.py mod_archive packs the folder)
  <work>/thumbs.json                              {atlas: {key: [left, top, right, bottom] in UV}} (build_catalog: `thumb`)
  r6/scripts/Homestead/HomesteadAtlas.reds        atlas name -> path (redscript can't build a ResRef from a string)
usage: python tools/make_thumbs.py [--all] [--pack] [key ...]   (--pack: no rendering, the cached renders packed;
keys: those rendered again)
"""
import copy, glob, io, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fo4'))
import paths

ROOT, W = paths.ROOT, paths.work()
RENDER, CELL, COLS, PROCS = 256, 128, 16, 8                  # rendered at 256, packed at 128 (sharper): 256 an atlas
TMP = os.path.join(W, 'thumbs_raw')
TEX = os.path.join(W, 'thumbs_tex')
PNGS = os.path.join(W, 'raw', 'homestead', 'ui')
GAME = os.path.join(W, 'json', 'homestead', 'ui')
NC = os.path.join(W, 'thumbs_nc', 'materials.json')


def textures(items):
    """Fallout's colour textures the items' materials use, each as a 512 px PNG in source/thumbs_tex (cached):
    -> {glb: {material: [png, alpha threshold or None]}}"""
    need = {}
    for key, parts, mats, _ in items:
        for g, ms in (mats or {}).items():
            for name, (tex, *_) in ms.items():
                if tex: need[tex] = os.path.join(TEX, tex.replace('\\', '_').replace('/', '_')[:150] + '.png')
    todo = [t for t, f in need.items() if not os.path.exists(f)]
    if todo:
        import convert
        files = convert.Files()
        os.makedirs(TEX, exist_ok=True)
        for t in todo:
            base, tint = t.split('__tint__')[0].split('__pal__')[0], t.split('__tint__')[1:]   # (a palette texture: its
            try:                                             # greyscale base, near enough; a tinted one: times its tint)
                im = Image.open(io.BytesIO(files.read('textures\\' + base + '.dds'))).convert('RGBA')
                im.thumbnail((512, 512))
                if tint: im = Image.merge('RGBA', [c.point(lambda v, k=int(k, 16) / 255: v * k) for c, k in zip(im.split(), tint[0].split('_') + ['ff'])])
                im.save(need[t])
            except Exception:
                pass                                         # (unreadable: that material renders grey)
    out = {}
    for key, parts, mats, _ in items:
        for g, ms in (mats or {}).items():
            out[g] = {name: [need.get(tex), *rest] for name, (tex, *rest) in ms.items() if not tex or os.path.exists(need[tex])}
    return out


def render(job):
    i, jobs = job
    lst = os.path.join(TMP, 'jobs_%d.json' % i)
    json.dump(jobs, open(lst, 'w'))
    subprocess.run([paths.get('blender'), '-b', '-P', os.path.join(os.path.dirname(__file__), 'thumbs_blender.py'), '--', lst, str(RENDER)],
                   capture_output=True)
    os.remove(lst)


def premultiplied(img):                                      # the cell: the render shrunk, alpha premultiplied
    img = img.convert('RGBA').resize((CELL, CELL), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    pre = a[..., :3] * a[..., 3:4]
    return Image.fromarray((np.dstack([pre, a[..., 3:4]]) * 255).round().astype(np.uint8), 'RGBA')


def pack(items):
    os.makedirs(PNGS, exist_ok=True); os.makedirs(GAME, exist_ok=True)
    for old in glob.glob(os.path.join(PNGS, 'thumbs*.png')) + glob.glob(os.path.join(GAME, 'thumbs*')): os.remove(old)
    px, per = COLS * CELL, COLS * COLS
    parts, missing = {}, []
    keys = [it[0] for it in items]
    for n in range(0, len(keys), per):
        name = str(n // per)
        atlas = Image.new('RGBA', (px, px), (0, 0, 0, 0))
        p = {}
        for j, k in enumerate(keys[n:n + per]):
            x, y = (j % COLS) * CELL, (j // COLS) * CELL
            src = os.path.join(TMP, k + '.png')
            if os.path.exists(src): atlas.paste(premultiplied(Image.open(src)), (x, y))
            else: missing.append(k); continue
            p[k] = [x / px, y / px, (x + CELL) / px, (y + CELL) / px]
        atlas.save(os.path.join(PNGS, 'thumbs_%s.png' % name))
        parts[name] = p
    json.dump(parts, open(os.path.join(W, 'thumbs.json'), 'w'), indent=0)
    # game textures and atlases
    import xbm
    tpl = json.load(open(os.path.join(ROOT, 'source', 'tpl', 'item_icons4.inkatlas.json'), encoding='utf-8-sig'))   # (ours, in the repo)
    for name, p in parts.items():
        xbm.ui_atlas(os.path.join(PNGS, 'thumbs_%s.png' % name), os.path.join(GAME, 'thumbs_%s.xbm' % name))
        doc = copy.deepcopy(tpl)
        mappers = [{'$type': 'inkTextureAtlasMapper',
                    'clippingRectInPixels': {'$type': 'Rect', 'bottom': 0, 'left': 0, 'right': 0, 'top': 0},
                    'clippingRectInUVCoords': {'$type': 'RectF', 'Bottom': b, 'Left': l, 'Right': r, 'Top': t},
                    'partName': {'$type': 'CName', '$storage': 'string', '$value': k}}
                   for k, (l, t, r, b) in p.items()]
        tex = {'$type': 'ResourcePath', '$storage': 'string', '$value': 'homestead\\ui\\thumbs_%s.xbm' % name}
        for slot in doc['Data']['RootChunk']['slots']['Elements']:
            slot['texture']['DepotPath'] = tex
            slot['parts'] = mappers
            slot['slices'] = []
        json.dump(doc, open(os.path.join(GAME, 'thumbs_%s.inkatlas.json' % name), 'w', encoding='utf-8'), indent=1)
    reds(list(parts))
    print(len(parts), 'atlases,', sum(len(p) for p in parts.values()), 'thumbs, missing', len(missing), missing[:10])


def reds(names):
    path = lambda n: 'r"homestead\\\\ui\\\\thumbs_%s.inkatlas"' % n
    cases = ''.join('        if Equals(name, "%s") { return %s; }\n' % (n, path(n)) for n in names)
    open(os.path.join(ROOT, 'r6', 'scripts', 'Homestead', 'HomesteadAtlas.reds'), 'w', newline='\r\n').write(
        '// Generated by tools/make_thumbs.py: menu thumbnail atlas name -> path.\n'
        'public abstract class HomesteadAtlas {\n'
        '    public static func Path(name: String) -> ResRef {\n' + cases +
        '        return %s;\n' % path(names[0] if names else '0') +
        '    }\n'
        '}\n')


def main():
    items = json.load(open(os.path.join(W, 'thumb_items.json')))   # [[key, parts, {glb: {material: [tex, aref(, opacity)]}}, view], ...]
    if '--pack' not in sys.argv:
        os.makedirs(TMP, exist_ok=True)
        tex = textures(items)
        if os.path.exists(NC):                               # Night City's (tools/nc_textures.py), by submesh
            tex.update({g: m for g, m in json.load(open(NC)).items() if m and not tex.get(g)})
        todo = [[parts, os.path.join(TMP, k + '.png'), {g: tex[g] for g in {q[0] for q in parts} if g in tex}, view]
                for k, parts, _, view in items if '--all' in sys.argv or k in sys.argv or not os.path.exists(os.path.join(TMP, k + '.png'))]
        print(len(todo), 'to render', flush=True)
        chunks = [todo[i::PROCS * 4] for i in range(PROCS * 4) if todo[i::PROCS * 4]]
        with ThreadPoolExecutor(PROCS) as ex:
            for n, _ in enumerate(ex.map(render, enumerate(chunks))):
                print('chunk', n + 1, len(chunks), flush=True)
    pack(items)


if __name__ == '__main__':
    main()
