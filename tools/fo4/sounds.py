"""Fallout's own sounds for its pieces, converted at import (nothing ships): a door's open / close (DOOR SNAM / ANAM),
the cues in a piece's sequences (SoundPlay.X / SoundStop.X text keys: a generator starting its hum), the sound of an
add-on effect (a fire's crackle) and a machine's own loop (ACTI SNAM). Each is a sound descriptor (SNDR): its files
(ANAM, one per variant - Fallout picks one at random), whether it loops (LNAM) and its attenuation (BNAM). The files
(.xwm / .wav in Sounds.ba2) become .ogg through ffmpeg, into source/fo4/sfx with Audioware's manifest (tools/import.py
puts it in the game's mods\\Homestead). -> pieces.json: `sounds` {seq: {name: [[t, play, event]]}, hum: [event]} and
source/fo4/sfx/sounds.json {event: {n, loop, vol}}.
  python tools/fo4/sounds.py        (after lights.py; convert.py runs it)
"""
import json, os, struct, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (tools/: paths.py)
import paths
import esm
from convert import Files, objects, FO4

OUT = os.path.join(FO4, 'sfx')
FFMPEG = paths.get('ffmpeg', required=False)                # (none: sounds converted before are kept, the rest left out)
FORCE = '--force' in sys.argv or 'post' in os.environ.get('HOMESTEAD_FORCE', '')   # (this code changed: every .ogg again)


def event(edid): return 'hs_' + edid.lower()


def descriptor(g, k):
    """a SNDR record -> (its sound files in the archives, loops, volume 0-1)"""
    files = []
    for d in g.fields(k, 'ANAM'):
        f = d.rstrip(b'\0').decode('cp1252').lower().replace('/', '\\')
        f = f[5:] if f.startswith('data\\') else f
        files.append(f)
    ln, bn = g.field(k, 'LNAM'), g.field(k, 'BNAM')
    loops = bool(ln and len(ln) > 1 and ln[1])
    att = struct.unpack_from('<H', bn, 4)[0] / 100 if bn and len(bn) >= 6 else 0.0      # static attenuation, dB
    return files, loops, round(max(0.2, 10 ** (-att / 20)), 3)


def one(job):                                               # a file -> .ogg (cached); True when it's there
    _, src, data, dst = job
    if os.path.exists(dst) and not (FORCE and FFMPEG): return True
    if not FFMPEG: return False
    tmp = dst + src[-4:]
    open(tmp, 'wb').write(data)
    r = subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', tmp, '-c:a', 'libvorbis', '-q:a', '4', dst], capture_output=True)
    os.remove(tmp)
    return r.returncode == 0 and os.path.exists(dst)


def patch(g=None, files=None):
    g = g or esm.Game()
    files = files or Files()
    sndr = {g.edid(k).lower(): k for k, (t, _) in g.rec.items() if t == 'SNDR' and g.edid(k)}
    by = {('fo4_' + (o['edid'] or '').lower()): o for o in objects(g)}
    def ref(k, name):
        d = g.field(k, name)
        r = g.ref(k, struct.unpack('<I', d[:4])[0]) if d and len(d) >= 4 else None
        return g.edid(r).lower() if r in g.rec and g.rec[r][0] == 'SNDR' else None
    path = os.path.join(FO4, 'pieces.json')
    pieces = json.load(open(path))
    used = set()
    for p in pieces:
        p.pop('sounds', None)
        o = by.get(p['key'])
        seq, hum = {}, []
        for name, s in (p.get('anim') or {}).get('seqs', {}).items():
            cues = [[t, pl, e.lower()] for t, pl, e in s.get('snd', []) if e.lower() in sndr]
            if cues: seq[name] = cues
        if o and o['kind'] == 'DOOR':                        # a door's open and close
            for name, f in (('Open', 'SNAM'), ('Close', 'ANAM')):
                e = ref(o['rec'], f)
                if e: seq.setdefault(name, []).insert(0, [0.0, 1, e])
        if o and o['kind'] in ('ACTI', 'MSTT'):              # a machine's own loop
            e = ref(o['rec'], 'SNAM')
            if e: hum.append(e)
        for fx in p.get('effects', []):                      # an effect's (a fire's crackle)
            if fx.get('sound') and fx['sound'].lower() in sndr: hum.append(fx['sound'].lower())
        # what runs while it's on, placed that way: the loops its turning-on starts (a generator's hum)
        for name in ('TurningOn', 'PoweringUpOn'):
            hum += [e for t, pl, e in seq.get(name, []) if pl]
        hum = list(dict.fromkeys(hum))
        if seq or hum:
            p['sounds'] = dict(seq={n: [[t, pl, event(e)] for t, pl, e in c] for n, c in seq.items()}, hum=[event(e) for e in hum])
            used |= {e for c in seq.values() for _, _, e in c} | set(hum)
    # the files
    os.makedirs(OUT, exist_ok=True)
    table, jobs = {}, []
    for e in sorted(used):
        fs, loops, vol = descriptor(g, sndr[e])
        n = 0
        for f in fs:
            data = None
            for cand in (f, os.path.splitext(f)[0] + '.xwm', os.path.splitext(f)[0] + '.wav'):      # (named .wav,
                data = files.read(cand)                                                             # stored .xwm)
                if data: break
            if not data: continue
            jobs.append((event(e), f, data, os.path.join(OUT, '%s_%d.ogg' % (event(e), n))))
            n += 1
        if n: table[event(e)] = dict(n=n, loop=loops, vol=vol)
    with ThreadPoolExecutor(8) as ex: ok = list(ex.map(one, jobs))
    bad = [j[1] for j, k in zip(jobs, ok) if not k]
    for j, k in zip(jobs, ok):                               # (a sound with a file missing: left out, not played short)
        if not k: table.pop(j[0], None)
    if bad and not FFMPEG: print("ffmpeg not found: Fallout's sounds not converted before are left out (%d files)" % len(bad))
    with open(os.path.join(OUT, 'homestead.yaml'), 'w') as f:     # Audioware's manifest: one event a file
        f.write('version: 1.0.0\nsfx:\n')
        for e, t in table.items():
            for i in range(t['n']): f.write('  %s_%d: %s_%d.ogg\n' % (e, i, e, i))
    json.dump(table, open(os.path.join(OUT, 'sounds.json'), 'w'), indent=0)
    for p in pieces:                                         # (only what converted)
        s = p.get('sounds')
        if not s: continue
        s['seq'] = {n: [c for c in cs if c[2] in table] for n, cs in s['seq'].items()}
        s['seq'] = {n: cs for n, cs in s['seq'].items() if cs}
        s['hum'] = [e for e in s['hum'] if e in table]
        if not s['seq'] and not s['hum']: p.pop('sounds')
    json.dump(pieces, open(path, 'w'))
    print(sum(1 for p in pieces if p.get('sounds')), 'pieces with sounds,', len(table), 'sounds,', len(jobs), 'files,', len(bad), 'failed', bad[:3])


if __name__ == '__main__':
    patch()
