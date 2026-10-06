HOMESTEAD - Fallout 4's settlement workshop in Cyberpunk 2077
================================================================

Homestead adds Fallout 4's workshop to Night City: found a settlement anywhere, then build with Fallout 4's
workshop pieces and Cyberpunk's own props. Nothing of Fallout 4 comes with this mod - the pieces are made on your
PC from your own copy of Fallout 4, once, by Homestead's importer.

NEEDS
  - Cyberpunk 2077 (2.3)
  - Fallout 4 installed: Steam, GOG, Epic, Game Pass or the Bethesda launcher. Tested with the next-gen update
    (1.11.240); older versions may work but are untested. Its DLCs add their pieces if you have them.
  - Cyber Engine Tweaks, RED4ext, redscript, Codeware, TweakXL, Audioware, Native Settings UI

SIZE AND TIME - for the import, done once; in game Homestead itself is light
  Download          217 MB zipped, 571 MB unpacked (most of it the importer and the tools it brings: WolvenKit,
                    .NET, ffmpeg, Python)
  While importing   about 20 GB free on the drive Cyberpunk is on; less if you point "Import data folder" at
                    another drive (then 10 GB on Cyberpunk's)
  Afterwards        about 10.4 GB: 9.8 GB of pieces (archive\pc\mod\Homestead_FO4.archive and Homestead.archive)
                    + 0.6 GB of import data. With "Keep import files": about 10 GB of import data instead
  First import      about 15-20 minutes; 10-15 measured on an 8-core Ryzen 7 5700X3D, 32 GB RAM, NVMe SSD; a few minutes more when
                    started from the game (Cyberpunk open at the main menu meanwhile)
  Re-import         only what changed is made again: under a minute when little did
  Memory            up to about 12 GB at its peak on that PC; most of the import uses under 2 GB. It starts only as
                    many workers as your free memory holds: less RAM means a slower import, not a failed one.
                    16 GB of RAM is comfortable with the game open
  CPU               up to 8 threads for Fallout's models and textures, one for most of the rest
  GPU               not used
  It runs at below-normal priority: the PC stays usable, and it can be cancelled (Settings > Mods > Homestead).

INSTALL
  With your mod manager, or unpack the zip into your Cyberpunk 2077 folder (the one with bin, archive and r6 in
  it). It holds the mod and the importer: the program that makes the pieces from your Fallout 4. The importer
  only reads your Fallout 4 files and writes into your Cyberpunk folder.

FIRST START: IMPORT FALLOUT 4
  1. Start Cyberpunk. On the main menu: Settings > Mods > Homestead.
  2. It shows where it found Fallout 4 ("Look again" if it's wrong). Press "Import" on the status line at the top.
  3. Leave it at the main menu while it works (about 15-20 minutes the first time, quietly in the background; the
     status line shows how it's going, and its button turns to "Cancel"). When it says "Built - quit Cyberpunk to install it", quit
     Cyberpunk: it installs as the game closes. Start Cyberpunk again - the pieces are there.

  Updating Homestead: install the new version over the old one. If the update needs an import, the status line
  and a message in workshop mode say so: import again - only what changed is made again. Otherwise there is
  nothing to do.
  If the import fails, the status line says why (for example what WolvenKit couldn't do); import.log (below) has
  the details.
  If pieces look broken: switch on "Overwrite already imported items" and import again - everything is made anew.

  Without the game: with Cyberpunk closed, run (double-click)
    bin\x64\plugins\cyber_engine_tweaks\mods\Homestead\importer\HomesteadImport.exe
  It has no window; how it's going is in bin\x64\plugins\cyber_engine_tweaks\mods\Homestead\import\fo4\import.log
  (and on the settings page next time you start the game). It installs by itself when done - no need to quit
  anything. From a command prompt, "HomesteadImport.exe --force" makes everything anew; "--check" only looks for the
  games. It's the same importer the settings page starts.

THE IMPORT'S DATA
  In this folder's "import" folder: about 0.6 GB after an import. "Keep import files" keeps ~9 GB more there, so a re-import after something
  changed redoes less. "Import data folder" puts it on another drive instead (then
  import again). Delete the folder to free the space - the next import remakes it.

SETTINGS
  Settings > Mods > Homestead, also from the pause menu: Keys (see KEYS) and Building (the settlement's border, a
  holographic wall in workshop mode; "Show snap points" draws the snap points round a held piece in snap
  placement - cyan built ones, yellow the one it snaps to, green its own).

BUILDING
  Found a settlement (CET binding "Found a settlement here"), walk to its workbench and press F. Hold F anywhere in a
  settlement (the circle round where you founded it: 50 m, or Settings > Building > Settlement size) to build. Fallout's keys: E place, R scrap, Tab back,
  Q snap / free placement, the mouse buttons turn the piece, the wheel further / nearer, Ctrl the move gizmo.
  Fallout's pieces are held and snap as in Fallout 4: the piece floats in the middle of the view, turns with
  you, and snaps when one of its snap points comes near one that fits; with two snaps on one spot the mouse
  buttons step between them. A snap that would put it inside something doesn't take.
  Cyberpunk's own props are in the Night City tab, a folder for each kind (Containers, Decor, Electronics,
  Furniture, Industrial, Lighting, Nature, Street, Weapons; 2,412 pieces). Lamps and lit signs light up; F on one
  turns it off and on.

YOUR BUILDINGS
  What you build is kept by Homestead itself, not inside the game's save: the files pieces.txt and pieces_<number>.txt
  in bin\x64\plugins\cyber_engine_tweaks\mods\Homestead (each save knows which of them is its own). That keeps your
  pieces out of the game's population, so a big settlement leaves Night City's traffic and crowds alone. Keep those
  files when you update, and copy them along with your saves if you move to another PC: a save without its file
  loads with nothing built. A settlement built with an older Homestead is carried over by itself the first time you
  walk up to it (a few seconds, outside workshop mode).

PEOPLE
  The People tab holds Night City's people, drones and mechs, holograms and animals. They are animated props: they
  stay where you put them. Placed on a seat, a bed or a work stall, a person takes it up; placed next to another
  person, the two talk. People > Animations has the game's own animations as cards: place one on a person to give it
  to them. Ctrl on a person moves them with the gizmo.

KEYS
  Settings > Mods > Homestead > Keys: every Homestead key can be changed. Each one's text says what else the game
  does on that key - "blocked in workshop mode" is harmless; "CONFLICT" means the game acts too (crouch, jump,
  sprint...), pick another key. The on-screen hints follow your keys.

UNINSTALL
  Remove the mod, then archive\pc\mod\Homestead_FO4.archive and Homestead.archive, and mods\Homestead (the sounds,
  and what you built: see YOUR BUILDINGS).

Bundled programs and their licences: importer\licenses.
