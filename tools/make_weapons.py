"""Every weapon in the game, placeable as a prop: one each, in its first look. A weapon is put together by the game from its .app (the receiver,
sights, magazine and decals of each look: default, neon, iconic...), listed in the weapons' appearance factory
(base\\gameplay\\factories\\items\\weapons\\weapons_appearances.csv; Phantom Liberty's own if installed). One entity
template of ours, homestead\\weapons.ent, has every weapon's every look as an appearance: a placed weapon is that
entity in that appearance. Reads the player's game; writes
  source/json/homestead/weapons.ent.json   (tools/import.py packs it)
  source/weapons.json                      (tools/build_catalog.py: one menu entry per weapon)
  python tools/make_weapons.py
"""
import glob, json, ntpath, os, re, shutil
import paths                                                  # (where the game and WolvenKit are)

SKIP = re.compile(r'shadow|placeholder|_stdr|fpp|_ui', re.I)   # (not seen: shadow casters, the reload's second mag)
KINDS = [('handgun', 'Handguns'), ('revolver', 'Revolvers'), ('rifle_assault', 'Assault Rifles'),
         ('rifle_precision', 'Precision Rifles'), ('rifle_sniper', 'Sniper Rifles'), ('smg', 'SMGs'), ('lmg', 'LMGs'),
         ('shotgun', 'Shotguns'), ('special', 'Heavy & Special'), ('explosives', 'Grenades'), ('', 'Melee')]


def D(o): return o.get('Data', o) if isinstance(o, dict) else o
def val(o, k): v = (o.get(k) or {}); return v.get('$value') if isinstance(v, dict) else None
def depot(o, k): return ((o.get(k) or {}).get('DepotPath') or {}).get('$value')


def unbundle(tmp, rx, **check):                             # (every archive folder in one run: a WolvenKit start costs
    game = os.path.join(paths.get('cp2077'), 'archive', 'pc')  # seconds, and it reads every archive's index each time)
    folders = [os.path.join(game, d) for d in ('content', 'ep1') if os.path.isdir(os.path.join(game, d))]
    paths.wk(['unbundle', *folders, '-o', tmp, '-r', rx], **check)


BATCH = 100                                                  # paths per unbundle regex (the command line holds ~32,000
                                                             # characters; a depot path is under 100)


def part(c):                                                # [mesh, its look, x, y, z, slot]
    t = ((c.get('localTransform') or {}).get('Position') or {})
    p = [((t.get(k) or {}).get('Bits', 0) or 0) / 131072 for k in 'xyz']
    b = D((c.get('parentTransform') or {}).get('Data') or {}) if isinstance(c.get('parentTransform'), dict) else {}
    return [depot(c, 'mesh'), val(c, 'meshAppearance') or 'default', *[round(v, 4) for v in p], val(b, 'bindName') or val(b, 'slotName') or '']


def kind(app):
    p = app.lower()
    for k, name in KINDS:
        if k and ('\\' + k + '\\' in p or '__' in ntpath.basename(p) and ntpath.basename(p).startswith('w_' + k + '__')): return name
    return 'Melee' if '\\melee\\' in p else 'Heavy & Special'


def pretty(preset):                                         # Preset_Ajax_Default -> Ajax; Preset_Nue_Jackie -> Nue Jackie
    w = [x for x in preset.split('_')[1:] if x.lower() not in ('default', 'base')]
    return ' '.join(x if x.isupper() else x.capitalize() for x in w) or preset


def main():
    with paths.scratch('weapons') as tmp: make(tmp)


