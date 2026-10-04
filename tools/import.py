"""Homestead's import: everything the mod needs that comes from the player's own games (nothing of Bethesda's or CDPR's
ships), built on their PC and installed into Cyberpunk. A re-run redoes only what changed - its inputs, or the code
that makes them (a hash per step, <work>/fo4/code.json); --force does it all again (the in-game toggle "Overwrite
already imported items").
  python tools/import.py            import (or update) and install into Cyberpunk (close the game first)
  python tools/import.py --check    what was found, nothing done
  python tools/import.py --force    a fresh import
  python tools/import.py --mod-only the mod's own files (Lua, scripts, plugin) into the game, nothing imported (ours)
  HomesteadImport.exe --from-game   (the in-game settings, through the RED4ext plugin): builds while the game runs,
                                    installs once it has closed (its archives are locked while it runs)
Steps: find the games and tools (paths.py) -> Cyberpunk's workspots, looping, its weapons as props and the border's
wall (make_workspots.py, make_weapons.py, make_border.py) -> Fallout 4's models, textures, lights, sounds, furniture and snap points (fo4/convert.py) -> their
game files and archive (fo4/build.py) -> the menu's catalog (build_catalog.py) -> Homestead.archive (our templates,
workspots, weapons) -> install. The import's data is in paths.work() (a player's: the CET mod's import folder, or the
in-game settings' importDir); a log there (fo4/import.log); how it's going in the CET mod's import_status.txt.
"""
import hashlib, json, multiprocessing, os, shutil, subprocess, sys, threading, time

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS); sys.path.insert(0, os.path.join(TOOLS, 'fo4'))
import paths

WORK = paths.work()
FO4 = os.path.join(WORK, 'fo4')
JSON = os.path.join(WORK, 'json')
CET = paths.CET
MOD_ARCHIVE = os.path.join(FO4, 'Homestead.archive')
MASTERS = [('Fallout4.esm', 'Fallout 4'), ('DLCRobot.esm', 'Automatron'), ('DLCworkshop01.esm', 'Wasteland Workshop'),
           ('DLCCoast.esm', 'Far Harbor'), ('DLCworkshop02.esm', 'Contraptions Workshop'),
           ('DLCworkshop03.esm', 'Vault-Tec Workshop'), ('DLCNukaWorld.esm', 'Nuka-World')]
T, F = TOOLS, os.path.join(TOOLS, 'fo4')
CODE = {                                                     # what a step's output depends on: any change redoes it
    'workspots': [os.path.join(T, 'make_workspots.py'), os.path.join(paths.mod_cet(), 'modules', 'life.lua')],
    'weapons': [os.path.join(T, 'make_weapons.py'), os.path.join(T, 'make_ent.py')],   # (weapons.ent is empty.ent's copy)
    'border': [os.path.join(T, 'make_border.py')],          # (the settlement border's mesh: its shape and its look)
    # the converted models: what model() runs (budget.py only sizes the pool: no output of its own)
    'convert': [os.path.join(F, f) for f in ('convert.py', 'nif.py', 'havok.py', 'bgsm.py', 'anim.py', 'ba2.py', 'esm.py')],
    'collision': [os.path.join(T, 'colliders.py')],          # (boxes from the shapes each model saved: convert.py collision)
    # run on every import over all pieces anyway; a change here only redoes what they cache (the .ogg sounds)
    'post': [os.path.join(F, f) for f in ('lights.py', 'sounds.py', 'furniture.py')],
    'xbm': [os.path.join(F, 'xbm.py')],
    'build': [os.path.join(F, 'build.py')],
}
codehash = None                                              # the frozen importer has no .py files to read: its steps'
if paths.FROZEN: import codehash                             # hashes were made when it was built (tools/release.py)


def log_file(name):
    """an append-only log in fo4\\ - begun afresh once over 4 MB (the one before kept as <name>.old)"""
    os.makedirs(FO4, exist_ok=True)
    p = os.path.join(FO4, name)
    if os.path.exists(p) and os.path.getsize(p) > 4e6: os.replace(p, p + '.old')
    return open(p, 'a', encoding='utf-8', buffering=1)


