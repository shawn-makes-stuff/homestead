"""Fallout 4 workshop pieces -> Cyberpunk: step 2, the game files (after tools/fo4/convert.py). WolvenKit imports the
textures (.png -> .xbm, one texture kind per run), pours each model's .glb into a copy of a plain Cyberpunk mesh
(WolvenKit only imports geometry into an existing .mesh), rewrites its materials as metal_base instances on our
textures, and packs <work>/fo4/Homestead_FO4.archive. What is already built (newer than its source) is kept; all of
it when the game has the archive this made from the same inputs (installed.json, manifest(): a re-import with the
working files tidied away needn't remake 9 GB). Every WolvenKit run is checked (paths.wk): a run that made nothing stops
the import with what went wrong; a mesh or texture that didn't make it is left out and tried again next time.
  python tools/fo4/build.py
"""
import filecmp, hashlib, json, os, re, shutil, sys
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (tools/: paths.py)
import budget, paths
from convert import RAW, DEPOT, FO4

ARC = os.path.join(FO4, 'archive')                          # the files to pack, at their depot paths
FORCE = '--force' in sys.argv or 'build' in os.environ.get('HOMESTEAD_FORCE', '')   # every material made again
TEMPLATE_DEPOT = r'base\environment\architecture\common\int\int_common_a\int_common_a_floor_l300_a.mesh'   # a plain
TEMPLATE = os.path.join(FO4, 'template', 'int_common_a_floor_l300_a.mesh')                         # static mesh (local
                                                                                                    # materials, no rig)


def template():                                             # the player's own Cyberpunk's: unpacked once, kept
    if not os.path.exists(TEMPLATE):
        tmp = os.path.join(FO4, 'template')
        got = os.path.join(tmp, TEMPLATE_DEPOT)
        paths.wk(['unbundle', '-p', paths.cp_content(), '-o', tmp, '-r', '^' + re.escape(TEMPLATE_DEPOT).replace(re.escape('\\'), '.') + '$'],
                 expect=[got], what="unpack the mesh template from Cyberpunk's files (%s)" % TEMPLATE_DEPOT)
        shutil.move(got, TEMPLATE)
    return TEMPLATE
# texture kind -> (group, gamma, block compression); WolvenKit's default is none (raw RGBA: ~4x the memory, 8x slower)
KINDS = {'normal': ('TEXG_Generic_Normal', 'false', 'TCM_Normalmap'),
         'rough': ('TEXG_Generic_Grayscale', 'false', 'TCM_QualityR'),
         'color': ('TEXG_Generic_Color', 'true', 'TCM_DXTNoAlpha'),
         'alpha': ('TEXG_Generic_Color', 'true', 'TCM_DXTAlpha')}          # colour with an alpha channel


def kind(path):
    return 'normal' if path.endswith('_n.png') else 'rough' if re.search(r'_r\d*\.png$', path) else         'alpha' if 'A' in (im := Image.open(path)).getbands() and im.getchannel('A').getextrema()[0] < 255 else 'color'     # (all colour PNGs are RGBA)


def cname(v): return {'$type': 'CName', '$storage': 'string', '$value': v}
def tex(name): return {'DepotPath': {'$type': 'ResourcePath', '$storage': 'string', '$value': DEPOT + '\\tex\\' + name + '.xbm'}, 'Flags': 'Default'}


