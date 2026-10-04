"""<work>/json/homestead/border.mesh.json: the settlement border's wall (modules/border.lua) - a unit open cylinder
(radius 1 m, 0..1 m up, no caps, faces outward, in bands that fade towards the top; Lua scales it to the settlement's radius and the wall's height) in the
game's own two-sided hologram material: blended, depth-tested (what stands in front hides it), no depth write, drawn
from both sides (CULL_None), one pass in renderstage_transparent - so no shadow pass. Made as Fallout's meshes are
(fo4/build.py): a .glb poured into a copy of a plain Cyberpunk mesh, its materials rewritten in its JSON; the archive
step (tools/import.py mod_archive) makes the game file from the JSON. The look is all here: MATERIAL and LOOK.
  python tools/make_border.py
"""
import json, os, re, shutil, sys
import numpy as np
T = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, T); sys.path.insert(0, os.path.join(T, 'fo4'))
import paths

MESH = os.path.join('homestead', 'border.mesh')              # its depot path (border.lua MESH)
SEGS = 96                                                    # sides: at a 50 m radius 3.3 m each, 2.7 cm off the circle
# base\fx\shaders\hologram_two_sided.mt (memoryresident_1_general.archive; read 2026-10-04): its parameters and their
# defaults - SurfaceColor 255,255,255  FallofColor 0,136,163 (the tint at grazing angles)  DotsColor 73,168,246
# Opacity 1 (0..1)  GlowStrength 0.257 (0..1)  FresnelStrength 0.93 (0..10)  OpaqueScanlineDensity 400
# ScanlineThickness 0 (-4..1)  LightBleed 0.3  GlitchChance / FlickerChance / ArtifactsChance 0  DotsSize 100
# AdditiveAlphaBlend 1. Only what LOOK names is set; the rest stays the material's own.
MATERIAL = 'base\\fx\\shaders\\hologram_two_sided.mt'
LOOK = {                                                     # (hologram blue, a faint glow; NOTES.md "Zone and border")
    'SurfaceColor': (56, 189, 248),
    'FallofColor': (37, 99, 235),
    'DotsColor': (125, 211, 252),
    'GlowStrength': 0.4,
}
# The fade towards the top: the material has no gradient, so the wall is bands, each a submesh with its own Opacity.
# (from, to) as shares of the height (border.lua: 30 m under the centre's ground to 30 m over it) and the opacity.
BANDS = [(0.0, 0.5, 0.35), (0.5, 0.533, 0.35), (0.533, 0.567, 0.28), (0.567, 0.617, 0.2), (0.617, 0.683, 0.13),
         (0.683, 0.767, 0.08), (0.767, 0.867, 0.04), (0.867, 1.0, 0.015)]


def cname(v): return {'$type': 'CName', '$storage': 'string', '$value': v}


def material(opacity):
    vals = [{'$type': 'Color', k: {'$type': 'Color', 'Red': v[0], 'Green': v[1], 'Blue': v[2], 'Alpha': 255}} if isinstance(v, tuple)
            else {'$type': 'Float', k: v} for k, v in dict(LOOK, Opacity=opacity).items()]
    return {'$type': 'CMaterialInstance', 'audioTag': cname('None'),
            'baseMaterial': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'string', '$value': MATERIAL}, 'Flags': 'Default'},
            'cookingPlatform': 'PLATFORM_None', 'enableMask': 0, 'metadata': None, 'resourceVersion': 4, 'values': vals}


