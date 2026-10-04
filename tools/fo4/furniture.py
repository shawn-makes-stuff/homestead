"""Where Fallout's people use its furniture: a FURN record's markers (SNAM, 24 bytes each: offset xyz in Fallout units,
heading in radians, keyword, entry flags; MNAM's low bits: which are enabled) and what they do there (its AnimFurn*
keyword: sit on a chair, lie in a bed, stand at a counter...). Markers stand on the floor: the animation brings the
height, made for Fallout's seats: so each marker also gets the top of what's under it (a vertical line through the
piece's mesh: the seat, the mattress), which life.lua matches the Cyberpunk animation to.
-> source/fo4/pieces.json: `seats` [[x, y, z, yaw, kind, top]] (metres and degrees in the piece's space; init's
modules/life.lua plays a Cyberpunk workspot of that kind there).
  python tools/fo4/furniture.py     (after convert.py; convert.py runs it)
"""
import json, math, os, struct, sys
import numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import esm
from convert import FO4, UNIT

KIND = {                                                    # Fallout's animation keyword -> what life.lua plays
    'AnimFurnChairSitAnims': 'chair', 'AnimFurnBarberChair': 'chair', 'AnimFurnCouch': 'couch',
    'AnimFurnChairWithTable': 'table', 'AnimFurnPicnicTable': 'table', 'AnimFurnBarStool': 'stool',
    'AnimFurnBedAnims': 'bed', 'AnimFurnFloorBedAnims': 'floorbed', 'AnimFurnGuardPost': 'guard',
    'AnimFurnBarShopKeep': 'counter', 'AnimFurnClipboardWithPen': 'counter', 'AnimFurnSodaStationDLC06': 'counter',
    'AnimFurnWorkbenchWeapons': 'work', 'AnimFurnWorkbenchChemistryA': 'work', 'AnimFurnSodaMixingMachine': 'work',
    'AnimFurnWorkbenchArmorA': 'work', 'AnimsFurnWorkbenchRobot': 'work', 'AnimFurnWorkbenchCookingStove': 'work',
    'AnimFurnDLC04MoonShineStill': 'work', 'AnimFurnWeldingLow': 'work', 'AnimFurnWeldingMedium': 'work',
    'AnimFurnWoodCookingFire': 'kneel', 'AnimFurnWorkbenchCookingSpit': 'kneel',
}
SITS = {'chair', 'table', 'stool', 'couch'}                 # (sat on: their seat's middle is found, seat_mid)


def heights(T, x, y):
    """where a vertical line at x, y meets the triangles T (n, 3, 3)"""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(d) > 1e-12
    d = np.where(ok, d, 1)
    l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
    l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
    l3 = 1 - l1 - l2
    return (l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2])[ok & (l1 >= 0) & (l2 >= 0) & (l3 >= 0)]


def top_at(T, x, y, z):
    """the seat under a marker: the highest surface below 0.95 m over it, median of five lines round it"""
    tops = []
    for dx, dy in ((0, 0), (0.08, 0), (-0.08, 0), (0, 0.08), (0, -0.08)):
        h = [v for v in heights(T, x + dx, y + dy) if z - 0.05 < v < z + 0.95]
        if h: tops.append(max(h))
    return round(float(np.median(tops)) - z, 3) if tops else 0.0


def seat_mid(T, m):
    """how far forward of a sitting marker the middle of its seat top is (+ the way the sitter faces): the cushion from
    its front edge back to where the backrest rises, along the line through the marker. Cyberpunk's sit animations go
    by the seat (life.lua FWD is from here), not by where Fallout's marker stands - one offset per kind put people into
    some backrests. None when the line finds no seat a body's depth"""
    x, y, z, yaw, seat = m[0], m[1], m[2], m[3], m[2] + m[5]
    fx, fy = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    def on(d):                                               # seat-high surface here, and no back over it
        h = heights(T, x + fx * d, y + fy * d)
        h = h[(h > z - 0.05) & (h < z + 1.3)]
        return bool(len(h)) and bool((np.abs(h - seat) < 0.05).any()) and not ((h > seat + 0.12) & (h < seat + 0.8)).any()
    start = next((d for d in (0, 0.04, -0.04, 0.08, -0.08, 0.12, -0.12) if on(d)), None)
    if start is None: return None
    front = back = start
    while front < 1.0 and on(front + 0.02): front += 0.02
    while back > -1.0 and on(back - 0.02): back -= 0.02
    if not 0.2 <= front - back <= 0.9: return None           # (not a seat: a sliver, or a bench's whole length)
    return round((front + back) / 2, 3)


