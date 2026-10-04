"""What drives each workshop object's behaviour: its record type, the Papyrus scripts attached to it (VMAD), its
keywords and workshop actor values (PRPS: power, food, water...), and for doors / lights / activators the sounds and
flags that matter. -> source/fo4/behaviours.json and a summary by record type and script.
  python tools/fo4/probe.py
"""
import collections, json, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import esm
from convert import objects, FO4


def scripts(g, k):
    d = g.field(k, 'VMAD')
    if not d: return []
    return sorted(set(m.decode() for m in re.findall(rb'([A-Za-z][A-Za-z0-9_:]{3,60}Script)', d)))


def keywords(g, k):
    d = g.field(k, 'KWDA')
    if not d: return []
    out = []
    for i in range(0, len(d), 4):
        r = g.ref(k, struct.unpack_from('<I', d, i)[0])
        if r in g.rec: out.append(g.edid(r))
    return out


def values(g, k):
    d = g.field(k, 'PRPS')
    out = {}
    if d:
        for i in range(0, len(d) - 7, 8):
            av, v = struct.unpack_from('<If', d, i)
            r = g.ref(k, av)
            out[g.edid(r) if r in g.rec else hex(av)] = round(v, 2)
    return out


def main():
    g = esm.Game()
    objs = objects(g)
    out = []
    for o in objs:
        k = o['rec']
        out.append(dict(key='fo4_' + (o['edid'] or '').lower(), name=o['name'], kind=o['kind'], menu='/'.join(o['menu']),
                        scripts=scripts(g, k), keywords=keywords(g, k), values=values(g, k)))
    json.dump(out, open(os.path.join(FO4, 'behaviours.json'), 'w'), indent=0)
    by = collections.defaultdict(collections.Counter)
    for b in out:
        for s in b['scripts'] or ['(none)']: by[b['kind']][s] += 1
    for kind, c in sorted(by.items(), key=lambda x: -sum(x[1].values())):
        print('%s (%d objects)' % (kind, sum(1 for b in out if b['kind'] == kind)))
        for s, n in c.most_common(14): print('   %4d %s' % (n, s))
    av = collections.Counter(a for b in out for a in b['values'])
    print('workshop values:', av.most_common(20))


if __name__ == '__main__':
    main()
