"""Fallout 4's own keyframe animations (nif.py sequences), made playable in Cyberpunk: which nodes move, where each
sits in every sequence sampled at RATE frames a second (position + quaternion in the model's space, metres), and
which state is the rest. The importer does this on the player's PC from their own files (FO4_IMPORT.md,
Animations): nothing of it ships.
Sequence names kept (what the game plays: a door's Open / Close, a machine's running On, a trap's Set / Trip...):
PLAY. The rest state (baked into the static mesh, and where the moving parts start): the first of REST present.
"""
import math

RATE = 15
PLAY = ['Open', 'Close', 'On', 'Off', 'TurningOn', 'TurningOff', 'Set', 'Arm', 'TripTransition', 'Tripped',
        'SetTransitionFromTripped', 'Trip', 'Idle', 'Fire', 'Held']
REST = ['On', 'Close', 'Set', 'Idle', 'Off', 'Held']


# parts Fallout spins from its Havok behaviour graph (no keys in the model): node name -> (axis in the node's frame,
# seconds a turn)
SPIN = {'fanblades': ((0, 0, 1), 1.2)}


# parts Fallout moves by script, not by any sequence (an elevator's car): each a part of its own, still - the mod
# moves it (modules/elevator.lua). The node's name
CARRIED = ('Car01',)


def still(rest_t, frame=1.0 / RATE):
    """a track that holds a node where it is (two keys: a part is what a sequence gives more than one key)"""
    return dict(pose=None, euler=None, rot=[], scale=[], trans=[(0.0, tuple(rest_t)), (frame, tuple(rest_t))])


# a turret's head: turns side to side about the vertical (degrees either way, seconds a sweep there and back)
SWEEP = {'BODY': (35.0, 9.0)}


def sweep(rest_q, axis, amp, period, steps=24):
    """a looping track turning a node amp degrees either way about axis and back, smoothly, each period"""
    return dict(pose=None, euler=None, trans=[], scale=[],
                rot=[(period * i / steps, qmul(rest_q, qaxis(axis, math.radians(amp) * math.sin(2 * math.pi * i / steps)))) for i in range(steps + 1)])


def spin(rest_q, axis, period, steps=8):
    """a looping track turning a node once about axis each period (keys under half a turn apart, for slerp)"""
    return dict(pose=None, euler=None, trans=[], scale=[],
                rot=[(period * i / steps, qmul(rest_q, qaxis(axis, 2 * math.pi * i / steps))) for i in range(steps + 1)])


def qmul(a, b):                                          # (w, x, y, z)
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def qaxis(axis, ang):
    s = math.sin(ang / 2)
    return (math.cos(ang / 2), axis[0] * s, axis[1] * s, axis[2] * s)


def slerp(a, b, t):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0: b, d = tuple(-x for x in b), -d
    if d > 0.9995:
        q = tuple(x + (y - x) * t for x, y in zip(a, b))
    else:
        th = math.acos(d); s = math.sin(th)
        q = tuple((x * math.sin((1 - t) * th) + y * math.sin(t * th)) / s for x, y in zip(a, b))
    n = math.sqrt(sum(x * x for x in q)) or 1
    return tuple(x / n for x in q)


def matq(m):                                             # 3x3 (orthonormal) -> (w, x, y, z)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1) * 2
        q = (0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s)
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = ((m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s)
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = ((m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s)
    else:
        s = math.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = ((m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s)
    n = math.sqrt(sum(x * x for x in q)) or 1
    return tuple(x / n for x in q)


def _lerp_keys(keys, t):
    """linear through (time, value) keys, value a number or a tuple; held at the ends"""
    if not keys: return None
    if t <= keys[0][0]: return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0
            return v0 + (v1 - v0) * f if not isinstance(v0, tuple) else tuple(a + (b - a) * f for a, b in zip(v0, v1))
    return keys[-1][1]


def local_at(track, rest, t):
    """a node's local transform (translation, quaternion, scale) at time t: its track's keys where it has them, else
    the track's own pose, else the node's rest transform"""
    rt, rq, rs = rest
    pose = track.get('pose')
    tt, tq, ts = pose if pose else (rt, rq, rs)
    v = _lerp_keys(track.get('trans') or [], t)
    if v is not None: tt = v
    if track.get('rot'):
        keys = track['rot']
        if t <= keys[0][0]: tq = keys[0][1]
        elif t >= keys[-1][0]: tq = keys[-1][1]
        else:
            for (t0, q0), (t1, q1) in zip(keys, keys[1:]):
                if t <= t1: tq = slerp(q0, q1, (t - t0) / (t1 - t0) if t1 > t0 else 0); break
    elif track.get('euler'):                             # XYZ keys (radians): X first, then Y, then Z
        ax = [_lerp_keys(k, t) if k else 0.0 for k in track['euler']]
        tq = qmul(qaxis((0, 0, 1), ax[2] or 0), qmul(qaxis((0, 1, 0), ax[1] or 0), qaxis((1, 0, 0), ax[0] or 0)))
    v = _lerp_keys(track.get('scale') or [], t)
    if v is not None: ts = v
    return tt, tq, ts


def moving(seqs):
    """the nodes some kept sequence really moves (keys that change, or a pose)"""
    out = set()
    for name, s in seqs.items():
        if name not in PLAY: continue
        for node, tr in s['tracks'].items():
            if len(tr.get('rot') or []) > 1 or len(tr.get('trans') or []) > 1 or len(tr.get('scale') or []) > 1 or \
               (tr.get('euler') and any(len(k) > 1 for k in tr['euler'])):
                out.add(node)
    return out


def rest_state(seqs):
    return next((n for n in REST if n in seqs), None)


def rest_time(seq):                                       # a transition ends in its state; a loop: its start
    return seq['start'] if seq['cycle'] == 0 else seq['stop']
