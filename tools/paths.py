"""Where everything is, on any PC: Fallout 4, Cyberpunk 2077, the WolvenKit CLI (+ the .NET it runs on), ffmpeg. Found from Steam (its library folders), the registry (Bethesda's and GOG's keys), our own
bundled tools folder and PATH. Any of them overridden by homestead_paths.json (the project root, or %APPDATA%\\Homestead)
or an environment variable HOMESTEAD_<NAME> (FO4, CP2077, WOLVENKIT, DOTNET, FFMPEG; BLENDER for the thumbnails, ours).
  python tools/paths.py            what was found (and what wasn't, with how to say where it is)
  python tools/paths.py --get cp2077   one of them
"""
import contextlib, glob, json, os, re, shutil, subprocess, sys

FROZEN = getattr(sys, 'frozen', False)                       # the player's importer (HomesteadImport.exe), or our repo
ROOT = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED = os.path.join(ROOT, 'bin') if FROZEN else os.path.join(ROOT, 'tools', 'bin')   # (WolvenKit CLI, .NET, ffmpeg)
CET = os.path.join('bin', 'x64', 'plugins', 'cyber_engine_tweaks', 'mods', 'Homestead')   # the CET mod, in a game folder
if FROZEN:                                                   # the player's importer has no window, nor do the tools it
                                                             # runs (WolvenKit, ffmpeg, tasklist): a console each would
    _init = subprocess.Popen.__init__                        # flash up over the game (every process imports this first)
    def _hidden(self, *a, **kw):
        kw['creationflags'] = kw.get('creationflags', 0) | subprocess.CREATE_NO_WINDOW
        _init(self, *a, **kw)
    subprocess.Popen.__init__ = _hidden
NAMES = {'fo4': 'Fallout 4 (its Data folder)', 'cp2077': 'Cyberpunk 2077', 'wolvenkit': 'WolvenKit CLI (WolvenKit.CLI.exe)',
         'dotnet': '.NET runtime for WolvenKit (a folder; not needed by a self-contained WolvenKit)', 'ffmpeg': 'ffmpeg (ffmpeg.exe)',
         'blender': 'Blender (blender.exe: menu thumbnails, tools/make_thumbs.py - ours, not the import)'}
_found = {}


def _overrides():
    for p in (os.path.join(ROOT, 'homestead_paths.json'), os.path.join(os.environ.get('APPDATA', ''), 'Homestead', 'homestead_paths.json')):
        if os.path.exists(p):
            try: return json.load(open(p, encoding='utf-8'))
            except Exception as e: print('homestead_paths.json unreadable:', p, e)
    return {}


def _reg(root, key, value):
    try:
        import winreg
        with winreg.OpenKey(root, key) as k: return winreg.QueryValueEx(k, value)[0]
    except Exception: return None


def _steam_libraries():
    import winreg
    steam = _reg(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath') or _reg(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')
    libs = [steam] if steam else []
    vdf = steam and os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
    if vdf and os.path.exists(vdf):
        libs += [p.replace('\\\\', '\\') for p in re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='replace').read())]
    return [os.path.normpath(l) for l in libs if l]


def _epic(name):
    """an Epic Games Store install of `name` (its launcher's manifests: DisplayName, InstallLocation)"""
    d = os.path.join(os.environ.get('PROGRAMDATA', r'C:\ProgramData'), 'Epic', 'EpicGamesLauncher', 'Data', 'Manifests')
    for f in (os.listdir(d) if os.path.isdir(d) else []):
        try: m = json.load(open(os.path.join(d, f), encoding='utf-8'))
        except Exception: continue
        if m.get('DisplayName', '').lower().startswith(name.lower()) and os.path.isdir(m.get('InstallLocation', '')):
            return os.path.normpath(m['InstallLocation'])


def _xbox(folder):
    """a Game Pass / Microsoft Store install: <drive>:/XboxGames/<folder>/Content"""
    for drive in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        p = os.path.join(drive + ':' + os.sep, 'XboxGames', folder, 'Content')
        if os.path.isdir(p): return p


def _game(folder, regs, epic=None):
    for root, key, value in regs:                            # (Bethesda's launcher, GOG)
        p = _reg(root, key, value)
        if p and os.path.isdir(p): return os.path.normpath(p)
    for lib in _steam_libraries():
        p = os.path.join(lib, 'steamapps', 'common', folder)
        if os.path.isdir(p): return p
    return (epic and _epic(epic)) or _xbox(folder)


def _find(name):
    import winreg
    HKLM = winreg.HKEY_LOCAL_MACHINE
    if name == 'fo4':
        g = _game('Fallout 4', [(HKLM, r'SOFTWARE\WOW6432Node\Bethesda Softworks\Fallout4', 'Installed Path'),
                                (HKLM, r'SOFTWARE\WOW6432Node\GOG.com\Games\1998527297', 'path')],
                  epic='Fallout 4')
        return g and os.path.join(g, 'Data')
    if name == 'cp2077':
        if FROZEN:                                           # (the importer lives in the game: <game>\<CET>\importer)
            g = os.path.normpath(os.path.join(ROOT, *[os.pardir] * 7))
            if os.path.exists(os.path.join(g, 'bin', 'x64', 'Cyberpunk2077.exe')): return g
        return _game('Cyberpunk 2077', epic='Cyberpunk 2077', regs=[(HKLM, r'SOFTWARE\WOW6432Node\GOG.com\Games\1423049311', 'path'),
                                        (HKLM, r'SOFTWARE\WOW6432Node\GOG.com\Games\1207664663', 'path')])
    if name == 'wolvenkit':
        for p in (os.path.join(BUNDLED, 'WolvenKit-cli', 'WolvenKit.CLI.exe'), shutil.which('WolvenKit.CLI')):
            if p and os.path.exists(p): return p
    if name == 'dotnet':
        for p in (os.environ.get('DOTNET_ROOT'), os.path.join(BUNDLED, 'dotnet')):
            if p and os.path.isdir(p): return p
    if name == 'ffmpeg':
        for p in (os.path.join(BUNDLED, 'ffmpeg', 'ffmpeg.exe'), shutil.which('ffmpeg')):
            if p and os.path.exists(p): return p
    if name == 'blender': return shutil.which('blender')
    return None


