"""Cyberpunk's own workspots that placed people use (modules/life.lua's BODY sets and the animations of
modules/own/poses.lua), copied to homestead\\workspots\\ with
their idle sequences looping. The game's play their sequence once and get up - its AI sends its people back, and a jump
back in goes through a way out and a way in (they stand up, then lie down again). The cat's already loop; the chicken's
and the iguana's are made here too (ANIMALS, homestead\\workspots\\animals\\). Their ways
out don't snap the body down onto the navmesh (forceNoZSnap): on our floors it runs under them.
Reads the player's game (base\\workspots\\common\\...), writes source/json/homestead/workspots/<folder>/<name>.workspot.json;
tools/import.py packs them.
"""
import json, os, re, shutil
import paths                                                  # (where the game and WolvenKit are)

OUT = os.path.join(paths.work(), 'json', 'homestead', 'workspots')
LIFE = [os.path.join(paths.mod_cet(), 'modules', f) for f in ('life.lua', os.path.join('own', 'poses.lua'))]


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


# Animals with one animation and no looping workspot in the game (life.lua's "animals\\<name>": its PET sets). The
# chicken's own workspot (base\workspots\animals\chicken) plays once: copied looping like the people's. The iguana has
# none that stands alone (its quest one names no animation set: the scene brings it), so its is the chicken's file
# around the iguana's rig and its terrarium idle of 20 s (rig, animation set, animation). The cow: no animation set in
# the game is made for its rig (every .anims but the people's own read, 2026-10-06) - nothing to make one from.
CHICKEN = 'chicken__stand_ground__stand_around__01'
ANIMALS = {CHICKEN: None,
           'iguana__sit_ground__sit_around__01': (
               'base\\characters\\common\\base_bodies\\animals\\iguana\\skeleton.rig',
               'base\\animations\\quest\\main_quests\\prologue\\q005\\q005_07_vip_apartament\\q005_07_vip_apartament__iguana_animation.anims',
               'q005_07_vip_apartament__iguana_terrarium_idle')}


def setup_hash(sets):                    # animAnimSetup.hash, as the game's files have it (the chicken's and the cats'
    M, P, h = (1 << 64) - 1, 1099511628211, 1099511628211    # workspots give theirs; none: the prime alone)
    for path, priority in sets:
        f = 14695981039346656037                             # (the path as the game hashes one: FNV-1a 64)
        for c in path.encode(): f = ((f ^ c) * P) & M
        h = ((((h ^ f) * P) & M) ^ priority) * P & M
    return h


def pet(d, rig, anims, anim):            # the chicken's workspot -> one animation of another animal, played on and on
    t = D(d['Data']['RootChunk']['workspotTree'])            # (as the game's cat__sit__01 is built: a sequence whose
    (a,) = t['finalAnimsets']                                # idle is its one clip)
    (e,), (h,) = a['animations']['cinematics'], a['loadingHandles']
    assert not a['animations']['gameplay']
    e['animSet']['DepotPath']['$value'] = h['DepotPath']['$value'] = anims
    a['rig']['DepotPath']['$value'] = rig
    a['animations']['hash'] = str(setup_hash([(anims, e['priority'])]))
    (seq,) = D(t['rootEntry'])['list']
    (many,) = D(seq)['list']
    clip = next(c for c in D(many)['list'] if D(c)['$type'] == 'workAnimClip')
    clip['HandleId'] = many['HandleId']                      # (handles stay numbered in order)
    D(seq)['idleAnim']['$value'] = D(clip)['animName']['$value'] = anim
    D(seq)['list'] = [clip]


def main():
    names = sorted(set(re.findall(r'"([a-z_]+)\\\\([a-z0-9_]+__[a-z0-9_]+)"', ''.join(open(f, encoding='utf-8').read() for f in LIFE if os.path.exists(f)))))   # (folder, name); '@' ones are base's
    rx = r'base.workspots.(common.(%s)|animals.chicken.%s)\.workspot$' % (
        '|'.join(re.escape(f + '\\' + n).replace('\\\\', '.') for f, n in names if f != 'animals'), CHICKEN)
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
            src = made.get((CHICKEN if f == 'animals' else n) + '.workspot.json')
            if not src or (f == 'animals' and n not in ANIMALS): print('not in the game:', f, n); continue
            d = json.load(open(src, encoding='utf-8-sig'))
            if f == 'animals' and ANIMALS[n]:
                try: pet(d, *ANIMALS[n])
                except (AssertionError, KeyError, ValueError, StopIteration) as e:   # (not the file this was written for)
                    print('not made:', f, n, repr(e)); continue
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
