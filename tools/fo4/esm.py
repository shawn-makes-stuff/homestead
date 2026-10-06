"""Fallout 4 masters (.esm): the records a workshop importer needs, from the top-level groups only. FormIDs become
(master file, object id), so nothing depends on load order; names come from the localized STRINGS in the archives.
Layout: FO4_RESEARCH.md, section 3 (xEdit wbDefinitionsFO4.pas).
  python tools/fo4/esm.py        the workshop menu tree with recipe counts
"""
import mmap, os, struct, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (tools/: paths.py)
import paths
import ba2

DATA = paths.get('fo4', required=False)                     # (None: Fallout's half is off - import.py check() asks for it when wanted)
MASTERS = ['Fallout4.esm', 'DLCRobot.esm', 'DLCworkshop01.esm', 'DLCCoast.esm', 'DLCworkshop02.esm', 'DLCworkshop03.esm', 'DLCNukaWorld.esm']
WANT = {b'KYWD', b'FLST', b'COBJ', b'STAT', b'SCOL', b'MSTT', b'DOOR', b'LIGH', b'ACTI', b'FURN', b'CONT', b'TERM', b'FLOR',
        b'TREE', b'MISC', b'CMPO', b'SNDR', b'ARTO', b'AVIF', b'ADDN', b'BOOK', b'MSWP',
        b'NPC_', b'RACE', b'ARMO', b'ARMA'}                     # (turrets: actors, their model on their race's skin)


def subrecords(data):
    out, o, big = [], 0, None
    while o + 6 <= len(data):
        t, n = struct.unpack_from('<4sH', data, o)
        o += 6
        if t == b'XXXX':
            big, = struct.unpack_from('<I', data, o); o += n; continue
        if big is not None: n, big = big, None
        out.append((t.decode('latin1'), data[o:o + n]))
        o += n
    return out


class Plugin:
    def __init__(self, name, data=DATA):
        self.name = name
        f = open(os.path.join(data, name), 'rb')
        self.m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        typ, size, flags, _fid = struct.unpack_from('<4sIII', self.m, 0)
        assert typ == b'TES4'
        self.localized = bool(flags & 0x80)
        self.masters = [d.rstrip(b'\0').decode() for t, d in subrecords(self.m[24:24 + size]) if t == 'MAST']
        self.records = {}                                      # (master, object id) -> (type, [subrecords])
        o = 24 + size
        while o < len(self.m):
            _g, gsize, label, gtype = struct.unpack_from('<4sI4si', self.m, o)
            if gtype == 0 and label in WANT: self._group(o + 24, o + gsize)
            o += gsize

    def key(self, fid):                                        # a FormID in this plugin -> (master file, object id)
        i = fid >> 24
        return (self.masters[i] if i < len(self.masters) else self.name, fid & 0xFFFFFF)

    def _group(self, o, end):
        while o < end:
            typ, size, flags, fid = struct.unpack_from('<4sIII', self.m, o)
            if typ == b'GRUP':                                  # (not in these types, but skip safely)
                o += size; continue
            data = self.m[o + 24:o + 24 + size]
            if flags & 0x40000: data = zlib.decompress(data[4:])
            if not flags & 0x20: self.records[self.key(fid)] = (typ.decode(), subrecords(data))
            o += 24 + size


class Strings:
    """<plugin>_en.STRINGS from the plugin's archive (Fallout4: Interface.ba2; DLCs: their Main.ba2)"""
    def __init__(self, data=DATA):
        self.t = {}
        for p in MASTERS:
            stem = p[:-4].lower()
            arc = os.path.join(data, 'Fallout4 - Interface.ba2' if stem == 'fallout4' else p[:-4] + ' - Main.ba2')
            if not os.path.exists(arc): continue             # (a DLC the player hasn't got)
            a = ba2.Archive(arc)
            n = 'strings\\%s_en.strings' % stem
            if n not in a.index:                             # (a Fallout 4 in another language: its own names)
                n = next((k for k in a.index if k.startswith('strings\\%s_' % stem) and k.endswith('.strings')), n)
            if n in a.index: self.t[p] = self._parse(a.read(n))

    @staticmethod
    def _parse(b):
        count, size = struct.unpack_from('<II', b, 0)
        base, out = 8 + count * 8, {}
        for i in range(count):
            sid, off = struct.unpack_from('<II', b, 8 + i * 8)
            s = base + off
            out[sid] = b[s:b.index(b'\0', s)].decode('utf-8', 'replace')
        return out

    def get(self, plugin, sid): return self.t.get(plugin, {}).get(sid)


