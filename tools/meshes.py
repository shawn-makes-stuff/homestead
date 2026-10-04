"""Fetch game meshes into the work folder's meshes\ (ours: source\meshes): raw .mesh, .mesh.json (bounds, appearances)
and .glb (geometry), with the game and WolvenKit paths.py finds.

usage: python tools/meshes.py <name-or-depot-path> ...     (names are matched as ...\\<name>.mesh)
Cached: a mesh already there is skipped.
"""
import os, re, subprocess, sys, glob, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
OUT = os.path.join(paths.work(), 'meshes')


def cli(*a):                                                 # (found here, not at import: the player's importer imports this)
    return subprocess.run([paths.get('wolvenkit'), *a], env=paths.wk_env(MeshExportArgs__WithMaterials='false'), capture_output=True, text=True)


def find(name):
    """Local .mesh path for a mesh name, or None."""
    hits = glob.glob(os.path.join(OUT, '**', name + '.mesh'), recursive=True)
    return hits[0] if hits else None


def fetch(names):
    names = [n.replace('/', '\\').split('\\')[-1].removesuffix('.mesh') for n in names]
    todo = [n for n in names if not find(n) or not os.path.exists(find(n) + '.json') or not os.path.exists(find(n)[:-5] + '.glb')]
    if not todo:
        return
    os.makedirs(OUT, exist_ok=True)
    rx = r'\\(' + '|'.join(re.escape(n) for n in todo) + r')\.mesh$'
    game = paths.get('cp2077')
    arch = os.path.join(game, 'archive', 'pc')
    cli('extract', os.path.join(arch, 'content'), os.path.join(arch, 'ep1'), '-r', rx, '-o', OUT)
    cli('uncook', os.path.join(arch, 'content'), os.path.join(arch, 'ep1'), '-r', rx, '-o', OUT, '--gamepath', game)
    for n in todo:
        p = find(n)
        if not p:
            print('NOT FOUND', n); continue
        cli('convert', 'serialize', p, '-o', os.path.dirname(p))
        print('ok', n, os.path.exists(p + '.json'), os.path.exists(p[:-5] + '.glb'))


def info(name):
    """(bounds min, max, appearances, depot path) from the .mesh.json."""
    p = find(name)
    r = json.load(open(p + '.json', encoding='utf-8-sig'))['Data']['RootChunk']
    b = r['boundingBox']
    apps = [a['Data']['name']['$value'] for a in r.get('appearances', []) if a.get('Data')]
    depot = os.path.relpath(p, OUT).replace('/', '\\')
    return [b['Min'][k] for k in 'XYZ'], [b['Max'][k] for k in 'XYZ'], apps, depot


if __name__ == '__main__':
    fetch(sys.argv[1:])
