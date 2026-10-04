"""The big catalog: every exported game prop measured and judged, so only pieces that work make it in.

  python tools/harvest.py meta     .mesh -> appearances, bone count, bounds (WolvenKit JSON, parsed then deleted)
  python tools/harvest.py geom     .glb  -> triangles, size, face area per side, a filled-volume ratio (parallel)
  python tools/harvest.py select   gates + taxonomy -> source/harvest/items.json (read by build_catalog.py)
  python tools/harvest.py shape    collision per item -> source/harvest/shape.json
  python tools/harvest.py more     what select would add, for review -> items_more.json, shape_more.json
  python tools/harvest.py lights   lamps' and signs' lit parts, from their meshes' emissive materials -> lights.json

Inputs: <work>/harvest/glb/<depot path>.{mesh,glb} (WolvenKit uncook; <work> is paths.work(), ours source/). Outputs:
<work>/harvest/*.json.
"""
import collections, glob, json, os, re, shutil, subprocess, sys, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths, taxonomy
from multiprocessing import Pool
import numpy as np
warnings.filterwarnings('ignore')
H = os.path.join(paths.work(), 'harvest')
GLB = os.path.join(H, 'glb')


def depot(p):  # local file -> depot path (backslashes, .mesh)
    return os.path.relpath(p, GLB).replace('/', '\\')[:-4] + '.mesh' if p.endswith('.glb') else os.path.relpath(p, GLB).replace('/', '\\')


