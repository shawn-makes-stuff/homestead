"""Fallout 4 .bgsm materials: the texture paths and the few settings a Cyberpunk material needs (alpha test,
two-sided, smoothness, specular). Layout: FO4_RESEARCH.md, section 2 (ousnius Material-Editor BGSM.cs).
  python tools/fo4/bgsm.py materials/<path>.bgsm
"""
import os, struct, sys


def path(p):
    """a material path as the archive has it: from the last 'materials\\', lower case"""
    p = p.replace('/', '\\').lower()
    i = p.rfind('materials\\')
    return p[i:] if i >= 0 else 'materials\\' + p.lstrip('\\')


def read(b):
    o = 0
    def u(fmt):
        nonlocal o
        v = struct.unpack_from('<' + fmt, b, o); o += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]
    def s():
        nonlocal o
        n = u('I'); t = b[o:o + n].rstrip(b'\0').decode('cp1252'); o += n; return t
    magic, ver, tile = u('4sII')
    assert magic == b'BGSM', magic
    m = {'version': ver, 'tile': (bool(tile & 2), bool(tile & 1))}
    m['uv'] = u('4f')
    m['alpha'] = u('f')
    m['blend'] = u('BII')
    m['alpha_ref'], m['alpha_test'] = u('BB')
    flags = u('10B')                                   # (z write, z test, SSR, wetness SSR, decal, two-sided, decal no
    m['two_sided'] = bool(flags[5])                    # fade, non-occluder, refraction, refraction falloff)
    m['decal'] = bool(flags[4] or flags[6])            # drawn over another surface, in its plane (Fallout biases it)
    u('f')                                             # refraction power
    if ver < 10: u('Bf')
    else: u('B')
    m['palette'] = bool(u('B'))                        # greyscale to palette: the diffuse is grey, its colour comes
                                                       # from the greyscale slot's gradient (a row of it: palette_scale)
    if ver >= 6: u('B')
    names = ['diffuse', 'normal', 'smooth_spec', 'greyscale']
    names += ['envmap', 'glow', 'inner', 'wrinkles', 'displacement'] if ver <= 2 else ['glow', 'wrinkles', 'specular', 'lighting', 'flow']
    if ver >= 17: names.append('distance_alpha')
    m['textures'] = {n: s() for n in names}
    if ver <= 2:                                       # FO4 (v2): the specular block follows
        u('B'); u('B'); u('f'); u('f'); u('B'); u('f')  # editor alpha ref, rim lighting + power, backlight, subsurface + rolloff
        m['specular_on'] = bool(u('B'))
        m['specular'] = u('3f'); m['specular_mult'] = u('f'); m['smoothness'] = u('f')
        u('4f')                                        # fresnel power, wetness spec scale / power scale / minvar
        u('f')                                         # wetness env map scale (v < 10)
        u('2f')                                        # wetness fresnel power, metalness
        m['root'] = s()                                # root material
        u('B')                                         # anisotropic lighting
        m['emit'] = bool(u('B'))                       # glows: emittance colour x multiplier (with the glow map)
        m['emit_color'] = u('3f') if m['emit'] else (0.0, 0.0, 0.0)
        m['emit_mult'] = u('f')
        u('BB')                                        # model space normals, external emittance
        u('6B')                                        # back lighting, receive / hide / cast shadows, dissolve, shadowmask
        m['glowmap'] = bool(u('B'))
        u('BBB'); u('3f'); u('BBBB')                   # env map window / eye, hair + tint, tree, facegen, skin tint, tessellate
        if ver < 3: u('5f')                            # displacement bias / scale, tessellation pn scale / base / fade
        m['palette_scale'] = u('f')
    return m


def read_bgem(b):
    """Fallout 4 .bgem effect materials (glow tubes, halos, holograms): the base texture, its colour and strength.
    Layout: ousnius Material-Editor BGEM.cs, version 2 (FO4)"""
    o = 0
    def u(fmt):
        nonlocal o
        v = struct.unpack_from('<' + fmt, b, o); o += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]
    def s():
        nonlocal o
        n = u('I'); t = b[o:o + n].rstrip(b'\0').decode('cp1252'); o += n; return t
    magic, ver, tile = u('4sII')
    assert magic == b'BGEM', magic
    m = {'version': ver, 'uv': u('4f'), 'alpha': u('f'), 'blend': u('BII')}
    m['alpha_ref'], m['alpha_test'] = u('BB')
    flags = u('10B')
    m['two_sided'] = bool(flags[5])
    u('f')                                             # refraction power
    if ver < 10: u('Bf')
    else: u('B')
    u('B')
    if ver >= 6: u('B')
    names = ['base', 'grayscale', 'envmap', 'normal', 'envmap_mask']
    if ver >= 10: names += ['specular', 'lighting', 'glow']
    m['textures'] = {n: s() for n in names}
    u('B')                                             # blood enabled
    m['lit'] = bool(u('B'))                            # effect lighting enabled (glass: lit, alpha-blended, an envmap)
    u('B'); u('B'); u('B')                             # falloff enabled, falloff colour enabled, grayscale to palette alpha
    u('B')                                             # soft enabled
    m['color'] = u('3f')                               # base colour
    m['color_scale'] = u('f')
    return m


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ba2
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import paths
    a = ba2.Archive(os.path.join(paths.get('fo4'), 'Fallout4 - Materials.ba2'))
    print(read(a.read(path(sys.argv[1]))))