class Log:
    def __init__(self):
        self.f = log_file('import.log')
    def __call__(self, *a):
        line = ' '.join(str(x) for x in a)
        print(line, flush=True)
        self.f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + line + '\n'); self.f.flush()


class Status:
    """how the import is going, for the in-game settings: "key=value" lines in the CET mod's import_status.txt (the one
    folder CET's Lua may read), written whole each time"""
    def __init__(self):
        self.path = os.path.join(paths.game_cet(), 'import_status.txt') if paths.get('cp2077', required=False) else None
        self.d = {'work': WORK}
    def __call__(self, **kw):
        self.d.update({k: str(v) for k, v in kw.items()})
        if not self.path or not os.path.isdir(os.path.dirname(self.path)): return
        tmp = self.path + '.tmp'
        # the game reads it once a second (the settings page): while it has it open, Windows refuses the swap ("Access
        # is denied" - that once failed a whole import, 2026-10-02). Tried again a moment later; news of how far it
        # got can wait for the next one, an end (done, failed, waiting) is tried for up to 10 s. Never fails the import
        end = kw.get('state') in ('done', 'failed', 'waiting', 'found')
        for _ in range(200 if end else 10):
            try:
                with open(tmp, 'w', encoding='utf-8') as f:
                    for k, v in self.d.items(): f.write('%s=%s\n' % (k, v.replace('\n', ' ')))
                os.replace(tmp, self.path)
                return
            except OSError:
                time.sleep(0.05)


def meaning(path):
    """what in a file can change a step's output: a .py's code (its syntax tree without comments and docstrings - a
    comment edited redoes nothing); life.lua: only the workspots it names (make_workspots.py copies those)"""
    src = open(path, encoding='utf-8').read()
    if path.endswith('.lua'):
        import re
        return repr(sorted(set(re.findall(r'"([a-z_]+)\\\\([a-z0-9_]+__[a-z0-9_]+)"', src))))
    import ast
    tree = ast.parse(src)
    for n in ast.walk(tree):
        body = getattr(n, 'body', None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], 'value', None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            n.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)


class Progress:
    """how far the import is and about how long it has left, for the in-game settings (status: pct, eta in seconds).
    Each phase weighs what it took here (a full import, 2026-10-01: ~15 min); inside one, its count where it has one
    (models, textures), else its time against that weight. The time left goes by how fast this PC has been so far."""
    PHASES = [('workspots', 20, 'Cyberpunk workspots'), ('weapons', 150, "Cyberpunk's weapons"), ('models', 15, "Fallout 4's models"),
              ('collision', 215, "Fallout 4's collision"),   # (2026-10-03, 20 models: collision ~95% of what
              # converting them took; the two were one 230 s phase)
              ('textures', 105, "Fallout 4's textures"), ('png', 5, "Fallout 4's textures"), ('meshes', 200, 'meshes'),
              ('materials', 60, 'materials'), ('pack', 55, 'packing'), ('catalog', 25, 'the menu'), ('archive', 10, 'Homestead.archive'),
              ('install', 15, 'installing')]
    def __init__(self, status):
        self.status, self.cur, self.last = status, None, 0
        self.w = {p: w for p, w, _ in self.PHASES}
        self.label = {p: l for p, _, l in self.PHASES}
        self.order = [p for p, _, _ in self.PHASES]
        self.total = sum(self.w.values())
        self.done_w, self.spent, self.measured = 0, 0.0, 0  # (weights behind it; time and weight of the phases timed)
        self.hidden = set()                                  # (phases run alongside another: not reported - main)
    def __call__(self, phase, done=None, total=None):
        if phase not in self.w or phase in self.hidden: return
        now = time.time()
        if phase != self.cur:
            if self.cur:
                took = now - self.t
                if took > 3: self.spent, self.measured = self.spent + took, self.measured + self.w[self.cur]   # (kept ones: not timed)
            i = self.order.index(phase)
            self.done_w = sum(self.w[p] for p in self.order[:i])
            self.cur, self.t, self.last = phase, now, 0
        if now - self.last < 1 and done != total: return
        self.last = now
        frac = done / total if total else min(0.95, (now - self.t) / self.w[phase])
        if total == 0: frac = 1
        left = self.total - self.done_w - self.w[phase] * frac
        speed = min(4.0, max(0.3, self.spent / self.measured)) if self.measured >= 60 else 1.0
        self.status(step=self.label[phase], pct=int(100 * (self.total - left) / self.total), eta=int(left * speed))


