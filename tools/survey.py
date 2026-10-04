"""Survey the game's mesh/entity files for catalog candidates. Needs the archive listing:
<work>/scout/alllist.txt ("<archive>|<depot path>" per line; <work>: paths.work(), ours source/ - nothing in the tree
makes it now). Writes <work>/survey/*.txt."""
import collections, os, re, sys
import paths as hpaths
W = hpaths.work()
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(W, 'scout', 'alllist.txt')
rows = [l.rstrip('\n').lstrip('﻿').split('|', 1) for l in open(src, encoding='utf-8-sig') if '|' in l]
paths = sorted(set(p.replace('\\', '/').lower() for a, p in rows))
mesh = [p for p in paths if p.endswith('.mesh')]
print(len(paths), 'files;', len(mesh), 'meshes;', sum(p.endswith('.ent') for p in paths), 'entities')
env = [p for p in mesh if p.startswith(('base/environment/', 'ep1/environment/'))]
print(len(env), 'environment meshes')
c = collections.Counter('/'.join(p.split('/')[1:4]) for p in env)
for k, v in c.most_common(60): print('%6d %s' % (v, k))
out = os.path.join(W, 'survey')
os.makedirs(out, exist_ok=True)
open(os.path.join(out, 'env_meshes.txt'), 'w').write('\n'.join(env))
open(os.path.join(out, 'all_paths.txt'), 'w').write('\n'.join(paths))