def get(name, required=True):
    """the path for `name` (see NAMES), or None (required: stops with how to say where it is)"""
    if name not in _found:
        p = os.environ.get('HOMESTEAD_' + name.upper()) or _overrides().get(name) or _find(name)
        _found[name] = os.path.normpath(p) if p and os.path.exists(p) else None
    if required and not _found[name]:
        sys.exit('Homestead: %s not found. Say where it is in homestead_paths.json ({"%s": "..."}) or HOMESTEAD_%s.'
                 % (NAMES[name], name, name.upper()))
    return _found[name]


def wk_env(**extra):
    """the environment WolvenKit runs in (its .NET, if it isn't self-contained)"""
    e = dict(os.environ, **extra)
    d = get('dotnet', required=False)
    if d: e['DOTNET_ROOT'] = d
    return e


def said(out):                                               # a tool's last words
    return next((l.strip() for l in reversed(out.splitlines()) if l.strip()), 'nothing')[:300]


def wk(args, expect=(), what=None, partial=False, **env):
    """a WolvenKit CLI run -> what it printed. expect: the files it must make (a * in one: any that match); one
    missing - with partial, every one (a run over many files: the caller sees to the few) - stops the import with a
    message a player can read (in-game status "failed"). Its exit code alone says little (import exits 3 when it
    worked). env: its settings (XbmImportArgs__..., GltfImportArgs__...)"""
    what = what or ' '.join(args[:2])
    try: r = subprocess.run([get('wolvenkit'), *args], env=wk_env(**env), capture_output=True, text=True, errors='replace')
    except OSError as e: raise SystemExit('WolvenKit could not start (%s): %s' % (what, e))
    out = (r.stdout or '') + (r.stderr or '')
    miss = [p for p in expect if not (glob.glob(p, recursive=True) if '*' in p else os.path.exists(p))]
    if miss and (not partial or len(miss) == len(expect)):
        raise SystemExit('WolvenKit could not %s: %d of %d files not made (e.g. %s); it exited %d saying: %s'
                         % (what, len(miss), len(expect), os.path.basename(miss[0]), r.returncode, said(out)))
    return out


@contextlib.contextmanager
def scratch(name):
    """a scratch folder in the work folder (on its drive, in its disk check: import.py room()), gone afterwards
    whatever happens"""
    d = os.path.join(work(), 'tmp', name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    try: yield d
    finally: shutil.rmtree(d, ignore_errors=True)


def cp_content(): return os.path.join(get('cp2077'), 'archive', 'pc', 'content')


listener = None                                              # (tools/import.py: the in-game settings show how it's going)
def progress(phase, done=None, total=None):
    """how the import is going: a phase begun, or done of total in it (the steps say; they work alone just as well)"""
    if listener: listener(phase, done, total)


def game_cet(): return os.path.join(get('cp2077'), CET)


def mod_cet():
    """the CET mod's own files (init.lua, modules): our repo's copy, or the one installed in the game"""
    return game_cet() if FROZEN else os.path.join(ROOT, CET)


def kv(path):
    """a "key=value" file (the in-game settings' settings.txt) -> dict"""
    try: return dict(l.rstrip('\r\n').split('=', 1) for l in open(path, encoding='utf-8') if '=' in l)
    except OSError: return {}


_work = None
def work():
    """where the import's data goes (made, kept for quick re-runs), and our dev tools' (harvest, meshes, thumbnails,
    survey): HOMESTEAD_WORK, else our repo's source/ - or, for a player, the in-game settings' importDir, else the CET
    mod's import folder. (Ours never reads the game's settings: a folder picked in game is the player importer's)"""
    global _work
    if _work is None:
        w = os.environ.get('HOMESTEAD_WORK') or (kv(os.path.join(game_cet(), 'settings.txt')).get('importDir', '').strip() if FROZEN else '')
        _work = os.path.normpath(w or (os.path.join(game_cet(), 'import') if FROZEN else os.path.join(ROOT, 'source')))
        os.makedirs(_work, exist_ok=True)
    return _work


def out_cet():
    """where the catalog is written: HOMESTEAD_OUT (a dry build: tools/dev/dry_catalog.py), else our repo's CET mod
    (the sim reads it), or the work folder (installed from there)"""
    return os.environ.get('HOMESTEAD_OUT') or (os.path.join(work(), 'cet') if FROZEN else os.path.join(ROOT, CET))


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--get':
        print(get(sys.argv[2]))
    else:
        for n, what in NAMES.items():
            p = get(n, required=False)
            print('%-10s %s' % (n, p or ('not found  (' + what + ')')))