def band(z0, z1):
    """one band of the wall: two rings of SEGS + 1 vertices (the seam doubled for the UVs), normals outward"""
    a = np.linspace(0, 2 * np.pi, SEGS + 1)
    ring = np.c_[np.cos(a), np.sin(a)]
    pos = np.r_[np.c_[ring, np.full(SEGS + 1, z0)], np.c_[ring, np.full(SEGS + 1, z1)]].astype(np.float32)
    nrm = np.r_[np.c_[ring, np.zeros(SEGS + 1)], np.c_[ring, np.zeros(SEGS + 1)]].astype(np.float32)
    u = np.linspace(0, 1, SEGS + 1)
    uv = np.r_[np.c_[u, np.full(SEGS + 1, 1 - z0)], np.c_[u, np.full(SEGS + 1, 1 - z1)]].astype(np.float32)
    i = np.arange(SEGS)
    tri = np.r_[np.c_[i, i + 1, i + SEGS + 2], np.c_[i, i + SEGS + 2, i + SEGS + 1]]
    gl = lambda v: np.c_[v[:, 0], v[:, 2], -v[:, 1]]          # Cyberpunk (Z up) -> glTF (Y up), as fo4/convert.py
    return gl(pos), gl(nrm), uv, tri


def main():
    import build, convert                                    # (the mesh template's depot path; the .glb writer)
    out = os.path.join(paths.work(), 'json', MESH + '.json')
    with paths.scratch('border') as tmp:
        arc, glb = os.path.join(tmp, 'arc'), os.path.join(tmp, 'glb')
        mesh = os.path.join(arc, MESH)
        # (the template unpacked here, not build.template()'s copy: this runs beside Fallout's models - import.py)
        got = os.path.join(tmp, 'tpl', build.TEMPLATE_DEPOT)
        paths.wk(['unbundle', '-p', paths.cp_content(), '-o', os.path.join(tmp, 'tpl'), '-r', '^' + re.escape(build.TEMPLATE_DEPOT).replace(re.escape('\\'), '.') + '$'],
                 expect=[got], what="unpack the mesh template from Cyberpunk's files")
        os.makedirs(os.path.dirname(mesh))
        shutil.copy(got, mesh)
        subs = []
        for n, (z0, z1, _) in enumerate(BANDS):
            pos, nrm, uv, tri = band(z0, z1)
            subs.append(dict(pos=pos, nrm=nrm, uv=uv, tri=tri, tan=convert.tangents(pos, nrm, uv, tri), material='border%d' % n))
        convert.write_glb(os.path.join(glb, MESH[:-5] + '.glb'), subs)
        said = paths.wk(['import', glb, '-k', '-o', arc], what="import the border's mesh", GltfImportArgs__ImportMaterials='false')
        if open(mesh, 'rb').read() == open(got, 'rb').read():
            raise SystemExit("WolvenKit could not import the border's mesh; it said: " + paths.said(said))
        paths.wk(['convert', 's', arc], expect=[mesh + '.json'], what="read the border's mesh")
        j = json.load(open(mesh + '.json', encoding='utf-8-sig'))
    rc = j['Data']['RootChunk']                              # (as fo4/build.py's materials: one local instance)
    names = ['border%d' % n for n in range(len(BANDS))]
    rc['materialEntries'] = [{'$type': 'CMeshMaterialEntry', 'index': n, 'isLocalInstance': 1, 'name': cname(m)} for n, m in enumerate(names)]
    rc['localMaterialBuffer']['materials'] = [material(o) for _, _, o in BANDS]
    rc['externalMaterials'], rc['preloadExternalMaterials'], rc['preloadLocalMaterialInstances'] = [], [], []
    a = rc['appearances'][0]
    a['Data']['chunkMaterials'], a['Data']['name'] = [cname(m) for m in names], cname('default')
    rc['appearances'] = [a]
    # the template floor's occluder would hide the world behind it once scaled up, its other parameters are a floor's
    # too: none kept. No shadows (the material has no pass for them; said here as well)
    rc['parameters'] = []
    for k in ('castGlobalShadowsCachedInCook', 'castLocalShadowsCachedInCook', 'castsRayTracedShadowsFromOriginalGeometry'):
        if k in rc: rc[k] = 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(j, open(out, 'w'))
    print(out)


if __name__ == '__main__':
    main()