def material(m):
    if m.get('glass'):                                      # Fallout's glass (convert.py): Cyberpunk's own, nearly clear
        t = m.get('tint') or [1, 1, 1]
        c = [max(0, min(255, int(round(v * 255)))) for v in t]
        vals = [{'$type': 'Color', 'TintColor': {'$type': 'Color', 'Red': c[0], 'Green': c[1], 'Blue': c[2], 'Alpha': 255}},
                {'$type': 'Float', 'Opacity': 0.15}, {'$type': 'Float', 'Roughness': 0.05}, {'$type': 'Float', 'IOR': 1.5}]
        return {'$type': 'CMaterialInstance', 'audioTag': cname('None'),
                'baseMaterial': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'string', '$value': 'base\\materials\\glass.mt'}, 'Flags': 'Default'},
                'cookingPlatform': 'PLATFORM_None', 'enableMask': 0, 'metadata': None, 'resourceVersion': 4, 'values': vals}
    vals = [{'$type': 'rRef:ITexture', 'BaseColor': tex(m['color'])}]
    if m['normal']: vals.append({'$type': 'rRef:ITexture', 'Normal': tex(m['normal'])})
    if m['rough']: vals.append({'$type': 'rRef:ITexture', 'Roughness': tex(m['rough'])})
    if m['alpha_test']: vals.append({'$type': 'Float', 'AlphaThreshold': round(m['alpha_ref'] / 255, 3)})   # Fallout's own cut-off
    if m.get('tint'): vals.append({'$type': 'Vector4', 'BaseColorScale': {'$type': 'Vector4', 'X': m['tint'][0], 'Y': m['tint'][1], 'Z': m['tint'][2], 'W': 1}})
    if m.get('emissive'):                                   # lit: glow maps, neon tubes, lit signs (always on: no power)
        c = [max(0, min(255, int(round(v * 255)))) for v in m['emissive_color']]
        vals += [{'$type': 'rRef:ITexture', 'Emissive': tex(m['emissive'])},
                 {'$type': 'Color', 'EmissiveColor': {'$type': 'Color', 'Red': c[0], 'Green': c[1], 'Blue': c[2], 'Alpha': 255}},
                 {'$type': 'Float', 'EmissiveEV': m['emissive_ev']}]
    return {'$type': 'CMaterialInstance', 'audioTag': cname('None'),
            'baseMaterial': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'string', '$value': 'engine\\materials\\metal_base.remt'}, 'Flags': 'Default'},
            'cookingPlatform': 'PLATFORM_None', 'enableMask': 1 if m['alpha_test'] else 0, 'metadata': None, 'resourceVersion': 4, 'values': vals}


def split(items, n):                                         # n near-equal parts (one WolvenKit run each; a run works
    n = max(1, min(n, len(items)))                           # one core: four of them, four cores)
    return [items[i::n] for i in range(n)]


def stale(src, dst): return not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src)


def installed():
    """the game has the archive this import last packed (tools/import.py moved it there: installed.json, its size)"""
    try:
        size = json.load(open(os.path.join(FO4, 'installed.json')))['size']
        return os.path.getsize(os.path.join(paths.get('cp2077'), 'archive', 'pc', 'mod', 'Homestead_FO4.archive')) == size
    except (OSError, KeyError, ValueError): return False


def meshes(pieces):
    """mesh -> its model, part or glow (one mesh per model: objects can share one); an animated one's moving parts and
    a lamp's glowing shapes (switched with it) are meshes of their own"""
    models = {p['mesh']: p for p in pieces if p.get('mesh')}
    for p in pieces:
        for part in p.get('parts', []): models[part['mesh']] = part
        if p.get('glow'): models[p['glow']['mesh']] = p['glow']
    return models


def manifest(pieces):
    """what the packed archive is made of: each mesh's .glb (size, time) and materials, and Fallout's archives (an HD
    pack added changes the textures) -> a hash, kept in installed.json by tools/import.py"""
    h = hashlib.sha1()
    for mesh, p in sorted(meshes(pieces).items()):
        st = os.stat(p['glb'])
        h.update(json.dumps([mesh, st.st_size, st.st_mtime_ns, p['materials']], sort_keys=True).encode())
    data = paths.get('fo4')
    for f in sorted(os.listdir(data)):
        if f.lower().endswith('.ba2'): h.update(('%s %d' % (f, os.path.getsize(os.path.join(data, f)))).encode())
    return h.hexdigest()


def unchanged(pieces):
    """the game has the archive packed from these same inputs, nothing waiting to be installed and no code change
    (xbm, build) or --force: textures, meshes, materials and the pack are all skipped"""
    if FORCE or 'xbm' in os.environ.get('HOMESTEAD_FORCE', '') or os.path.exists(os.path.join(FO4, 'Homestead_FO4.archive')): return False
    try: return installed() and json.load(open(os.path.join(FO4, 'installed.json')))['inputs'] == manifest(pieces)
    except (OSError, KeyError, ValueError): return False