# ---- meta --------------------------------------------------------------------------------------------------------
def meta():
    out = {}
    folders = sorted(set(os.path.dirname(p) for p in glob.glob(os.path.join(GLB, '**', '*.mesh'), recursive=True)))
    tmp = os.path.join(H, 'json_tmp')
    for i, f in enumerate(folders):
        os.makedirs(tmp, exist_ok=True)
        for old in glob.glob(os.path.join(tmp, '*')): os.remove(old)
        subprocess.run([paths.get('wolvenkit'), 'convert', 'serialize', f, '-o', tmp, '-v', 'Minimal'], env=paths.wk_env(), capture_output=True)
        for j in glob.glob(os.path.join(tmp, '*.json')):
            try:
                r = json.load(open(j, encoding='utf-8-sig'))['Data']['RootChunk']
            except Exception:
                continue
            name = os.path.basename(j)[:-5]
            b = r.get('boundingBox', {})
            apps = [a['Data']['name']['$value'] for a in r.get('appearances', []) if a.get('Data')]
            key = depot(os.path.join(f, name))
            out[key] = dict(apps=apps, bones=len(r.get('boneNames') or []),
                            min=[b.get('Min', {}).get(k, 0) for k in 'XYZ'], max=[b.get('Max', {}).get(k, 0) for k in 'XYZ'],
                            mats=len(r.get('materialEntries') or []))
        if i % 50 == 0: print(i, len(folders), len(out), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    json.dump(out, open(os.path.join(H, 'meta.json'), 'w'))
    print('meta', len(out))


# ---- geom --------------------------------------------------------------------------------------------------------
def geom_one(p):
    import trimesh
    try:
        with open(p, 'rb') as fh:                         # the glb's JSON chunk: skins?
            fh.seek(12); ln = int.from_bytes(fh.read(4), 'little'); fh.read(4)
            gj = json.loads(fh.read(ln))
        s = trimesh.load(p)
        g = s.dump(concatenate=True) if hasattr(s, 'dump') else s
        v = np.asarray(g.vertices)
        if len(g.faces) == 0: return depot(p), None
        m = trimesh.Trimesh(np.c_[v[:, 0], -v[:, 2], v[:, 1]], g.faces, process=False)
        n = m.face_normals * m.area_faces[:, None]
        sides = [(float(n[:, i].clip(0).sum()), float(-n[:, i].clip(max=0).sum())) for i in range(3)]
        lo, hi = m.bounds
        size = (hi - lo).tolist()
        # filled-volume ratio on a coarse voxel grid: how much of the bounds the piece fills
        pitch = max(max(size) / 24, 0.02)
        try:
            vg = trimesh.voxel.creation.voxelize(m, pitch).fill()
            fill = float(vg.matrix.sum()) * pitch ** 3 / max(np.prod(np.maximum(size, pitch)), 1e-9)
        except Exception:
            fill = -1
        return depot(p), dict(tris=int(len(g.faces)), size=size, min=lo.tolist(), max=hi.tolist(), sides=sides,
                              area=float(m.area), skins=len(gj.get('skins', [])), meshes=len(gj.get('meshes', [])), fill=fill)
    except Exception as e:
        return depot(p), dict(error=str(e)[:200])


def geom():                                               # (measured once: a rerun measures new exports only)
    f = os.path.join(H, 'geom.json')
    out = json.load(open(f)) if os.path.exists(f) else {}
    files = [p for p in glob.glob(os.path.join(GLB, '**', '*.glb'), recursive=True) if depot(p) not in out]
    with Pool(12) as pool:
        for i, (k, r) in enumerate(pool.imap_unordered(geom_one, files, chunksize=8)):
            out[k] = r
            if i % 500 == 0: print(i, len(files), flush=True)
    json.dump(out, open(f + '.tmp', 'w'))
    os.replace(f + '.tmp', f)
    print('geom', len(out), 'new', len(files))


# ---- select ------------------------------------------------------------------------------------------------------
# (regex on the path below environment\, tab, group). First match wins; group None = left out. Left out on purpose:
# drugs, money, cables, quest one-offs, signage lettering, holograms, road surfaces, gore, sex toys, mannequins (user,
# 2026-10-02: the whole group out).
RULES = [
    (r'recreation/(drugs|smoking)|misc/(money|tarot|numbers|shops|foliage)|toys/adult|grass/debris|^architecture/(?!megabuilding/decorations)|^base/lighting/'
     r'|medical/medicine|unique/|public_utility/(cable|elevator)|electrical/cable|advertising/(holograms|signage/.*(letter|font|character))|^street/|exhibition/(cyberware|av_engine|holo_city|netwatch|launcher|mantis)'
     r'|attachments/(military_cables|cables|monitor_arm|buttons)|hardware/(credit_chip|id_card|shard)|surgical_tool|garbage/(scraps|trash/(glass|paper))'
     r'|various/(blood|hanging_body|bubble_gum|flare|mask|necklace|orbital|origami|mound|cargo_train|public_train|barghest)'
     r'|tools/medical|workshop/nail|music/guitar_pic|games/(casino_chips|playing_cards|poker_chip|mexican|go_board|warri)|sports/(ball|gym_accessories|billiard_stick|cricket|hockey)'
     r'|devices/(access_point|antena|universal_device|light_switch|regular_door|elevator_door|wire_link|device_relay|shard_box|rc_controller|detonator|power_switch)|misc/weapons/(handcuffs|mine|spike)'
     r'|dino_|platform/stage|machine_ship|meat_machine|entropy_pipe|lootable_document|lootable_laptop|medical/accessories/(medkit)|mannequin', None, None),
    # The second harvest (docs/nc_expansion.md): small things on tables and shelves, posters and flags, signs. Clutter,
    # Posters and Signs are gate profiles (GATES), their menu folders in taxonomy.T
    (r'textiles/bedding/.*mattress|trash_mattress_|camping/sleeping_bag', 'Furniture', 'Bedroom/Beds'),
    (r'vegetation/furniture', 'Nature', 'Plants & Shrubs'),
    (r'megabuilding/decorations/bench', 'Furniture', 'Seating'),
    (r'food/|dining_accessories/|containers/bottles|misc/(paper|office|writing|hanging_lab_vial)|music/vinyl|textiles/(clothes|bathwear|bedding|cleaning)'
     r'|apparel/|sanitation/|medical/accessories|hardware/(keyboard|wide_keyboard)|tools/office|various/(funeral|picture_frames|voodoo_craft|hand_fan)|camping/camping_bag', 'Clutter', 'Clutter'),
    (r'advertising/(posters|streamers)|textiles/(flags|banners)', 'Posters', 'Posters & Flags'),
    (r'advertising/signage', 'Signs', 'Signs & Neon'),
    (r'advertising/', 'Street', 'Billboards'),
    (r'exhibition/display_case', 'Furniture', 'Storage/Display Cases & Safes'),
    # Buildings: whole small structures
    (r'small_shops/kiosks|vending_kiosk', 'Buildings', 'Kiosks & Stalls'),
    (r'small_shops/stands/(market|poor_market)', 'Buildings', 'Kiosks & Stalls'),
    (r'small_shops/awnings', 'Buildings', 'Awnings & Tarps'),
    (r'textiles/scaffolding', 'Buildings', 'Awnings & Tarps'),
    (r'recreation/camping/tent|scaffolding', 'Buildings', 'Tents & Scaffolds'),
    (r'rooftop_water_tower|greenhouse_tank', 'Buildings', 'Towers & Tanks'),
    # Industrial first where it lives inside other folders (wall units, fuse boxes, generators)
    (r'electronics/attachments|public_utility/(generator|electrical)|construction/power_generator', 'Industrial', 'Power'),
    # Furniture
    (r'furniture/bathroom|morgue_sink|onsen_locker', 'Furniture', 'Bathroom'),
    (r'furniture/.*(bed|bunk)', 'Furniture', 'Beds'),
    (r'furniture/kitchen|display_freezer|ice_machine|kitchen_counter|butcher_table', 'Furniture', 'Kitchen'),
    (r'furniture/restaurant/(bar|club|nkts_bar|afterlife)', 'Furniture', 'Bar'),
    (r'furniture/.*(chair|stool|sofa|couch|bench|bean_bag|couchette|low_seat|seat)|church_wooden_bench', 'Furniture', 'Seating'),
    (r'furniture/.*(table|desk|counter|workstation)', 'Furniture', 'Tables & Desks'),
    (r'furniture/(lab|outdoor)|medical_cart|umbrella|beach', 'Furniture', 'Outdoor & Lab'),
    (r'furniture/|tv_stand', 'Furniture', 'Storage & Shelves'),
    # Electronics
    (r'electronics/.*(television|tv|monitor|screen|computer|laptop|terminal|server|computing|hardware)', 'Electronics', 'Screens & Computers'),
    (r'electronics/.*(vending|drop_point|cash_register|service/)', 'Electronics', 'Vending & Service'),
    (r'electronics/.*(game_machine|pachinko|cyber_tube|braindance)|recreation/games', 'Electronics', 'Arcade & Casino'),
    (r'electronics/(audio|.*(speaker|radio))|music/(amplifier|speaker)', 'Electronics', 'Audio'),
    (r'electronics/(security|medical)', 'Electronics', 'Security & Medical'),
    (r'electronics/', 'Electronics', 'Appliances & Devices'),
    # Lighting
    (r'lighting/street', 'Lighting', 'Street Lights'),
    (r'lighting/(candles|lanterns)', 'Lighting', 'Lanterns & Candles'),
    (r'lighting/.*(ceiling|hanging_lamp|corridor|bar_lamp|fluorescent)', 'Lighting', 'Ceiling Lights'),
    (r'lighting/.*(spotlight|construction_light|studio|disco|surgery_lamp)|lighting/(industrial|lab)', 'Lighting', 'Work Lights'),
    (r'lighting/', 'Lighting', 'Lamps'),
    # Containers
    (r'lootable_(weapon|ammo|military|equipment|gadgets)|containers/cases', 'Containers', 'Cases & Chests'),
    (r'containers/(cargo|crates|packaging)|lootable_(crate|valuable|av_cargo)', 'Containers', 'Crates & Boxes'),
    (r'containers/(barrel|tanks|gallons|buckets)', 'Containers', 'Barrels & Tanks'),
    (r'garbage/', 'Containers', 'Bins & Dumpsters'),
    (r'containers/(planter|vases|exotic)', 'Containers', 'Planters & Vases'),
    (r'containers/|lootable_', 'Containers', 'Cases & Chests'),
    # Industrial
    (r'industrial/pipes', 'Industrial', 'Pipes'),
    (r'public_utility/vents', 'Industrial', 'Vents & Fans'),
    (r'industrial/(trolley|platform)|forklift|car_lift|scissor', 'Industrial', 'Pallets & Lifts'),
    (r'decoration/construction/|public_utility/construction|metal_studs|heap_pipes|cable_coil', 'Industrial', 'Construction'),
    (r'tools/', 'Industrial', 'Tools'),
    (r'industrial/|public_utility/fixtures/(attachment_antenna|utility_fixture)', 'Industrial', 'Machines'),
    # Street
    (r'public_utility/fences', 'Street', 'Fences & Railings'),
    (r'public_utility/(roadblock|road_block)|hesco|sandbags', 'Street', 'Barriers'),
    (r'public_utility/(signages|racks|fixtures)', 'Street', 'Signs & Fixtures'),
    # Decor
    (r'sculptures|exhibition/|fountain|droid|painting|flamingo|katana_stand', 'Decor', 'Art & Statues'),
    (r'misc/music', 'Decor', 'Music'),
    (r'recreation/sports', 'Decor', 'Sports & Gym'),
    (r'textiles/', 'Decor', 'Odds & Ends'),
    (r'medical/|misc/', 'Decor', 'Odds & Ends'),
    # Vehicles
    (r'vehicles/|motorboat', 'Industrial', 'Vehicles & Tires'),
    # Weapons
    (r'weapons/|fire_axe|fake_katana', 'Weapons', 'Weapons'),
    # Nature
    (r'vegetation/trees|palms/', 'Nature', 'Trees & Palms'),
    (r'vegetation/', 'Nature', 'Plants & Shrubs'),
    (r'terrain/', 'Nature', 'Rocks'),
]
# parts and technical meshes (by name): lids, doors, drawers, bedding layers, damaged / debris / proxy variants
PART = re.compile(r'(_|^)(lod\d|proxy|mproxy|shadow|occluder|decal|col|collision|helper|blockout|dummy|placeholder|mask|frag|chunk|shard|debris|dst|destr\w*|destroyed|broken|'
                  r'damaged|fractured|burnt|dirty_decal|glass|lid|door|doors|drawer|drawers|handle|cover|seat|panel|pillow|quilt|bedding|blanket|duvet|mattress|cushion|sheet|cap|top|bottom|mid|'
                  r'left|right|end|start|corner|part|parts|piece|pieces|leg|legs|base|frame|screen|glow|emissive|hologram|holo|fx|ui|cable|cables|wire|wires|rope|chain|'
                  r'attachment|addon|addons|element|module|modules|segment|plug|mount|hinge|knob|button|sign_only|text|logo|letter|interior|inside|ext|extension)(_|$|\d)')
# whole pieces whose names have a part's word in them (judged from sampled names, the sheets have the last word;
# "light" and "open" are out of PART: most are whole lamps and open boxes - a lamp-named mesh that glows in no look
# is still a part, pick())
WHOLE = re.compile(r'asian_screen|(cinema|low|car|train)_seat|colorful_mask|holo_projector_[a-z]$|solar_panel_[a-z]$|control_panel_[a-z]$|^attachment_antenna_1_[a-z]$'
                   r'|interior_lab_lamp|concrete_debris_(small|medium|large|big)$|debris_pile|mattress_[a-z]$|drug_lab_glass_[a-z]$|voodoo_glass|^glass_[a-z]_|_glass_(vine|champagne)')
DESTR = re.compile(r'/_?destruction/|/_proxyhelper/')     # (a destructible's broken pieces; proxies)
OFF_COPY = re.compile(r'_off$')                              # (a lamp or a sign switched off: the lit one is there)
# gate profiles by rule tab: (smallest size in m, one-sided faces out?). Clutter is small; posters, signs and foliage
# are one-sided by nature (a poster's back is the wall, a leaf card is drawn from both sides); rocks are not (user,
# 2026-10-02: solid standalone rocks, not faces or walls) - by folder, Rocks
GATES = {'Weapons': (0.4, True), 'Clutter': (0.15, True), 'Posters': (0.3, False), 'Signs': (0.3, False), 'Nature': (0.3, False),
         'Rocks': (0.3, True)}
ROCK_OUT = re.compile(r'mining_tunnel/|static_for_foliage/')   # (tunnel walls and floors; copies of the canyon rocks)
ROCK_FILL = 0.3                                              # (under it a rock is a shell: a cliff face, half a hill)
# clothes the way a body wears them (user, 2026-10-02: "solid and positioned"): the character garments' own meshes,
# named <layer><n>_<nnn>_ (l1_045_ma_pants__suit_simple); piles, folded, scattered and hanging clothes are named for it
GARMENT = re.compile(r'^[a-z]\d_\d{3}_')
# a sign in parts (user, 2026-10-02: assembled signs only): its arm, support, back or middle, one bar of a set, a
# bare bracket (fill <= 0.1 with a modelled frame's triangles: wire in a big box), a single tube or strip (sign_line);
# and a family most of whose members are such parts (Misty's neon: six tubes and an arc)
SIGN_PART = re.compile(r'(_|^)(arm|support|back|middle)(_|$|\d)|_set_[a-z]_[a-z]$')
SIGN_FILL = 0.1
TABS = ['Structure', 'Buildings', 'Furniture', 'Electronics', 'Lighting', 'Containers', 'Industrial', 'Street', 'Decor',
        'Nature', 'Weapons', 'Zone']
ITEMS = os.path.join(H, 'items.json')
LIGHT_WORD = re.compile(r'(_|^)lights?(_|$|\d)')


def sign_line(size, tris):
    """a tube: thin both ways and a metre or more long, or a bare strip twenty times longer than it is wide (few
    triangles: a lettered board that long has hundreds)"""
    a, b, c = sorted(size)
    return (c >= 1 and a <= 0.07 and b <= 0.2) or (c >= 20 * b and tris < 300)


def pick():
    """the gates and the menu folders over every measured mesh -> (items, why)"""
    geo = json.load(open(os.path.join(H, 'geom.json')))
    met = json.load(open(os.path.join(H, 'meta.json'))) if os.path.exists(os.path.join(H, 'meta.json')) else {}
    rules = [(re.compile(r), t, g) for r, t, g in RULES]
    dropf = os.path.join(H, 'drop.txt')                      # eyeballed out
    dropped = {l.strip() for l in open(dropf) if l.strip() and not l.startswith('#')} if os.path.exists(dropf) else set()
    why, items, seen, fams = collections.Counter(), [], set(), collections.defaultdict(lambda: [0, 0])
    for depot_, x in sorted(geo.items()):
        rel = depot_.split('\\environment\\', 1)[-1].replace('\\', '/')
        stem = os.path.basename(rel)[:-5]
        rule = next(((t, gr) for r, t, gr in rules if r.search(rel)), None)
        if rule is None: why['no rule'] += 1; continue
        if rule[0] is None: why['left out'] += 1; continue
        if not x or 'tris' not in x: why['no geometry'] += 1; continue
        m = met.get(depot_, {})
        if x['skins'] or m.get('bones'): why['skinned'] += 1; continue
        if (PART.search(stem) and not WHOLE.search(stem)) or DESTR.search(rel): why['part / technical'] += 1; continue
        if OFF_COPY.search(stem): why['off copy'] += 1; continue
        cat, grp = taxonomy.path(rule[0], stem, rule[1])     # the menu folder (tools/taxonomy.py)
        if cat is None: why['taxonomy drop'] += 1; continue
        rock = cat == 'Nature' and grp.startswith('Rocks')
        size = x['size']
        big, small = max(size), sorted(size)[1]
        lo_size, sided = GATES['Rocks' if rock else rule[0]] if rock or rule[0] in GATES else (0.3, True)
        if big < lo_size or small < 0.05: why['too small / flat'] += 1; continue
        if big > 30: why['too big'] += 1; continue
        if x['tris'] > 80000 or x['tris'] < 12: why['triangles'] += 1; continue
        imb = [abs(p - n) / max(p + n, 1e-9) for p, n in x['sides']]
        if sided and (max(imb[:2]) > 0.35 or imb[2] > 0.9): why['one-sided'] += 1; continue
        if rock and (ROCK_OUT.search(rel) or x['fill'] < ROCK_FILL): why['rock face / tunnel'] += 1; continue
        if rule[0] == 'Clutter' and GARMENT.search(stem): why['worn garment'] += 1; continue
        if rule[0] == 'Lighting' and SIGN_PART.search(stem): why['fixture part'] += 1; continue   # (a lamp's support, arm)
        fam = re.sub(r'_[a-z]$', '', stem)
        if rule[0] == 'Signs':
            fams[fam][1] += 1
            if SIGN_PART.search(stem) or (x['fill'] <= SIGN_FILL and x['tris'] > 500) or sign_line(size, x['tris']): fams[fam][0] += 1; why['sign part'] += 1; continue
        sig = (x['tris'], tuple(round(v, 2) for v in size), taxonomy.pretty(stem))   # (same shape, other name: a retexture, kept)
        if sig in seen: why['duplicate'] += 1; continue
        seen.add(sig)
        apps = [a for a in m.get('apps', []) if not re.search(r'destroy|broken|damag|burn|dirty|off$', a)][:6] or ['default']
        if 'h_' + stem in dropped: why['eyeballed out'] += 1; continue
        items.append(dict(key='h_' + stem, name=taxonomy.pretty(stem), cat=cat, group=grp, mesh=depot_, apps=apps,
                          min=x['min'], max=x['max'], fill=x['fill'], tris=x['tris'], rule=rule[0], fam=fam))
    # a sign whose family is mostly parts is one too; a lamp-named mesh with no glowing material in any of its looks
    # is a fixture's part (user, 2026-10-02: ceiling lights' pipes, brackets and broken shards)
    named = [i for i in items if i['cat'] == 'Lighting' and LIGHT_WORD.search(os.path.basename(i['mesh'])[:-5])]
    lit = glows(named)
    dark = {i['mesh'].lower() for i in named if not lit[i['mesh'].lower()].get('any')}
    keep = []
    for i in items:
        r, f = i.pop('rule'), i.pop('fam')
        if r == 'Signs' and fams[f][0] * 2 > fams[f][1]: why['sign part'] += 1; continue
        if i['mesh'].lower() in dark: why['fixture part (no glow)'] += 1; continue
        keep.append(i)
    items = keep
    # keys are unique and stay put (placed pieces are saved by key): a mesh keeps the key items.json gave it, a new
    # repeat gets _<n>
    old = {i['mesh']: i['key'] for i in json.load(open(ITEMS))} if os.path.exists(ITEMS) else {}
    keys, taken, n = collections.Counter(i['key'] for i in items), set(old.values()), 0
    for i in items:
        if i['mesh'] in old: i['key'] = old[i['mesh']]; continue
        if keys[i['key']] > 1 or i['key'] in taken:
            while i['key'] + '_' + str(n) in taken: n += 1
            i['key'] += '_' + str(n)
        taken.add(i['key'])
    # (tiny folders are folded in build_catalog, over the whole catalog)
    # names: repeats in a group get A, B, C...
    by = collections.defaultdict(list)
    for i in items: by[(i['cat'], i['group'], i['name'])].append(i)
    for v in by.values():
        if len(v) > 1:
            for n, i in enumerate(sorted(v, key=lambda i: i['key'])): i['name'] = (i['name'] + ' ' + (chr(65 + n) if n < 26 else str(n))).strip()
    items.sort(key=lambda i: (TABS.index(i['cat']), i['group'].replace('Other', '~'), i['name']))   # Other last
    return items, why


def report(items, why):
    print('kept', len(items), dict(why))
    for (t, g), n in sorted(collections.Counter((i['cat'], i['group']) for i in items).items(), key=lambda k: (TABS.index(k[0][0]), k[0][1])):
        print('  %-12s %-28s %4d' % (t, g, n))


def select():
    items, why = pick()
    json.dump(items, open(ITEMS, 'w'), indent=0)
    report(items, why)


def more():
    """candidates for review: what pick() keeps that items.json doesn't have -> items_more.json, and their collision
    -> shape_more.json (after the review: drops into drop.txt, then select and shape)"""
    have = {i['mesh'] for i in json.load(open(ITEMS))}
    items, why = pick()
    new = [i for i in items if i['mesh'] not in have]
    json.dump(new, open(os.path.join(H, 'items_more.json'), 'w'), indent=0)
    report(new, why)
    shape('items_more.json', 'shape_more.json')


# ---- shape -------------------------------------------------------------------------------------------------------
# Per selected item: its ground contact (colliders.ground) and collision boxes. Small or solid pieces get their bounds;
# big hollow ones (a kiosk, a car, a rock arch) are voxelized into boxes, coarser until there are few enough. Trees
# block at the trunk only, plants and shrubs not at all (you walk through them, as in the game).
MAX_BOXES = 32


def load_glb(depot_):
    import trimesh
    s = trimesh.load(os.path.join(GLB, depot_[:-5] + '.glb'))
    g = s.dump(concatenate=True) if hasattr(s, 'dump') else s
    v = np.asarray(g.vertices)
    return trimesh.Trimesh(np.c_[v[:, 0], -v[:, 2], v[:, 1]], g.faces, process=False)


def shape_one(it):
    sys.path.insert(0, os.path.dirname(__file__))
    import colliders
    try:
        m = load_glb(it['mesh'])
        mn, mx = it['min'], it['max']
        base = colliders.ground(m.vertices, mn, mx)
        size = [mx[i] - mn[i] for i in range(3)]
        bb = [[round((mx[i] + mn[i]) / 2, 3) for i in range(3)] + [round((mx[i] - mn[i]) / 2, 3) for i in range(3)]]
        if it['cat'] == 'Nature' and not it['group'].startswith('Rocks'):   # (trees and palms: the trunk, 40 cm round
            trunk = [[base[0], base[1], base[2] + 1.5, 0.2, 0.2, 1.5]]          # the base, 3 m up; plants: nothing)
            return it['key'], dict(base=base, boxes=trunk if it['group'] in ('Trees', 'Palms') else [])
        if max(size) < 1.2 or it['fill'] > 0.7:
            return it['key'], dict(base=base, boxes=bb)
        pitch = min(max(max(size) / 16, 0.08), 0.6)
        for _ in range(4):
            b = colliders.mesh_boxes(m, (mn, mx), pitch, minvol=0.01)
            if 0 < len(b) <= MAX_BOXES: return it['key'], dict(base=base, boxes=[list(x) for x in b])
            pitch *= 1.5
        return it['key'], dict(base=base, boxes=bb)
    except Exception as e:
        return it['key'], dict(error=str(e)[:200])


def shape(src='items.json', dst='shape.json'):
    items = json.load(open(os.path.join(H, src)))
    out = {}
    with Pool(12) as pool:
        for i, (k, r) in enumerate(pool.imap_unordered(shape_one, items, chunksize=4)):
            out[k] = r
            if i % 200 == 0: print(i, len(items), flush=True)
    json.dump(out, open(os.path.join(H, dst), 'w'))
    print('shape', len(out), 'errors', sum(1 for r in out.values() if 'error' in r))


# ---- lights ------------------------------------------------------------------------------------------------------
# A lamp's or a sign's lit parts, from its own mesh: the chunks an appearance gives a glowing material (an emissive
# template or emissive values, not switched off), where they are in the glb (submesh_<chunk>, LOD 1) and their
# colour; the look they glow in (the item's first that glows) and one that switches them all off. build_catalog
# puts the light there (native_light); pick() drops a lamp-named mesh that glows in no look (a fixture's pipe).
GLOW_MT = re.compile(r'lights_interactive|signages|neon_tubes|device_diode')
GLOW_WORD = re.compile(r'emis|emmis|light|glow|bulb|neon|fluo')
NOT_GLOW = re.compile(r'multilayered|decal|glass|font')     # (paint, stickers, panes, lettering masks)
OFF = re.compile(r'(^|_)off(_|$)|black\.xbm')


def glow_colour(name, m):
    """a material's glow: its colour [r, g, b], [] when it glows but says no colour, None when it doesn't glow"""
    base = m['baseMaterial']['DepotPath']['$value'].lower()
    vals = {k: v for d in m.get('values') or [] for k, v in d.items() if k != '$type'}
    ev = [v for k, v in vals.items() if k.endswith('EmissiveEV')]
    tex = vals.get('Emissive')
    tex = tex['DepotPath']['$value'].lower() if isinstance(tex, dict) and 'DepotPath' in tex else ''
    if NOT_GLOW.search(base) or OFF.search(name.lower()) or OFF.search(base) or OFF.search(tex) or (ev and max(ev) <= 0): return None
    if not (GLOW_MT.search(base) or ev or GLOW_WORD.search(name.lower()) or GLOW_WORD.search(os.path.basename(base))): return None
    c = vals.get('EmissiveColor') or vals.get('EmissiveColor1') or vals.get('ColorOneStart')   # (metal_base, device_diode, signages)
    return [c['Red'], c['Green'], c['Blue']] if isinstance(c, dict) and max(c.get('Red', 0), c.get('Green', 0), c.get('Blue', 0)) > 0 else []


def glow_one(it, r):
    """(item, its .mesh JSON root) -> {any, lit (the look), glow: [[cx, cy, cz, hx, hy, hz]] (1-2 boxes), color, off}"""
    import trimesh
    ext = r.get('externalMaterials') or []
    loc = r['localMaterialBuffer']['materials'] or [x['Data'] for x in r.get('preloadLocalMaterialInstances') or []]
    mats = {}
    for e in r['materialEntries']:
        i, n = e['index'], e['name']['$value']
        m = loc[i] if e.get('isLocalInstance') and i < len(loc) else dict(baseMaterial=ext[i]) if not e.get('isLocalInstance') and i < len(ext) else None
        mats[n] = glow_colour(n, m) if m else None
    apps = {a['Data']['name']['$value']: [c['$value'] for c in a['Data']['chunkMaterials']] for a in r.get('appearances', []) if a.get('Data')}
    lit_in = {a: {k: mats[c] for k, c in enumerate(ch) if mats.get(c) is not None} for a, ch in apps.items()}
    look = next((a for a in it['apps'] + list(apps) if lit_in.get(a)), None)
    out = dict(any=look is not None, lit=look, glow=None, color=None, off=None)
    if look is None: return out
    lit = lit_in[look]
    out['color'] = next((c for c in lit.values() if c), None)
    out['off'] = next((a for a, ch in apps.items() if all(k < len(ch) and mats.get(ch[k]) is None for k in lit)), None)
    s = trimesh.load(os.path.join(GLB, it['mesh'][:-5] + '.glb'))
    v = []
    for node in s.graph.nodes_geometry:
        tf, gname = s.graph[node]
        k = re.search(r'submesh_(\d+)', gname) or re.search(r'submesh_(\d+)', node)
        if k and int(k.group(1)) in lit: v.append(trimesh.transform_points(s.geometry[gname].vertices, tf))
    if not v: return out
    v = np.vstack(v)
    v = np.c_[v[:, 0], -v[:, 2], v[:, 1]]                     # (.glb Y-up -> the piece's space)
    a = int(np.ptp(v[:, 1]) > np.ptp(v[:, 0]))               # two lamp heads on one mesh (a double street lamp):
    xs = np.sort(v[:, a])                                     # split at the widest gap along the long way
    gaps = np.diff(xs)
    parts = [v[v[:, a] <= xs[gaps.argmax()]], v[v[:, a] > xs[gaps.argmax()]]] if len(xs) > 1 and gaps.max() > 0.5 else [v]
    out['glow'] = [[round(float(x), 3) for x in list((p.min(0) + p.max(0)) / 2) + list((p.max(0) - p.min(0)) / 2)] for p in parts]
    return out


def glows(items, fresh=False):
    """{mesh depot path (lower case): its lit parts} for these items: lights.json, and what isn't in it yet read from
    the meshes (their .mesh files serialized at once, under their keys, in a temp folder)"""
    import tempfile
    f = os.path.join(H, 'lights.json')
    out = {} if fresh or not os.path.exists(f) else json.load(open(f))
    todo = {i['mesh'].lower(): i for i in items if i['mesh'].lower() not in out}
    if not todo: return out
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, 'in')); os.makedirs(os.path.join(tmp, 'out'))
        for i in todo.values(): shutil.copy(os.path.join(GLB, i['mesh']), os.path.join(tmp, 'in', i['key'] + '.mesh'))
        subprocess.run([paths.get('wolvenkit'), 'convert', 'serialize', os.path.join(tmp, 'in'), '-o', os.path.join(tmp, 'out'), '-v', 'Minimal'], env=paths.wk_env(), capture_output=True)
        for k, i in todo.items():
            try:
                r = json.load(open(os.path.join(tmp, 'out', i['key'] + '.mesh.json'), encoding='utf-8-sig'))['Data']['RootChunk']
                out[k] = glow_one(i, r)
            except Exception as e: out[k] = dict(error=str(e)[:200])
    json.dump(out, open(f, 'w'), indent=0)
    return out


def lights():
    """every harvested lamp's and sign's lit parts (items.json and items_more.json), read afresh -> lights.json"""
    items = [i for f in ('items.json', 'items_more.json') if os.path.exists(os.path.join(H, f))
             for i in json.load(open(os.path.join(H, f))) if i['cat'] == 'Lighting' or i['group'].startswith('Signs & Neon')]
    out = glows(items, fresh=True)
    print('lights', len(out), 'glowing', sum(1 for r in out.values() if r.get('glow')), 'with an off look', sum(1 for r in out.values() if r.get('off')),
          'errors', sum(1 for r in out.values() if 'error' in r))


if __name__ == '__main__':
    {'meta': meta, 'geom': geom, 'select': select, 'more': more, 'shape': shape, 'lights': lights}[sys.argv[1]]()
