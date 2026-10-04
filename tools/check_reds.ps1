# Compiles every redscript the game would (all of r6\scripts, with this repo's Homestead scripts swapped in, plus every
# RED4ext plugin's Scripts folder) in a scratch copy, the way RED4ext calls scc. Fails on any compile error.
# Note: scc only compiles the plugin folders when they're listed in -compilePathsFile; with just -compile <dir> on a
# folder outside r6\scripts it compiles nothing and still says "Compilation complete".
$ErrorActionPreference = 'Stop'
$root = Resolve-Path "$PSScriptRoot\.."
$game = python "$PSScriptRoot\paths.py" --get cp2077              # (found as the importer finds it: tools/paths.py)
if (-not $game -or $game -eq 'None') { throw 'Cyberpunk 2077 not found (homestead_paths.json "cp2077")' }
$tmp = "$env:TEMP\homestead_scc"
Remove-Item $tmp -Recurse -Force -EA 0
New-Item -ItemType Directory "$tmp\cache" -Force | Out-Null
Copy-Item "$game\r6\scripts" "$tmp\scripts" -Recurse
Remove-Item "$tmp\scripts\Homestead" -Recurse -Force -EA 0
Copy-Item "$root\r6\scripts\Homestead" "$tmp\scripts\Homestead" -Recurse
$plugins = Get-ChildItem "$game\red4ext\plugins\*\Scripts" -Directory | ForEach-Object FullName
Set-Content "$tmp\paths.txt" ($plugins -join "`n") -Encoding ascii
Copy-Item "$game\r6\cache\final.redscripts" "$tmp\cache\final.redscripts" -Force
& "$game\engine\tools\scc.exe" -compile "$tmp\scripts" -compilePathsFile "$tmp\paths.txt" -customCacheDir "$tmp\cache" 2>&1 | Out-Null
$code = $LASTEXITCODE
$log = Get-Content "$tmp\logs\redscript_rCURRENT.log"
$files = ($log | Select-String '\.reds$').Count
$errors = $log | Select-String '^\[ERROR'
if ($code -ne 0 -or $errors -or $files -eq 0) {
    $log | Select-String -NotMatch '\.reds$' | Select-Object -First 40
    throw "redscript check FAILED ($files files, exit $code)"
}
"redscript check passed: $files files compiled"