def digest(step): return codehash.CODE[step] if codehash else source_digest(step)


def source_digest(step):                                     # (tools/release.py bakes these into codehash.py)
    h = hashlib.sha1()
    for f in CODE[step]: h.update(meaning(f).encode())
    return h.hexdigest()


class Stamps:                                                # step -> the hash of its code when it last ran through
    path = os.path.join(FO4, 'code.json')
    def __init__(self, force):
        self.d = {} if force or not os.path.exists(self.path) else json.load(open(self.path))
        self.lock = threading.Lock()                         # (two steps run at once: main)
    def changed(self, step): return self.d.get(step) != digest(step)
    def done(self, step):
        with self.lock:
            self.d[step] = digest(step)
            json.dump(self.d, open(self.path, 'w'), indent=1)


def exe_version(p):
    """a Windows program's file version ("1.11.240"), or None"""
    import ctypes
    from ctypes import wintypes
    v = ctypes.windll.version
    n = v.GetFileVersionInfoSizeW(p, None)
    if not n: return None
    buf = ctypes.create_string_buffer(n)
    if not v.GetFileVersionInfoW(p, 0, n, buf): return None
    r, l = ctypes.c_void_p(), wintypes.UINT()
    if not v.VerQueryValueW(buf, '\\', ctypes.byref(r), ctypes.byref(l)): return None
    f = ctypes.cast(r, ctypes.POINTER(ctypes.c_uint32 * 13)).contents   # (VS_FIXEDFILEINFO: version MS, LS at 2, 3)
    return '%d.%d.%d' % (f[2] >> 16, f[2] & 0xffff, f[3] >> 16)