def triangles(glb):
    m = trimesh.load(glb, force='mesh')
    v = np.asarray(m.vertices)
    return np.c_[v[:, 0], -v[:, 2], v[:, 1]][np.asarray(m.faces)]       # glTF (Y up) -> Cyberpunk (Z up)


def beds(p, T, s):
    """a bed's places from the bed itself: Fallout's sleep markers face across it (its animation turns them), so each
    becomes the middle of its half of the mattress (a double: two), yaw pointing to the head end - its taller end"""
    lo, hi = p['min'], p['max']
    ax = 1 if hi[1] - lo[1] >= hi[0] - lo[0] else 0           # (the long side)
    head = 1
    if T is not None:
        v = T.reshape(-1, 3)
        top = lambda m: float(v[m, 2].max()) if m.any() else 0.0
        if top(v[:, ax] < lo[ax] + 0.35) > top(v[:, ax] > hi[ax] - 0.35) + 0.02: head = -1
    yaw = {(1, 1): 0.0, (1, -1): 180.0, (0, 1): -90.0, (0, -1): 90.0}[(ax, head)]
    c = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2]
    out = []
    for m in s:                                               # (side by side across the bed, as Fallout's are)
        q = list(c)
        if len(s) > 1: q[1 - ax] = m[1 - ax]
        out.append([round(q[0], 3), round(q[1], 3), m[2], yaw, m[4]])
    return out


def seats_of(g, k):
    kw = g.field(k, 'KWDA') or b''
    kinds = [KIND.get(g.edid(g.ref(k, struct.unpack_from('<I', kw, i)[0])) or '') for i in range(0, len(kw), 4)]
    kind = next((x for x in kinds if x), None)
    mn = g.field(k, 'MNAM')
    if not kind or not mn: return []
    on = struct.unpack_from('<I', mn)[0] & 0xffffff         # (the enabled markers)
    out = []
    for s in g.fields(k, 'SNAM'):
        for i in range(0, len(s) - 23, 24):
            if not on >> (i // 24) & 1: continue
            x, y, z, head = struct.unpack_from('<4f', s, i)
            out.append([round(x * UNIT, 3), round(y * UNIT, 3), round(z * UNIT, 3), round(-math.degrees(head), 1), kind])
    return out                                              # (Fallout turns clockwise: Cyberpunk's yaw the other way)


def patch(g=None):
    g = g or esm.Game()
    by = {'fo4_' + (g.edid(k) or '').lower(): k for k, (t, _) in g.rec.items() if t == 'FURN'}
    path = os.path.join(FO4, 'pieces.json')
    pieces = json.load(open(path))
    n = 0
    for p in pieces:
        p.pop('seats', None)
        s = p['kind'] == 'FURN' and p['key'] in by and seats_of(g, by[p['key']])
        if s:
            T = triangles(p['glb']) if p.get('glb') and os.path.exists(p['glb']) else None
            if s[0][4] in ('bed', 'floorbed'): s = beds(p, T, s)
            for m in s:
                m.append(top_at(T, m[0], m[1], m[2]) if T is not None else 0.0)
                mid = T is not None and m[4] in SITS and m[5] > 0.2 and seat_mid(T, m)
                if mid is not None and mid is not False: m.append(mid)   # (seats[7]; without it life.lua goes by the marker)
            p['seats'] = s; n += 1
    json.dump(pieces, open(path, 'w'))
    print(n, 'pieces with seats')


if __name__ == '__main__':
    patch()