class Game:
    """all masters, later ones overriding earlier records (their load order)"""
    def __init__(self, data=DATA):
        self.plugins = [Plugin(p, data) for p in MASTERS if os.path.exists(os.path.join(data, p))]
        self.rec, self.src = {}, {}
        for p in self.plugins:
            for k, v in p.records.items(): self.rec[k], self.src[k] = v, p
        self.strings = Strings(data)
        self.byEdid = {self.edid(k): k for k in self.rec}

    def field(self, k, name):
        for t, d in self.rec[k][1]:
            if t == name: return d

    def fields(self, k, name): return [d for t, d in self.rec[k][1] if t == name]

    def edid(self, k):
        d = self.field(k, 'EDID')
        return d.rstrip(b'\0').decode('latin1') if d else None

    def full(self, k):
        d = self.field(k, 'FULL')
        if not d: return None
        p = self.src[k]
        if p.localized: return self.strings.get(k[0], struct.unpack('<I', d[:4])[0]) or self.strings.get(p.name, struct.unpack('<I', d[:4])[0])
        return d.rstrip(b'\0').decode('cp1252')

    def ref(self, k, fid): return self.src[k].key(fid)


def menu_paths(g):
    """recipe-filter keyword -> its folder path in the workshop menu (['Structures', 'Wood', 'Floors'])"""
    out = {}
    def walk(k, path, seen):
        if k in seen or k not in g.rec: return
        seen.add(k)
        t = g.rec[k][0]
        if t == 'FLST':
            ents = [g.ref(k, struct.unpack('<I', d)[0]) for d in g.fields(k, 'LNAM')]
            named = ents and ents[0] in g.rec and g.rec[ents[0]][0] == 'KYWD'
            here = path + [g.full(ents[0])] if named and path is not None else (path or [])
            for e in (ents[1:] if named and path is not None else ents): walk(e, here, seen)
        elif t == 'KYWD':
            out[k] = path + [g.full(k)]
    walk(g.byEdid['WorkshopMenuMain'], None, set())
    return out


def menu(g):
    """WorkshopMenuMain as a tree: FLST -> submenu (named by its first entry, a keyword), KYWD -> leaf of recipes"""
    recipes = {}
    for k, (t, _) in g.rec.items():
        if t != 'COBJ': continue
        fn = g.field(k, 'FNAM')
        if fn:
            for i in range(0, len(fn), 4): recipes.setdefault(g.ref(k, struct.unpack_from('<I', fn, i)[0]), []).append(k)
    def walk(k, depth, seen):
        if k in seen or k not in g.rec: return
        seen.add(k)
        t = g.rec[k][0]
        if t == 'FLST':
            ents = [g.ref(k, struct.unpack('<I', d)[0]) for d in g.fields(k, 'LNAM')]
            name = g.full(ents[0]) if ents and ents[0] in g.rec and g.rec[ents[0]][0] == 'KYWD' else g.edid(k)
            print('%s%s  [%s]' % ('  ' * depth, name, g.edid(k)))
            for e in ents[1:] if ents and g.rec.get(ents[0], ('',))[0] == 'KYWD' and depth else ents: walk(e, depth + 1, seen)
        elif t == 'KYWD':
            print('%s- %s: %d recipes  [%s]' % ('  ' * depth, g.full(k), len(recipes.get(k, [])), g.edid(k)))
    walk(g.byEdid['WorkshopMenuMain'], 0, set())
    return recipes


if __name__ == '__main__':
    g = Game()
    print({p.name: (len(p.records), p.localized, p.masters) for p in g.plugins})
    menu(g)