def drives():
    """the PC's own drives (not network, USB or CD), with GB free: the in-game settings offer a Homestead\\import
    folder on each for the import's data"""
    import ctypes, string
    out = []
    for l in string.ascii_uppercase:
        root = l + ':' + os.sep
        if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:  # (DRIVE_FIXED)
            try: out.append((l + ':', shutil.disk_usage(root).free // 10 ** 9))
            except OSError: pass
    return out


def archives(fo4):
    """the .ba2 versions there, e.g. {1: 32, 7: 12, 8: 51}: every Fallout 4 has its own mix (1 before the 2024
    update, 7 / 8 after; patched installs mix them) - all read alike (fo4/ba2.py)"""
    import collections, struct
    c = collections.Counter()
    for f in os.listdir(fo4):
        if f.lower().endswith('.ba2'):
            with open(os.path.join(fo4, f), 'rb') as h: c[struct.unpack('<4xI', h.read(8))[0]] += 1
    return dict(sorted(c.items()))


def check(log, status):
    """the games and tools; which of Fallout's masters are there (a missing DLC: its pieces left out)"""
    cp = paths.get('cp2077', required=False)
    fo4 = paths.get('fo4', required=False)
    status(fo4=fo4 or 'not found', cp2077=cp or 'not found')
    log('Fallout 4:', fo4); log('Cyberpunk 2077:', cp); log('import data:', WORK)
    if not fo4: raise SystemExit('Fallout 4 not found - say where it is in homestead_paths.json')
    if not cp: raise SystemExit('Cyberpunk 2077 not found')
    log('WolvenKit CLI:', paths.get('wolvenkit'))
    ff = paths.get('ffmpeg', required=False)
    log('ffmpeg:', ff or 'not found - Fallout\'s sounds are left out (those converted before are kept)')
    if not os.path.exists(os.path.join(fo4, 'Fallout4.esm')): raise SystemExit('Fallout4.esm is not in ' + fo4)
    ver = exe_version(os.path.join(os.path.dirname(fo4), 'Fallout4.exe')) or 'unknown'
    ba = archives(fo4)
    if set(ba) - {1, 7, 8}: raise SystemExit('Fallout 4 archives of a version Homestead doesn\'t know: %s' % ba)
    log('Fallout 4 version:', ver, ' archives (version: count):', ba)
    status(fo4version=ver, drives=';'.join('%s|%d' % d for d in drives()))
    for f, name in MASTERS:
        log('  %-24s %s' % (name, 'yes' if os.path.exists(os.path.join(fo4, f)) else 'not installed (its pieces are left out)'))
    hd = any(n.lower().startswith('dlcultrahighresolution') for n in os.listdir(fo4))
    log('  %-24s %s' % ('High Resolution Textures', 'yes' if hd else 'no (the standard textures are used)'))


def room(cp):
    """disk enough? About 20 GB on the import's drive while it works, less what an earlier import left there (kept files
    are remade in place, its scratch folders are made there too); the 9 GB archive moves to the game's drive at the
    end, so room there too if it's another"""
    shutil.rmtree(os.path.join(WORK, 'tmp'), ignore_errors=True)   # (a stopped run's scratch folders: paths.scratch)
    os.makedirs(WORK, exist_ok=True)
    have = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(WORK) for f in fs)
    need, free = max(2e9, 20e9 - have), shutil.disk_usage(WORK).free
    if free < need:
        raise SystemExit('not enough disk space: about %d GB free needed on %s (%d GB free) - free some, or pick another '
                         '"Import data folder"' % (need / 1e9 + 0.5, os.path.splitdrive(WORK)[0] or WORK, free / 1e9))
    if os.path.splitdrive(WORK)[0].lower() != os.path.splitdrive(cp)[0].lower():
        arc = os.path.join(cp, 'archive', 'pc', 'mod', 'Homestead_FO4.archive')   # (an earlier one is replaced)
        gfree = shutil.disk_usage(cp).free + (os.path.getsize(arc) if os.path.exists(arc) else 0)
        if gfree < 10e9:
            raise SystemExit('not enough disk space on %s for the 9 GB archive (%d GB free)' % (os.path.splitdrive(cp)[0], gfree / 1e9))


def game_running():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Cyberpunk2077.exe'], capture_output=True, text=True).stdout
    return 'Cyberpunk2077.exe' in out


def game_assets(st):
    """from the player's Cyberpunk: the workspots placed people use, looping; every weapon as a prop; the border's
    wall (in a mesh of the game's)"""
    import make_ent, make_workspots, make_weapons, make_border
    make_ent.main()                                          # (our templates' JSON first: the weapons' entity is one)
    paths.progress('workspots')
    if st.changed('workspots') or not os.path.isdir(os.path.join(JSON, 'homestead', 'workspots')):
        make_workspots.main(); st.done('workspots')
    paths.progress('weapons')
    if st.changed('weapons') or not os.path.exists(os.path.join(JSON, 'homestead', 'weapons.ent.json')):
        make_weapons.main(); st.done('weapons')
    if st.changed('border') or not os.path.exists(os.path.join(JSON, make_border.MESH + '.json')):
        make_border.main(); st.done('border')


def fallout(st):
    """Fallout 4's pieces, then their game files and archive; a step whose code changed is done again in full (told
    through the environment: the steps' worker processes read it too)"""
    redo = [s for s in ('convert', 'collision', 'post', 'xbm', 'build') if st.changed(s)]
    if 'convert' in redo: redo.append('build')               # (new models: new materials)
    os.environ['HOMESTEAD_FORCE'] = ','.join(redo)
    import convert, build
    convert.main()                                           # (collision, the post steps and xbm run in it)
    for s in ('convert', 'collision', 'post', 'xbm'): st.done(s)
    build.main(); st.done('build')


def mod_archive():
    """Homestead.archive: the templates pieces spawn from, the looping workspots, the weapons, the border - all JSON made to game
    files in one WolvenKit run (in place, folders kept), then packed"""
    import make_ent
    make_ent.main()                                          # (empty.ent / empty_lit.ent JSON: the pieces' templates)
    with paths.scratch('mod_archive') as tmp:
        pack = os.path.join(tmp, 'Homestead')
        shutil.copytree(os.path.join(JSON, 'homestead'), os.path.join(pack, 'homestead'))
        ui = os.path.join(paths.ROOT, 'data', 'ui')          # the menu's thumbnail atlases, shipped (tools/make_thumbs.py)
        if paths.FROZEN and os.path.isdir(ui): shutil.copytree(ui, os.path.join(pack, 'homestead', 'ui'), dirs_exist_ok=True)
        want = [os.path.join(d, f)[:-5] for d, _, fs in os.walk(pack) for f in fs if f.endswith('.json')]
        paths.wk(['convert', 'deserialize', pack], expect=want, what="make Homestead.archive's game files")
        for w in want: os.remove(w + '.json')
        out = os.path.join(tmp, 'out', 'Homestead.archive')
        paths.wk(['pack', pack, '-o', os.path.dirname(out)], expect=[out], what='pack Homestead.archive')
        os.replace(out, MOD_ARCHIVE)


def install(log, mod_only=False):
    """into the game: what the import made (not with mod_only); from our repo also the mod's own files (a player's came
    with the mod)"""
    cp = paths.get('cp2077')
    def put(src, rel):                                       # a file, unless it's the same one already
        dst = os.path.join(cp, rel)
        if not os.path.exists(src): return 0
        if os.path.exists(dst) and (os.path.samefile(src, dst) or
                                    (os.path.getsize(src) == os.path.getsize(dst) and os.path.getmtime(dst) >= os.path.getmtime(src))):
            return 0
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return 1
    def put_dir(src, rel, skip=()):                          # a folder, replaced whole (nothing stale left behind)
        dst = os.path.join(cp, rel)
        if not os.path.isdir(src) or (os.path.exists(dst) and os.path.samefile(src, dst)): return 0
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*skip))
        return 1
    n = 0 if mod_only else put(MOD_ARCHIVE, os.path.join('archive', 'pc', 'mod', 'Homestead.archive'))
    fa = os.path.join(FO4, 'Homestead_FO4.archive')          # (moved, not copied: no second 9 GB left here)
    dst = os.path.join(cp, 'archive', 'pc', 'mod', 'Homestead_FO4.archive')
    if os.path.exists(fa) and not mod_only:
        import build
        inputs = build.manifest(json.load(open(os.path.join(FO4, 'pieces.json'))))   # (what it's made of: fo4/build.py)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(fa, dst + '.part')                       # (to another drive: copied - the old one stays till it's in)
        os.replace(dst + '.part', dst)
        json.dump({'size': os.path.getsize(dst), 'inputs': inputs}, open(os.path.join(FO4, 'installed.json'), 'w'))
        n += 1
    if not mod_only and not os.path.exists(dst):             # (never "done" without Fallout's pieces)
        raise SystemExit("Fallout 4's pieces were not packed (no Homestead_FO4.archive) - see fo4\\import.log")
    if not mod_only:
        n += put(os.path.join(paths.out_cet(), 'catalog.lua'), os.path.join(CET, 'catalog.lua'))
        n += put_dir(os.path.join(paths.out_cet(), 'data'), os.path.join(CET, 'data'))
        sfx = os.path.join(FO4, 'sfx')                       # Fallout's sounds, where Audioware looks
        n += put_dir(sfx, os.path.join('mods', 'Homestead'), skip=('sounds.json',))
    if not paths.FROZEN:                                     # (our repo: the mod itself as well)
        R = paths.ROOT
        n += put(os.path.join(R, CET, 'init.lua'), os.path.join(CET, 'init.lua'))
        n += put_dir(os.path.join(R, CET, 'modules'), os.path.join(CET, 'modules'))
        n += put_dir(os.path.join(R, 'r6', 'scripts', 'Homestead'), os.path.join('r6', 'scripts', 'Homestead'))
        n += put(os.path.join(R, 'r6', 'tweaks', 'Homestead.yaml'), os.path.join('r6', 'tweaks', 'Homestead.yaml'))
        n += put(os.path.join(R, 'plugin', 'build', 'Release', 'Homestead.dll'), os.path.join('red4ext', 'plugins', 'Homestead', 'Homestead.dll'))
    b = os.path.join(paths.game_cet(), 'build.txt')         # (the release this import is of: the mod asks for one after an update)
    if not mod_only and os.path.exists(b): shutil.copyfile(b, os.path.join(paths.game_cet(), 'imported.txt'))
    log('installed into', cp, '(%d changed) - start Cyberpunk to load it' % n)


