# Homestead

Fallout 4's settlement workshop in Cyberpunk 2077: found a settlement anywhere, hold F, and build with Fallout 4's
workshop pieces and Night City's own props.

Nothing of Fallout 4 ships with the mod. Its pieces are converted on the player's PC, once, from their own Fallout 4
install by the bundled importer. The only Fallout-derived files in this repository are the menu's thumbnail atlases.

Player documentation: [README_PLAYER.txt](README_PLAYER.txt).

## Requirements

- Cyberpunk 2077 (2.3) and an installed Fallout 4 (any version; DLCs add their pieces)
- Cyber Engine Tweaks, RED4ext, redscript, Codeware, TweakXL, Audioware, Native Settings UI
- Windows. The importer does not run natively on Linux; under Proton it is untested.

## Layout

| Path | What |
|---|---|
| `bin/x64/plugins/cyber_engine_tweaks/mods/Homestead/` | The mod: CET Lua (`init.lua`, `modules/`) |
| `r6/` | redscript and TweakXL files |
| `plugin/` | RED4ext plugin (starts the importer, mouse capture, key names) |
| `tools/import.py` | The importer: Fallout 4's pieces, the catalog, the archives, install |
| `tools/fo4/` | Fallout 4 readers and converters (BA2, NIF, Havok, materials, textures) |
| `tools/release.py` | Builds the player's zip (frozen importer and bundled tools) |
| `tools/sim.py` | The test suite: the mod's Lua run against a mock of the game |
| `source/` | Data the importer ships: the Night City catalog, thumbnails, entity templates |

## Building

Python 3.11 with `numpy scipy pillow trimesh networkx lupa`, WolvenKit CLI, a .NET runtime and ffmpeg. Tool paths that
are not found automatically go in `homestead_paths.json` (see `tools/paths.py`).

```
python tools/import.py              # import from your Fallout 4 and install into Cyberpunk (game closed)
python tools/import.py --mod-only   # only the mod's own files
python -X faulthandler tools/sim.py # tests (needs an import first: they read the generated catalog)
cmake -S plugin -B plugin/build && cmake --build plugin/build --config Release
python tools/release.py             # dist/Homestead-<version>.zip
```

An import redoes only the steps whose code or inputs changed. A release carries a build id; the mod asks for a new
import after an update only when that id differs from the one the last import ran with.
