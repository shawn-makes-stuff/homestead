"""Cyberpunk's own workspots that placed people use (modules/life.lua's BODY sets), copied to homestead\\workspots\\ with
their idle sequences looping. The game's play their sequence once and get up - its AI sends its people back, and a jump
back in goes through a way out and a way in (they stand up, then lie down again). The cat's already loop. Their ways
out don't snap the body down onto the navmesh (forceNoZSnap): on our floors it runs under them.
Reads the player's game (base\\workspots\\common\\...), writes source/json/homestead/workspots/<folder>/<name>.workspot.json;
tools/import.py packs them.
"""
import json, os, re, shutil
import paths                                                  # (where the game and WolvenKit are)

OUT = os.path.join(paths.work(), 'json', 'homestead', 'workspots')
LIFE = os.path.join(paths.mod_cet(), 'modules', 'life.lua')


def D(o): return o.get('Data', o) if isinstance(o, dict) else o


def loop(root):                          # every sequence of its own (not a reaction's): played on until they're sent off
    n = 0
    for c in root.get('list', []):
        c = D(c)
        if c.get('$type') in ('workSequence', 'workConditionalSequence'):
            c['loopInfinitely'] = 1; n += 1
            for s in c.get('list', []):
                s = D(s)
                if s.get('$type') == 'workSequence': s['loopInfinitely'] = 1; n += 1
    return n


def no_snap(o):                          # every way out: no snap down onto the navmesh at the end (on our floors it runs
    n = 0                                # under them - the exit dropped people through; modules/life.lua holds the height)
    if isinstance(o, dict):
        if o.get('$type') == 'workExitAnim': o['forceNoZSnap'], o['snapZToNavmesh'], o['stayOnNavmesh'], n = 1, 0, 0, 1
        for v in o.values(): n += no_snap(v)
    elif isinstance(o, list):
        for v in o: n += no_snap(v)
    return n


def main():
    names = sorted(set(re.findall(r'"([a-z_]+)\\\\([a-z0-9_]+__[a-z0-9_]+)"', open(LIFE, encoding='utf-8').read())))   # (folder, name); '@' ones are base's
    rx = r'base.workspots.common.(%s)\.workspot$' % '|'.join(re.escape(f + '\\' + n).replace('\\\\', '.') for f, n in names)
    with paths.scratch('workspots') as tmp:
        paths.wk(['unbundle', '-p', paths.cp_content(), '-o', tmp, '-r', rx], expect=[os.path.join(tmp, 'base')],
                 what="unpack the game's workspots")
        js = os.path.join(tmp, 'json')
        os.makedirs(js)                                      # (WolvenKit: "Invalid output directory" if it isn't there)
        paths.wk(['convert', 'serialize', os.path.join(tmp, 'base'), '-o', js], expect=[os.path.join(js, '**', '*.workspot.json')],
                 what="read the game's workspots")           # (all in one run)
        made = {f: os.path.join(d, f) for d, _, fs in os.walk(js) for f in fs}   # (WolvenKit keeps the folders)
        shutil.rmtree(OUT, ignore_errors=True)
        done = 0
        for f, n in names:
            src = made.get(n + '.workspot.json')
            if not src: print('not in the game:', f, n); continue
            d = json.load(open(src, encoding='utf-8-sig'))
            if not loop(D(D(d['Data']['RootChunk']['workspotTree'])['rootEntry'])): print('no sequence to loop:', f, n); continue
            no_snap(d['Data']['RootChunk']['workspotTree'])
            os.makedirs(os.path.join(OUT, f), exist_ok=True)
            json.dump(d, open(os.path.join(OUT, f, n + '.workspot.json'), 'w', encoding='utf-8'), indent=1)
            done += 1
    print('workspots: %d of %d looped' % (done, len(names)))
    if done < len(names) * 0.9:                              # (people would sit once and get up: not an import to install)
        raise SystemExit('only %d of %d workspots made - WolvenKit could not read the game?' % (done, len(names)))


if __name__ == '__main__':
    main()