def main():
    budget.gentle()
    pieces = json.load(open(os.path.join(FO4, 'pieces.json')))
    if unchanged(pieces):
        print('archive kept: the game has it, made from these same models and textures'); return
    models = meshes(pieces)
    PAR = budget.workers(2.0, 4)                             # WolvenKit runs at once (~2 GB each): what this PC holds
    traw = os.path.join(RAW, DEPOT, 'tex')
    # textures, one kind per WolvenKit run (its import settings come from the environment); new or changed only
    pngs = [os.path.relpath(os.path.join(d, f), traw) for d, _, fs in os.walk(traw) for f in fs if f.endswith('.png')]
    # (one WolvenKit run uses one core, ~12 s a texture: the work is split over PAR runs at once, ~2 GB each)
    jobs = []
    xbm = lambda r: os.path.join(ARC, DEPOT, 'tex', r[:-4] + '.xbm')
    kinds = {r: kind(os.path.join(traw, r)) for r in pngs if stale(os.path.join(traw, r), xbm(r))}
    for r in kinds:                                          # (an old one gone first: what's there after was made now)
        if os.path.exists(xbm(r)): os.remove(xbm(r))
    for k, (group, gamma, comp) in KINDS.items():
        todo = [r for r in kinds if kinds[r] == k]
        for i in range(PAR):
            src = os.path.join(FO4, 'tex_%s%d' % (k, i))
            shutil.rmtree(src, ignore_errors=True)
            part = todo[i::PAR]
            for r in part:
                os.makedirs(os.path.join(src, DEPOT, 'tex', os.path.dirname(r)), exist_ok=True)
                shutil.copy(os.path.join(traw, r), os.path.join(src, DEPOT, 'tex', r))
            if part: jobs.append((k, part, src, group, gamma, comp))
    os.makedirs(os.path.join(ARC, DEPOT, 'tex'), exist_ok=True)
    def texjob(j):
        k, part, src, group, gamma, comp = j
        paths.wk(['import', src, '-o', ARC], expect=[xbm(r) for r in part], partial=True, what='import %d %s textures' % (len(part), k),
                 XbmImportArgs__TextureGroup=group, XbmImportArgs__IsGamma=gamma, XbmImportArgs__Compression=comp)
        shutil.rmtree(src, ignore_errors=True)
        miss = [r for r in part if not os.path.exists(xbm(r))]   # (left out: tried again next run)
        print(k, len(part) - len(miss), 'of', len(part), 'imported', miss[:3], flush=True)
    paths.progress('png')
    with ThreadPoolExecutor(PAR) as ex: list(ex.map(texjob, jobs))
    # meshes: the template copied under each model's name, then its .glb imported into it; new or changed only
    # (split over PAR runs at once: one run imports one mesh at a time - 3,000 of them took two minutes on one core)
    gsrc = os.path.join(FO4, 'glb')
    shutil.rmtree(gsrc, ignore_errors=True)
    todo = []
    for mesh, p in models.items():
        dst = os.path.join(ARC, mesh)
        if not stale(p['glb'], dst): continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(template(), dst); os.utime(dst, (0, 0))  # (not yet the model: a run stopped here finds it stale)
        todo.append(mesh)
    paths.progress('meshes')
    if todo:
        parts = split(todo, PAR)
        for i, part in enumerate(parts):
            for mesh in part:
                g = os.path.join(gsrc, str(i), mesh[:-5] + '.glb')   # (the run's root: the depot path under it)
                os.makedirs(os.path.dirname(g), exist_ok=True)
                shutil.copy(models[mesh]['glb'], g)
        def meshjob(i): return paths.wk(['import', os.path.join(gsrc, str(i)), '-k', '-o', ARC], what='import meshes',
                                        GltfImportArgs__ImportMaterials='false')
        with ThreadPoolExecutor(PAR) as ex: logs = list(ex.map(meshjob, range(len(parts))))
        same = [m for m in todo if filecmp.cmp(TEMPLATE, os.path.join(ARC, m), shallow=False)]   # (still the template:
        for m in same: os.remove(os.path.join(ARC, m))       # not imported - left out, tried again next run)
        if len(same) == len(todo):
            raise SystemExit('WolvenKit could not import any of the %d meshes; it said: %s' % (len(todo), paths.said(logs[0])))
        print('meshes', len(todo) - len(same), 'of', len(todo), 'in', len(parts), 'runs', same[:3], flush=True)
    # materials: one appearance, a local metal_base instance per submesh. In batches (a WolvenKit start costs
    # seconds; a run works one core, so PAR of them at once): the meshes moved to work folders, a run each to JSON,
    # edited here, a run each back; done ones remembered
    paths.progress('materials')
    stamp_path = os.path.join(FO4, 'materials_done.json')
    stamp = json.load(open(stamp_path)) if os.path.exists(stamp_path) else {}
    mtodo = [m for m in models if os.path.exists(os.path.join(ARC, m)) and (FORCE or m in todo or stamp.get(m) != os.path.getmtime(models[m]['glb']))]
    work = os.path.join(FO4, 'mat_work')
    shutil.rmtree(work, ignore_errors=True)
    wparts, wdir = split(mtodo, PAR), {}
    for i, part in enumerate(wparts):
        for mesh in part:
            wdir[mesh] = os.path.join(work, str(i))
            os.makedirs(os.path.dirname(os.path.join(wdir[mesh], mesh)), exist_ok=True)
            shutil.move(os.path.join(ARC, mesh), os.path.join(wdir[mesh], mesh))
    def convert_all(mode):                                   # (s: each mesh's .json made; d: the mesh made back from it)
        def one(i): paths.wk(['convert', mode, os.path.join(work, str(i))], partial=True, what="rewrite the meshes' materials",
                             expect=[os.path.join(work, str(i), m) + ('.json' if mode == 's' else '') for m in wparts[i]])
        with ThreadPoolExecutor(PAR) as ex: list(ex.map(one, range(len(wparts))))
    if mtodo: convert_all('s')
    def mats(mesh):
        mp = os.path.join(wdir[mesh], mesh)
        if not os.path.exists(mp + '.json'): return mesh, 'no json'
        j = json.load(open(mp + '.json'))
        rc = j['Data']['RootChunk']
        ms = models[mesh]['materials']
        names = [m['name'] for m in ms]
        rc['materialEntries'] = [{'$type': 'CMeshMaterialEntry', 'index': i, 'isLocalInstance': 1, 'name': cname(n)} for i, n in enumerate(names)]
        rc['localMaterialBuffer']['materials'] = [material(m) for m in ms]
        rc['externalMaterials'], rc['preloadExternalMaterials'], rc['preloadLocalMaterialInstances'] = [], [], []
        a = rc['appearances'][0]
        a['Data']['chunkMaterials'] = [cname(n) for n in names]
        a['Data']['name'] = cname('default')
        rc['appearances'] = [a]
        json.dump(j, open(mp + '.json', 'w'))
        os.remove(mp)
        return mesh, 'ok'
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(mats, mtodo))
    if mtodo: convert_all('d')
    bad = []
    for mesh, r in res:
        mp = os.path.join(wdir[mesh], mesh)
        if r == 'ok' and not os.path.exists(mp): r = 'not written back'
        if r != 'ok':                                       # (left as it was; a missing one is re-imported next run)
            bad.append((mesh, r))
            if os.path.exists(mp): shutil.move(mp, os.path.join(ARC, mesh))
            continue
        os.remove(mp + '.json')
        shutil.move(mp, os.path.join(ARC, mesh))
        stamp[mesh] = os.path.getmtime(models[mesh]['glb'])
    json.dump(stamp, open(stamp_path, 'w'))
    print('materials', len(res) - len(bad), 'ok,', len(bad), 'failed', bad[:3], flush=True)
    # the archive (as it was if nothing in it changed: here, or already moved into the game - installed.json)
    final, dirty = os.path.join(FO4, 'Homestead_FO4.archive'), os.path.join(FO4, 'pack.todo')
    if jobs or todo or mtodo: open(dirty, 'w').close()      # (till it is packed: a run that dies packing packs next time)
    if not os.path.exists(dirty) and (os.path.exists(final) or installed()):
        print('archive kept (nothing in it changed)'); return
    paths.progress('pack')
    out = os.path.join(FO4, 'packed')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    print(paths.said(paths.wk(['pack', ARC, '-o', out], expect=[os.path.join(out, '*.archive')], what="pack Fallout 4's pieces")))
    for f in os.listdir(out):
        if f.endswith('.archive'): shutil.move(os.path.join(out, f), os.path.join(FO4, 'Homestead_FO4.archive'))
    if os.path.exists(dirty): os.remove(dirty)
    print('->', os.path.join(FO4, 'Homestead_FO4.archive'))


if __name__ == '__main__':
    main()
