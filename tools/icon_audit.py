"""The menu icons audited from the atlas pixels (tools/make_thumbs.py's PNGs) and the render metadata: every shown
catalog row -> its cell's alpha coverage, brightness, colour spread and how much of it has a texture.
  none         a shown row with no icon          blank    a cell with (almost) nothing in it
  tiny         under 3% covered, under half across     dark     what is there is near black
  untextured   a material with no texture (clay grey) over half the item, or all of it grey by its pixels
usage: python tools/icon_audit.py [out.md] [--sheets <dir>]    (--sheets: a contact sheet per category and cause)
"""
import collections, json, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fo4'))
import paths

W = paths.work()
CELL, BG = 128, np.array([40, 40, 44], np.float32) / 255
CAUSES = ['none', 'blank', 'tiny', 'dark', 'untextured']


def rows():
    out = []
    for l in open(os.path.join(paths.ROOT, paths.CET, 'catalog.lua'), encoding='utf-8'):
        if 'items[#items + 1]' not in l: continue
        r = dict(re.findall(r'(\w+) = "([^"]*)"', l))
        r.update({k: True for k in re.findall(r'(\w+) = true', l)})
        out.append(r)
    return out


def kind(r):
    k, g = r['key'], r.get('group', '')
    if r.get('npc'): return 'People'
    if k.startswith('fo4_pa_'): return 'Power armour'
    if re.search(r'marquee', k + g, re.I): return 'Marquee letters'
    if re.search(r'sign|neon|billboard|poster|advert', k + g, re.I): return 'Signs and neon'
    if 'Weapons' in g or r['cat'] == 'Weapons': return 'Weapons'
    if re.search(r'prefab', k + g, re.I): return 'Prefabs and buildings'
    return 'Fallout' if r.get('fo4') else 'Night City'


def textured():
    """{key: share of the item's materials that have a texture}"""
    from make_thumbs import TEX, NC
    nc = json.load(open(NC)) if os.path.exists(NC) else {}
    p, out = os.path.join(W, 'thumb_items.json'), {}
    for key, parts, mats, _ in json.load(open(p)) if os.path.exists(p) else []:
        have = n = 0
        for g in {q[0] for q in parts}:
            if mats.get(g):
                fs = [not t or os.path.exists(os.path.join(TEX, t.replace('\\', '_').replace('/', '_')[:150] + '.png')) for t, *_ in mats[g].values()]
                have += sum(fs); n += len(fs)
            elif nc.get(g): have += len(nc[g]); n += len(nc[g])
            else: n += 1
        out[key] = have / max(n, 1)
    return out


def cells():
    """{key: the cell, RGBA float (premultiplied, as packed)}"""
    out = {}
    for a, parts in json.load(open(os.path.join(W, 'thumbs.json'))).items():
        im = np.asarray(Image.open(os.path.join(W, 'raw', 'homestead', 'ui', 'thumbs_%s.png' % a)).convert('RGBA'), np.float32) / 255
        n = im.shape[0]
        for k, (l, t, r, b) in parts.items():
            out[k] = im[round(t * n):round(b * n), round(l * n):round(r * n)]
    return out


def measure(c):
    a = c[..., 3]
    m = a > 0.1
    cov = float(m.mean())
    if cov < 0.002: return dict(cov=cov, lum=0, sat=0, span=0)
    ys, xs = np.nonzero(m)
    span = max(np.ptp(ys), np.ptp(xs)) / CELL
    rgb = c[..., :3][m] / a[m][:, None]
    return dict(cov=cov, span=float(span), lum=float((rgb @ np.array([0.299, 0.587, 0.114], np.float32)).mean()), sat=float((rgb.max(1) - rgb.min(1)).mean()))


def audit():
    tx, cs, res = textured(), cells(), []
    for r in rows():
        k, why = r['key'], []
        if r.get('hidden') or r.get('stashed') or r['cat'] == 'Zone': continue
        if 'thumb' not in r or k not in cs: res.append((r, ['none'], None)); continue
        m = measure(cs[k])
        if m['cov'] < 0.002: why.append('blank')
        elif m['cov'] < 0.03 and m['span'] < 0.5: why.append('tiny')   # (a pole fills little, but spans its cell)
        if m['cov'] >= 0.002 and m['lum'] < 0.07: why.append('dark')
        if tx.get(k, 1) < 0.5 or (m['cov'] >= 0.002 and m['sat'] < 0.012 and 0.3 < m['lum'] < 0.8 and tx.get(k, 1) < 1):
            why.append('untextured')
        res.append((r, why, m))
    return res, cs


def sheet(keys, cs, path, cols=16):
    im = Image.new('RGB', (cols * CELL, -(-len(keys) // cols) * (CELL + 12)), (40, 40, 44))
    d = ImageDraw.Draw(im)
    for i, k in enumerate(keys):
        x, y = (i % cols) * CELL, (i // cols) * (CELL + 12)
        if k in cs:
            c = cs[k]
            im.paste(Image.fromarray((np.clip(c[..., :3] + (1 - c[..., 3:4]) * BG, 0, 1) * 255).astype(np.uint8)), (x, y))
        d.text((x + 1, y + CELL), re.sub(r'^(fo4|h|npc)_', '', k)[:21], fill=(200, 200, 200))
    im.save(path)


def main():
    res, cs = audit()
    tot, bad = collections.Counter(kind(r) for r, _, _ in res), collections.Counter((kind(r), w) for r, why, _ in res for w in why)
    lines = ['| category | shown | ' + ' | '.join(CAUSES) + ' | any |', '|---|---|' + '---|' * (len(CAUSES) + 1)]
    for c in sorted(tot) + ['all']:
        hit = lambda r: c in ('all', kind(r))
        lines.append('| %s | %d | %s | %d |' % (c, sum(1 for r, _, _ in res if hit(r)),
                                                 ' | '.join(str(sum(1 for r, why, _ in res if hit(r) and w in why)) for w in CAUSES),
                                                 sum(1 for r, why, _ in res if hit(r) and why)))
    print('\n'.join(lines))
    args = sys.argv[1:]
    if '--sheets' in args:
        d = args.pop(args.index('--sheets') + 1); args.remove('--sheets')
        os.makedirs(d, exist_ok=True)
        by = collections.defaultdict(list)
        for r, why, m in res:
            by[kind(r)].append(r['key'])
            for w in why: by['bad_' + w].append(r['key'])
        for name, keys in by.items():
            for p in range(0, len(keys), 640):
                sheet(keys[p:p + 640], cs, os.path.join(d, re.sub(r'\W+', '_', name) + ('_%d' % (p // 640 + 1) if len(keys) > 640 else '') + '.png'))
    if args:
        with open(args[0], 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines) + '\n\n')
            for w in CAUSES:
                ks = sorted((kind(r), r['key'], m) for r, why, m in res if w in why)
                f.write('## %s (%d)\n\n' % (w, len(ks)))
                for c, k, m in ks:
                    f.write('- %s: %s%s\n' % (c, k, ' (cov %.3f lum %.2f sat %.3f)' % (m['cov'], m['lum'], m['sat']) if m else ''))
                f.write('\n')


if __name__ == '__main__':
    main()