def make(tmp):
    unbundle(tmp, r'^(base|ep1)\\gameplay\\factories\\items\\weapons\\weapons_appearances[^\\]*\.csv$',
             expect=[os.path.join(tmp, '**', '*.csv')], what="find the game's weapons list")
    rows = []
    for f in glob.glob(os.path.join(tmp, '**', '*.csv'), recursive=True):
        j = os.path.join(tmp, ntpath.basename(f) + '.json')
        paths.wk(['convert', 'serialize', f, '-o', tmp], expect=[j], what="read the game's weapons list")
        rows += json.load(open(j, encoding='utf-8-sig'))['Data']['RootChunk']['data']
    apps = {r[1]: r[0] for r in rows}
    print(len(rows), 'weapon looks in the factories,', len(apps), '.app files')
    for i in range(0, len(apps), BATCH):
        unbundle(tmp, '^(%s)$' % '|'.join(re.escape(a).replace(r'\\', '.') for a in list(apps)[i:i + BATCH]))
    looks, meshes = {}, {}
    aj = os.path.join(tmp, 'appjson'); os.makedirs(aj, exist_ok=True)
    for top in ('base', 'ep1'):                             # (all at once: each WolvenKit start costs seconds)
        if os.path.isdir(os.path.join(tmp, top, 'weapons')):
            paths.wk(['convert', 'serialize', os.path.join(tmp, top, 'weapons'), '-o', aj], expect=[os.path.join(aj, '*.json')],
                     what="read the game's weapon looks")
    for app, preset in apps.items():
        jp = os.path.join(aj, ntpath.basename(app) + '.json')
        if not os.path.exists(jp): print('  not in the game:', app); continue
        j = json.load(open(jp, encoding='utf-8-sig'))['Data']['RootChunk']
        names, first = [], None
        for a in j.get('appearances') or []:
            a = D(a); n = val(a, 'name')
            if not n: continue
            names.append(n)
            if first is None:                                # its parts: mesh, look, where (the slot it hangs on)
                first = [part(D(c)) for c in a.get('components') or [] if D(c).get('$type') in ('entSkinnedMeshComponent', 'entMeshComponent')]
                first = [m for m in first if m[0] and not SKIP.search(m[0])]
        if names: looks[preset] = (app, names[:1], first or [])   # (its first look only: one menu entry per weapon)
        for m in first or []: meshes[m[0]] = None
    for i in range(0, len(meshes), BATCH):
        unbundle(tmp, '^(%s)$' % '|'.join(re.escape(m).replace(r'\\', '.') for m in list(meshes)[i:i + BATCH]))
    md = os.path.join(tmp, 'meshjson'); os.makedirs(md, exist_ok=True)
    mt = os.path.join(tmp, 'meshes')                         # (only the meshes, apart: serialized in one go)
    for m in meshes:
        src = os.path.join(tmp, m.replace('\\', os.sep))
        if os.path.exists(src):
            os.makedirs(mt, exist_ok=True); shutil.move(src, os.path.join(mt, ntpath.basename(m)))
    if os.path.isdir(mt): paths.wk(['convert', 'serialize', mt, '-o', md], expect=[os.path.join(md, '*.json')], what="read the weapons' meshes")
    for m in meshes:
        try:
            bb = json.load(open(os.path.join(md, ntpath.basename(m) + '.json'), encoding='utf-8-sig'))['Data']['RootChunk']['boundingBox']
            meshes[m] = ([bb['Min'][k] for k in 'XYZ'], [bb['Max'][k] for k in 'XYZ'])
        except Exception: pass
    out, apps_ent = [], []
    for preset, (app, names, ms) in sorted(looks.items()):
        bbs = [meshes[m[0]] for m in ms if meshes.get(m[0])]
        if not bbs: print('  no bounds:', preset); continue
        lo = [round(min(b[0][k] for b in bbs), 3) for k in range(3)]
        hi = [round(max(b[1][k] for b in bbs), 3) for k in range(3)]
        for n in names:
            apps_ent.append({'$type': 'entTemplateAppearance', 'appearanceName': {'$type': 'CName', '$storage': 'string', '$value': n},
                             'appearanceResource': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'string', '$value': app}, 'Flags': 'Default'},
                             'name': {'$type': 'CName', '$storage': 'string', '$value': preset + '__' + n}})
        out.append(dict(preset=preset, name=pretty(preset), kind=kind(app), app=app, looks=names, min=lo, max=hi, parts=ms))
    if not out: raise SystemExit("no weapons made: WolvenKit read none of the game's weapons")
    tpl = json.load(open(os.path.join(paths.work(), 'json', 'homestead', 'empty.ent.json')))
    tpl['Data']['RootChunk']['appearances'] = apps_ent
    tpl['Data']['RootChunk']['defaultAppearance'] = {'$type': 'CName', '$storage': 'string', '$value': apps_ent[0]['name']['$value']}
    json.dump(tpl, open(os.path.join(paths.work(), 'json', 'homestead', 'weapons.ent.json'), 'w'), indent=1)
    json.dump(out, open(os.path.join(paths.work(), 'weapons.json'), 'w'), indent=1)
    print('%d weapons, %d looks -> weapons.ent' % (len(out), len(apps_ent)))


if __name__ == '__main__':
    main()