def keep():
    """keep the import's working files (~9 GB: re-imports in ~2 min instead of ~7)? Ours always; a player's if the
    in-game settings say so (keepImportFiles)"""
    return not paths.FROZEN or paths.kv(os.path.join(paths.game_cet(), 'settings.txt')).get('keepImportFiles') == '1'


def tidy(log):
    """after an install: the archive's staging folder goes (unless kept) - what's left is the converted models
    (a few hundred MB), so a re-import needn't read Fallout's models again"""
    if keep(): return
    gone = 0
    for d in ('archive', 'packed', 'mat_work', 'glb'):
        p = os.path.join(FO4, d)
        for r, _, fs in os.walk(p): gone += sum(os.path.getsize(os.path.join(r, f)) for f in fs)
        shutil.rmtree(p, ignore_errors=True)
    log('working files tidied away: %.1f GB freed' % (gone / 1e9))


def quiet():
    """the frozen importer has no console (its tools start hidden: paths.py): what it prints goes to a file"""
    if sys.stdout is None: sys.stdout = sys.stderr = log_file('console.log')


def main():
    multiprocessing.freeze_support()
    from_game = '--from-game' in sys.argv
    quiet()
    log, status = Log(), Status()
    if '--mod-only' in sys.argv:                             # (ours: the mod's own files into the game, no import)
        if game_running(): sys.exit('Homestead: close Cyberpunk 2077 first')
        install(log, mod_only=True); return
    force = '--force' in sys.argv
    t0 = time.time()
    status(state='checking' if '--check' in sys.argv else 'running', step='looking for the games', started=int(t0), message='')
    try:
        log('Homestead import%s' % (' (fresh: --force)' if force else ''))
        check(log, status)
        if '--check' in sys.argv: status(state='found', step=''); return
        if game_running() and not from_game: raise SystemExit('close Cyberpunk 2077 first (its archives are locked while it runs)')
        room(paths.get('cp2077'))
        import build_catalog, budget
        if from_game: os.environ['HOMESTEAD_PRIORITY'] = 'normal'   # (the player waits at the main menu: not below the idling game)
        st = Stamps(force)
        paths.listener = Progress(status)
        def step(name, fn):
            t = time.time()
            log('==', name)
            fn()
            log('   %s: %.0f s' % (name, time.time() - t))
        # the game's own assets (WolvenKit runs, one core) alongside Fallout's models (a pool of workers), on a PC with
        # the room (budget.roomy: a low-end one runs them one after the other); its progress isn't shown then
        side, err = None, []
        def aside():
            try: step('Cyberpunk assets', lambda: game_assets(st))
            except BaseException as e: err.append(e)
        if budget.roomy():
            paths.listener.hidden = {'workspots', 'weapons'}
            side = threading.Thread(target=aside, daemon=True); side.start()
        else: step('Cyberpunk assets', lambda: game_assets(st))
        step('Fallout 4', lambda: fallout(st))
        if side:
            side.join()
            if err: raise err[0]
        paths.progress('catalog'); step('catalog', build_catalog.main)
        paths.progress('archive'); step('Homestead.archive', mod_archive)
        if game_running():                                   # (started from the game: it installs once that has closed)
            log('built - waiting for Cyberpunk to close to install'); status(state='waiting', step='', pct=99, eta=0)
            while game_running(): time.sleep(5)
            time.sleep(3)                                    # (its files let go)
        t = time.time()
        log('== install'); status(state='running'); paths.progress('install')
        install(log)
        log('   install: %.0f s' % (time.time() - t))
        tidy(log)
        m = (time.time() - t0) / 60
        log('done in %.1f min' % m)
        status(state='done', step='', finished=time.strftime('%Y-%m-%d %H:%M'), minutes='%.1f' % m)
    except SystemExit as e:
        msg = str(e.code) if e.code not in (None, 0) else ''
        if msg:
            log('Homestead:', msg); status(state='failed', message=msg)
            sys.exit('Homestead: ' + msg)
    except Exception as e:
        import traceback
        log(traceback.format_exc()); status(state='failed', message='%s: %s' % (type(e).__name__, e))
        raise


if __name__ == '__main__':
    main()
