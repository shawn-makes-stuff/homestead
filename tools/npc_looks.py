"""What every placeable person looks like, for their menu icon (dev time; tools/make_thumbs.py renders it): the
Character record's entity template (the game's tweakdb.bin: <record>.entityTemplatePath, .appearanceName), that
template's appearance (the record's, else its default, else its first), and that appearance's cooked components in
its .app - each mesh, its look and its chunk mask (the body's parts hidden under the clothes). Reads the player's
game through WolvenKit; writes <work>/survey/people_looks.json: {record: [[mesh, look, chunk mask], ...]}.
  python tools/npc_looks.py
"""
import glob, json, os, re, struct, zlib
import paths
from make_weapons import BATCH, D, depot, unbundle, val

OUT = os.path.join(paths.work(), 'survey', 'people_looks.json')
SKIP = re.compile(r'shadow|proxy|fpp|_cutout|vfx', re.I)     # (not the person: shadow casters, the far-off stand-in)


def fnv(s):
    h = 0xCBF29CE484222325
    for c in s.encode(): h = ((h ^ c) * 0x100000001B3) & (2 ** 64 - 1)
    return h


def flats(b, want):
    """tweakdb.bin's flats of the types in want ({type name: 'res' or 'name'}) -> {TweakDBID: value}. The flats' table:
    a count, then per type its hash (FNV1a64 of its name), value count, key count, offset; at the offset the values
    (a count; a resource: its path's hash, a CName: a length byte - 0x40: one more - and the text), then the keys
    (a count; id, index of its value)"""
    fo = struct.unpack_from('<I', b, 16)[0]
    want = {fnv(k): v for k, v in want.items()}
    out = {}
    for i in range(struct.unpack_from('<I', b, fo)[0]):
        h, _, _, o = struct.unpack_from('<QIII', b, fo + 4 + i * 20)
        if h not in want: continue
        vals, n = [], struct.unpack_from('<I', b, o)[0]
        o += 4
        for _ in range(n):
            if want[h] == 'res': vals.append(struct.unpack_from('<Q', b, o)[0]); o += 8
            else:
                l = b[o] & 0x3f; o += 1
                if b[o - 1] & 0x40: l |= b[o] << 6; o += 1
                vals.append(b[o:o + l].decode('utf-8', 'replace')); o += l
        for k in range(struct.unpack_from('<I', b, o)[0]):
            t, ix = struct.unpack_from('<Qi', b, o + 4 + k * 12)
            out[t] = vals[ix]
    return out


def tid(s): return zlib.crc32(s.encode()) | len(s) << 32


def read(tmp, files):
    """the game's files (depot paths) -> {depot path: its root chunk}: unbundled, then serialized next to themselves"""
    files = sorted(set(files))
    for i in range(0, len(files), BATCH):
        unbundle(tmp, '^(%s)$' % '|'.join(re.escape(f).replace(r'\\', '.') for f in files[i:i + BATCH]))
    for top in glob.glob(os.path.join(tmp, '*')):
        if os.path.isdir(top): paths.wk(['convert', 'serialize', top])
    out = {}
    for f in files:
        p = os.path.join(tmp, f + '.json')
        if os.path.exists(p): out[f] = json.load(open(p, encoding='utf-8-sig'))['Data']['RootChunk']
    return out


def meshes(o):                                               # an appearance's, or a template's: [mesh, look, chunk mask]
    return [[depot(c, 'mesh'), val(c, 'meshAppearance') or 'default', int(c.get('chunkMask', 2 ** 64 - 1))]
            for c in map(D, o.get('components') or []) if 'MeshComponent' in c.get('$type', '') and depot(c, 'mesh')
            and not SKIP.search(depot(c, 'mesh') + (val(c, 'name') or ''))]


def main():
    import icon_audit
    records = sorted({r['record'] for r in icon_audit.rows() if r.get('npc')})
    cache = os.path.join(paths.get('cp2077'), 'r6', 'cache')
    b = open(next(p for p in (os.path.join(cache, n) for n in ('tweakdb_ep1.bin', 'tweakdb.bin')) if os.path.exists(p)), 'rb').read()
    F = flats(b, {'CName': 'name', 'raRef:CResource': 'res'})
    ents = {fnv(l): l for l in (l.strip().replace('/', '\\') for l in open(os.path.join(paths.work(), 'survey', 'all_paths.txt'))) if l.endswith('.ent')}
    who = {r: (ents.get(F.get(tid(r + '.entityTemplatePath'))), F.get(tid(r + '.appearanceName'))) for r in records}
    print(len(records), 'people,', sum(1 for e, _ in who.values() if e), 'with a template')
    out = {}
    with paths.scratch('npc_looks') as tmp:
        E = read(os.path.join(tmp, 'ent'), [e for e, _ in who.values() if e])
        pick = {}
        for r, (e, name) in who.items():
            apps = [(val(a, 'name'), depot(a, 'appearanceResource'), val(a, 'appearanceName')) for a in (E.get(e) or {}).get('appearances') or []]
            apps = [a for a in apps if a[1]]
            if not apps:                                     # (no looks: an animal, a machine - the template's own meshes)
                if meshes(E.get(e) or {}): out[r] = meshes(E[e])
                continue
            want = (name, val(E[e], 'defaultAppearance'))
            pick[r] = next((a for w in want for a in apps if a[0] == w), apps[0])
        A = read(os.path.join(tmp, 'app'), [a[1] for a in pick.values()])
        for r, (_, app, look) in pick.items():
            looks = [D(a) for a in (A.get(app) or {}).get('appearances') or []]
            a = next((a for a in looks if val(a, 'name') == look), looks[0] if looks else None)
            if not a: continue
            if meshes(a): out[r] = meshes(a)
    json.dump(out, open(OUT, 'w'), indent=0)
    print(len(out), 'looks,', len({(p[0], p[1]) for v in out.values() for p in v}), 'mesh looks,', len({p[0] for v in out.values() for p in v}), 'meshes;',
          'none for', [r for r in records if r not in out][:40])


if __name__ == '__main__':
    main()
