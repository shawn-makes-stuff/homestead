"""What Fallout attaches to its pieces through add-on nodes (nif.py addons: "AddOnNode<n>" -> the ADDN record with
index n): lights (ADDN LNAM -> a LIGH record: colour, radius, fade; the workshop's switchable lamps, a campfire's glow)
and effects (ADDN MODL: fire, smoke, sparks; SNAM: their sound, e.g. a fire's crackle). Plus a light object's own
light (LIGH records: at the model's AttachLight node, else near its top). -> source/fo4/pieces.json: `lights`
[{color, radius, fade, pos}] (Cyberpunk light components, init.lua addLight) and `effects` [{model, sound, pos}].
  python tools/fo4/lights.py        (after convert.py; convert.py runs it)
"""
import json, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import esm, nif
from convert import Files, objects, FO4, UNIT


def light_of(g, k, pos, M=None):
    """a LIGH record's light at pos (metres, the piece's space); None if it has no usable data. A spotlight (flags
    0x400 / 0x4000) also has its cone (FOV, degrees) and where it shines: its node's -X (a display's lights shine down
    on the armour, a floor light up)"""
    d = g.field(k, 'DATA')
    if not d or len(d) < 16: return None
    _time, radius = struct.unpack_from('<iI', d, 0)
    fn = g.field(k, 'FNAM')
    fade = struct.unpack('<f', fn[:4])[0] if fn and len(fn) >= 4 else 1.0
    out = dict(color=[d[8], d[9], d[10]], radius=round(radius * UNIT, 2), fade=round(fade, 2), pos=[round(float(v), 3) for v in pos])
    if len(d) >= 24:
        flags, _fall, fov = struct.unpack_from('<Iff', d, 12)
        if flags & 0x4400 and M is not None:
            R = M / np.maximum(np.linalg.norm(M, axis=0, keepdims=True), 1e-9)
            out['spot'] = round(float(fov), 1)
            out['dir'] = [round(float(v), 3) for v in -R[:, 0]]
    return out


def patch(g=None, files=None):
    g = g or esm.Game()
    files = files or Files()
    addn = {}
    for k, (t, _) in g.rec.items():
        d = g.field(k, 'DATA') if t == 'ADDN' else None
        if d and len(d) >= 4: addn[struct.unpack_from('<I', d)[0]] = k
    by = {('fo4_' + (o['edid'] or '').lower()): o for o in objects(g)}
    path = os.path.join(FO4, 'pieces.json')
    pieces = json.load(open(path))
    nl = ne = 0
    for p in pieces:
        p.pop('light', None); p.pop('lights', None); p.pop('effects', None)
        o = by.get(p['key'])
        mb = files.read(o['model']) if o else None
        if not mb: continue
        try: n = nif.Nif(mb)
        except Exception: continue
        lights, effects = [], []
        for idx, T, M in n.addons():
            k = addn.get(idx)
            if k is None: continue
            pos = T * UNIT
            l = g.field(k, 'LNAM')
            lk = g.ref(k, struct.unpack('<I', l[:4])[0]) if l else None
            if lk in g.rec and g.rec[lk][0] == 'LIGH':
                x = light_of(g, lk, pos, M)
                if x: lights.append(x)
            m = g.field(k, 'MODL')
            if m:
                s = g.field(k, 'SNAM')
                sk = g.ref(k, struct.unpack('<I', s[:4])[0]) if s else None
                effects.append(dict(model=m.rstrip(b'\0').decode('cp1252').lower(), sound=g.edid(sk) if sk in g.rec else None,
                                    pos=[round(float(v), 3) for v in pos]))
        if o['kind'] == 'LIGH' and not lights:                 # a light object: its own light
            f = n.node_transform('AttachLight')
            pos = f[1] * UNIT if f is not None else [(p['min'][0] + p['max'][0]) / 2, (p['min'][1] + p['max'][1]) / 2, p['max'][2] - 0.1]
            x = light_of(g, o['rec'], pos, f[0] if f is not None else None)
            if x: lights.append(x)
        if lights: p['lights'] = lights; nl += 1
        if effects: p['effects'] = effects; ne += 1
    json.dump(pieces, open(path, 'w'))
    print(nl, 'pieces with lights,', ne, 'with effects')


if __name__ == '__main__':
    patch()
