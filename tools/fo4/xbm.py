"""Cyberpunk textures (.xbm) written straight from Fallout's own block-compressed data: no decoding, no re-encoding.
Fallout's DDS textures are already the formats Cyberpunk uses (colour BC1 / BC3, normals BC5) and an .xbm holds the
same blocks, mips one after another; the only difference is that Cyberpunk's rows run bottom-up, so the blocks are
flipped (lossless: block rows reversed, pixel rows inside each block swapped). Roughness is the one texture computed
(from the gloss in _s, convert.py's formula), encoded to BC4 here. The .xbm header comes from one tiny WolvenKit-made
header per kind / size / mip count, cached in source/fo4/heads; the data buffer is stored uncompressed.
  python tools/fo4/xbm.py [--force]      every texture pieces.json uses; what's already made is kept unless --force
  python tools/fo4/xbm.py <fallout texture path> <out.xbm> <kind>     one texture (a test)
"""
import base64, io, json, os, struct, sys, zlib
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (tools/: paths.py)
import paths

HEADS = os.path.join(paths.work(), 'fo4', 'heads')
# kind -> (compression, group, gamma, block layout); the layouts are what Fallout stores for that kind
KINDS = {'normal': ('TCM_Normalmap', 'TEXG_Generic_Normal', 0, 'bc5'),
         'rough': ('TCM_QualityR', 'TEXG_Generic_Grayscale', 0, 'bc4'),
         'color': ('TCM_DXTNoAlpha', 'TEXG_Generic_Color', 1, 'bc1'),
         'alpha': ('TCM_DXTAlpha', 'TEXG_Generic_Color', 1, 'bc3'),
         'ui': ('TCM_DXTAlpha', 'TEXG_Generic_UI', 1, 'bc3')}            # menu thumbnail atlases: no mips, not streamed
LAYOUT = {71: 'bc1', 72: 'bc1', 77: 'bc3', 78: 'bc3', 80: 'bc4', 83: 'bc5'}          # DXGI format -> block layout
FOURCC = {b'DXT1': 71, b'DXT3': 74, b'DXT5': 77, b'ATI1': 80, b'BC4U': 80, b'ATI2': 83, b'BC5U': 83}   # classic DDS headers
BLOCK = {'bc1': 8, 'bc4': 8, 'bc3': 16, 'bc5': 16}


def mip_sizes(w, h, mips, layout):
    out = []
    for m in range(mips):
        mw, mh = max(1, w >> m), max(1, h >> m)
        out.append((mw, mh, max(1, (mw + 3) // 4), max(1, (mh + 3) // 4)))
    return out


def _flip_bc1(b, rows):                                    # colour block: rows of 2-bit indices, one byte each
    idx = b[..., 4:8].copy()
    b[..., 4:4 + rows] = idx[..., :rows][..., ::-1]


def _flip_bc4(b, rows):                                    # alpha / BC4 block: rows of 12 bits in 48-bit indices
    v = np.zeros(b.shape[:-1], np.uint64)
    for i in range(6): v |= b[..., 2 + i].astype(np.uint64) << np.uint64(8 * i)
    r = [(v >> np.uint64(12 * k)) & np.uint64(0xFFF) for k in range(4)]
    r[:rows] = r[:rows][::-1]
    v = r[0] | (r[1] << np.uint64(12)) | (r[2] << np.uint64(24)) | (r[3] << np.uint64(36))
    for i in range(6): b[..., 2 + i] = ((v >> np.uint64(8 * i)) & np.uint64(0xFF)).astype(np.uint8)


def flip(body, w, h, mips, layout):
    """block-compressed mips, upside down (lossless)"""
    out, o, bs = [], 0, BLOCK[layout]
    for mw, mh, bx, by in mip_sizes(w, h, mips, layout):
        n = bx * by * bs
        b = np.frombuffer(body, np.uint8, n, o).reshape(by, bx, bs)[::-1].copy()
        o += n
        rows = min(4, mh)
        if layout == 'bc1': _flip_bc1(b, rows)
        elif layout == 'bc4': _flip_bc4(b, rows)
        elif layout == 'bc3': _flip_bc4(b[..., :8], rows); _flip_bc1(b[..., 8:], rows)   # (views: written through)
        elif layout == 'bc5': _flip_bc4(b[..., :8], rows); _flip_bc4(b[..., 8:], rows)
        out.append(b.tobytes())
    return b''.join(out)


def encode_bc4(img):
    """a grey image (uint8, h x w) -> BC4 blocks (8-value mode: max, min and six steps between)"""
    h, w = img.shape
    ph, pw = -h % 4, -w % 4
    a = np.pad(img, ((0, ph), (0, pw)), mode='edge').astype(np.int32)
    by, bx = a.shape[0] // 4, a.shape[1] // 4
    px = a.reshape(by, 4, bx, 4).transpose(0, 2, 1, 3).reshape(by, bx, 16)
    hi, lo = px.max(-1), px.min(-1)
    span = np.maximum(hi - lo, 1)
    p = np.rint((hi[..., None] - px) * 7 / span[..., None]).astype(np.int64)          # 0 = hi .. 7 = lo
    idx = np.where(p == 0, 0, np.where(p == 7, 1, p + 1)).astype(np.uint64)
    idx = np.where((hi == lo)[..., None], 0, idx)
    v = np.zeros((by, bx), np.uint64)
    for i in range(16): v |= idx[..., i] << np.uint64(3 * i)
    out = np.zeros((by, bx, 8), np.uint8)
    out[..., 0], out[..., 1] = hi, lo
    for i in range(6): out[..., 2 + i] = ((v >> np.uint64(8 * i)) & np.uint64(0xFF)).astype(np.uint8)
    return out.tobytes()


def encode_bc1(rgb):
    """an RGB image (uint8, h x w x 3) -> BC1 colour blocks (4-colour mode; endpoints: the block's colour box corners
    along its brightest-to-darkest diagonal - plain, fine for menu thumbnails)"""
    h, w, _ = rgb.shape
    a = np.pad(rgb, ((0, -h % 4), (0, -w % 4), (0, 0)), mode='edge').astype(np.float32)
    by, bx = a.shape[0] // 4, a.shape[1] // 4
    px = a.reshape(by, 4, bx, 4, 3).transpose(0, 2, 1, 3, 4).reshape(by, bx, 16, 3)
    hi, lo = px.max(2), px.min(2)
    def q565(c):
        r, g, b = np.rint(c[..., 0] * 31 / 255), np.rint(c[..., 1] * 63 / 255), np.rint(c[..., 2] * 31 / 255)
        return (r.astype(np.uint32) << 11) | (g.astype(np.uint32) << 5) | b.astype(np.uint32)
    def d565(v):
        return np.stack([((v >> 11) & 31) * 255 / 31, ((v >> 5) & 63) * 255 / 63, (v & 31) * 255 / 31], -1).astype(np.float32)
    c0, c1 = q565(hi), q565(lo)
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    e0, e1 = d565(c0), d565(c1)
    pal = np.stack([e0, e1, (2 * e0 + e1) / 3, (e0 + 2 * e1) / 3], 2)                  # codes 0..3
    idx = ((px[:, :, :, None, :] - pal[:, :, None, :, :]) ** 2).sum(-1).argmin(-1).astype(np.uint32)
    idx = np.where((c0 == c1)[..., None], 0, idx)
    bits = np.zeros((by, bx), np.uint32)
    for i in range(16): bits |= idx[..., i] << np.uint32(2 * i)
    out = np.zeros((by, bx, 8), np.uint8)
    out[..., 0], out[..., 1] = c0 & 255, c0 >> 8
    out[..., 2], out[..., 3] = c1 & 255, c1 >> 8
    for i in range(4): out[..., 4 + i] = (bits >> np.uint32(8 * i)) & 255
    return out


def encode_bc3(rgba):
    """an RGBA image -> BC3 blocks (BC4 alpha + BC1 colour), bottom-up as Cyberpunk stores them"""
    rgba = np.ascontiguousarray(rgba[::-1])
    al = np.frombuffer(encode_bc4(rgba[..., 3]), np.uint8).reshape(-1, 8)
    co = encode_bc1(rgba[..., :3]).reshape(-1, 8)
    return np.concatenate([al, co], 1).tobytes()


def ui_atlas(png, out):
    """a menu thumbnail atlas (.png, premultiplied) -> a UI .xbm: BC3, no mips, not streamed"""
    im = np.asarray(Image.open(png).convert('RGBA'))
    h, w = im.shape[:2]
    make_heads([('ui', w, h, 1)])
    write(out, 'ui', w, h, 1, encode_bc3(im))


def rough_bc4(dds, smooth):
    """Fallout's _s (gloss in green) -> roughness BC4 with mips, bottom-up: n = 2^(10 g s + 1), r = (2 / (n + 2))^0.25"""
    g = np.asarray(Image.open(io.BytesIO(dds)).convert('RGB'))[..., 1].astype(np.float32) / 255
    r = ((2 / (2 ** (10 * g * smooth + 1) + 2)) ** 0.25)[::-1]
    out, mips = [], 0
    while True:
        out.append(encode_bc4((r * 255).clip(0, 255).round().astype(np.uint8))); mips += 1
        if r.shape == (1, 1): break
        fh, fw = (2 if r.shape[0] > 1 else 1), (2 if r.shape[1] > 1 else 1)
        h2, w2 = r.shape[0] // fh, r.shape[1] // fw
        r = r[:h2 * fh, :w2 * fw].reshape(h2, fh, w2, fw).mean((1, 3))
    return b''.join(out), mips


# --- the .xbm header ---------------------------------------------------------------------------------------------

def _json(kind, w, h, mips):
    comp, group, gamma, layout = KINDS[kind]
    bs, info, off = BLOCK[layout], [], 0
    for mw, mh, bx, by in mip_sizes(w, h, mips, layout):
        size = bx * by * bs
        info.append({'$type': 'rendRenderTextureBlobMipMapInfo',
                     'layout': {'$type': 'rendRenderTextureBlobMemoryLayout', 'rowPitch': bx * bs, 'slicePitch': size},
                     'placement': {'$type': 'rendRenderTextureBlobPlacement', 'offset': off, 'size': size}})
        off += size
    blob = {'$type': 'rendRenderTextureBlobPC',
            'header': {'$type': 'rendRenderTextureBlobHeader', 'flags': 1, 'histogramData': [], 'mipMapInfo': info,
                       'sizeInfo': {'$type': 'rendRenderTextureBlobSizeInfo', 'depth': 1, 'height': h, 'width': w},
                       'textureInfo': {'$type': 'rendRenderTextureBlobTextureInfo', 'dataAlignment': 8, 'mipCount': mips,
                                       'sliceCount': 1, 'sliceSize': off, 'textureDataSize': off, 'type': 'TEXTYPE_2D'},
                       'version': 2},
            'textureData': {'BufferId': '0', 'Flags': 131072, 'Bytes': base64.b64encode(bytes(16)).decode()}}
    root = {'$type': 'CBitmapTexture', 'cookingPlatform': 'PLATFORM_PC', 'depth': 1, 'height': h,
            'histBiasAddCoef': {'$type': 'Vector3', 'X': 0, 'Y': 0, 'Z': 0}, 'histBiasMulCoef': {'$type': 'Vector3', 'X': 1, 'Y': 1, 'Z': 1},
            'renderResourceBlob': None,
            'renderTextureResource': {'$type': 'rendRenderTextureResource', 'renderResourceBlobPC': {'HandleId': '0', 'Data': blob}},
            'setup': {'$type': 'STextureGroupSetup', 'allowTextureDowngrade': 0, 'alphaToCoverageThreshold': 0, 'compression': comp,
                      'group': group, 'hasMipchain': int(kind != 'ui'), 'isGamma': gamma, 'isStreamable': int(kind != 'ui'), 'platformMipBiasConsole': 0,
                      'platformMipBiasPC': 0, 'rawFormat': 'TRF_TrueColor'},
            'width': w}
    return {'Header': {'WolvenKitVersion': '9.0.1', 'WKitJsonVersion': '0.0.9', 'GameVersion': 2310, 'DataType': 'CR2W'},
            'Data': {'Version': 195, 'BuildVersion': 0, 'RootChunk': root, 'EmbeddedFiles': []}}


def head_name(kind, w, h, mips): return '%s_%dx%d_%d' % (kind, w, h, mips)


def make_heads(combos):
    """the .xbm headers for these (kind, w, h, mips) not made yet: one WolvenKit run over a folder of tiny ones"""
    todo = [c for c in set(combos) if not os.path.exists(os.path.join(HEADS, head_name(*c) + '.bin'))]
    if not todo: return
    work = os.path.join(HEADS, 'work')
    os.makedirs(work, exist_ok=True)
    for c in todo: json.dump(_json(*c), open(os.path.join(work, head_name(*c) + '.xbm.json'), 'w'))
    paths.wk(['convert', 'd', work], expect=[os.path.join(work, head_name(*c) + '.xbm') for c in todo], what='make texture headers')
    for c in todo:
        b = open(os.path.join(work, head_name(*c) + '.xbm'), 'rb').read()
        obj_end = struct.unpack_from('<I', b, 24)[0]
        open(os.path.join(HEADS, head_name(*c) + '.bin'), 'wb').write(b[:obj_end])
    for f in os.listdir(work): os.remove(os.path.join(work, f))
    os.rmdir(work)


def write(path, kind, w, h, mips, body):
    """an .xbm: its cached header with the buffer entry and CRCs set for this data (stored uncompressed)"""
    hd = bytearray(open(os.path.join(HEADS, head_name(kind, w, h, mips) + '.bin'), 'rb').read())
    buf_off, nbuf = struct.unpack_from('<II', hd, 40 + 5 * 12)
    assert nbuf == 1
    struct.pack_into('<IIII', hd, buf_off + 8, len(hd), len(body), len(body), zlib.crc32(body))   # offset, disk, mem, crc
    struct.pack_into('<I', hd, 28, len(hd) + len(body))                                            # buffers end
    struct.pack_into('<I', hd, 32, 0xDEADBEEF)
    struct.pack_into('<I', hd, 32, zlib.crc32(bytes(hd[:160])))                                  # header CRC
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: f.write(hd); f.write(body)


def dds_parts(dds):
    """(w, h, mips, DXGI format, body) of a DDS as ba2.py writes them"""
    h, w = struct.unpack_from('<II', dds, 12)
    mips = max(1, struct.unpack_from('<I', dds, 28)[0])
    four = dds[84:88]
    fmt = struct.unpack_from('<I', dds, 128)[0] if four == b'DX10' else FOURCC.get(four, 0)
    return w, h, mips, fmt, dds[148 if four == b'DX10' else 128:]


# --- all of a conversion's textures --------------------------------------------------------------------------------

FILES = None
FORCE = '--force' in sys.argv or 'xbm' in os.environ.get('HOMESTEAD_FORCE', '')   # re-make what is already there (workers too)


def _one(job):
    try: return _make(job)
    except Exception as e: return job[0], 'error: %s' % e


def _make(job):
    """(name, kind, source) -> how it was made: 'copied' (Fallout's blocks), 'computed' (roughness), 'png' (a format
    we don't copy: left as a PNG for build.py's WolvenKit step) or 'missing'"""
    global FILES
    import convert
    if FILES is None: FILES = convert.Files()
    name, kind, src = job
    out = os.path.join(convert.FO4, 'archive', convert.DEPOT, 'tex', name + '.xbm')
    if not FORCE and os.path.exists(out): return name, 'kept'
    dds = FILES.read(src)
    if dds is None: return name, 'missing'
    w, h, mips, fmt, body = dds_parts(dds)
    if kind == 'pal':                                       # greyscale to palette: each grey looked up in its gradient
        _, rest = name.split('__pal__')                     # (a row of it), the colour Fallout's shader would make
        grad, row = rest.rsplit('__', 1)
        gd = FILES.read('textures\\' + grad.replace('~', '\\') + '.dds')
        if gd is None: return name, 'missing'
        gw, gh, _, gfmt, gbody = dds_parts(gd)
        if gfmt == 87: G = np.frombuffer(gbody[:gw * gh * 4], np.uint8).reshape(gh, gw, 4)[..., [2, 1, 0]]   # (B8G8R8A8)
        elif gfmt == 28: G = np.frombuffer(gbody[:gw * gh * 4], np.uint8).reshape(gh, gw, 4)[..., :3]
        else: G = np.asarray(Image.open(io.BytesIO(gd)).convert('RGB'))
        line = G[int(round(int(row) / 100 * (gh - 1)))].astype(np.float32)
        t = np.arange(256) / 255 * (gw - 1)                 # (a 256-entry table from grey to colour: an 8k texture
        lo = np.floor(t).astype(int); hi = np.minimum(lo + 1, gw - 1); f = (t - lo)[:, None]   # costs bytes, not GBs)
        lut = (line[lo] * (1 - f) + line[hi] * f).clip(0, 255).astype(np.uint8)
        src = Image.open(io.BytesIO(dds)).convert('RGBA')
        im = Image.fromarray(lut[np.asarray(src.convert('L'))], 'RGB')
        im.putalpha(src.getchannel('A'))
        convert.write_png(im, os.path.join(convert.RAW, convert.DEPOT, 'tex', name + '.png'))
        return name, 'png'
    smooth = int(name[-3:]) / 100 if name[-3:].isdigit() else 1.0
    has = lambda *c: os.path.exists(os.path.join(HEADS, head_name(*c) + '.bin'))
    if kind == 'rough' and has('rough', w, h, _mips(w, h)):
        body, mips = rough_bc4(dds, smooth)
        write(out, 'rough', w, h, mips, body)
        return name, 'computed'
    lay = LAYOUT.get(fmt)
    k = 'normal' if kind == 'normal' else {'bc1': 'color', 'bc3': 'alpha'}.get(lay) if kind == 'color' else None
    if k and KINDS[k][3] == lay and has(k, w, h, mips):
        write(out, k, w, h, mips, flip(body, w, h, mips, lay))
        return name, 'copied'
    im = Image.open(io.BytesIO(dds))                        # anything else: a PNG, as before (convert.py's formulas)
    png = os.path.join(convert.RAW, convert.DEPOT, 'tex', name + '.png')
    if kind == 'normal':
        a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
        x, y = a[..., 0] * 2 - 1, a[..., 1] * 2 - 1
        z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
        im = Image.fromarray((np.dstack([x, y, z]) * 127.5 + 127.5).clip(0, 255).astype(np.uint8))
    elif kind == 'rough':
        g = np.asarray(im.convert('RGB'))[..., 1].astype(np.float32) / 255
        im = Image.fromarray(((2 / (2 ** (10 * g * smooth + 1) + 2)) ** 0.25 * 255).clip(0, 255).astype(np.uint8))
    convert.write_png(im.convert('RGBA') if kind == 'color' else im, png)
    return name, 'png'


def _mips(w, h): return max(w, h).bit_length()           # a full chain down to 1 x 1


def main(pieces=None, workers=None):
    """every texture pieces.json's materials use (a glow's too): headers first (one WolvenKit run), then the files in
    parallel; none when the game has the archive made from these same inputs (build.unchanged)"""
    import build, collections, convert, time
    from multiprocessing import Pool
    t0 = time.time()
    pieces = pieces or json.load(open(os.path.join(convert.FO4, 'pieces.json')))
    if build.unchanged(pieces): print('textures kept: the game has the archive made from them'); return
    jobs = {}
    for p in pieces:                                        # (a lamp's glow mesh too: its glow map can be a texture no
                                                            # other material uses - 15 were never made on a fresh import)
        for m in p['materials'] + [m for part in p.get('parts', []) + [p.get('glow') or {'materials': []}] for m in part['materials']]:
            for slot in ('color', 'normal', 'rough', 'emissive'):             # (a glow map is a colour texture)
                n, kind = m.get(slot), 'color' if slot == 'emissive' else slot
                if n and '__pal__' in n: jobs[n] = (n, 'pal', 'textures\\' + n.split('__pal__')[0] + '.dds')
                elif n: jobs[n] = (n, kind, 'textures\\' + (n.rsplit('_r', 1)[0] if kind == 'rough' else n) + '.dds')
    files = convert.Files()
    combos = set()
    for n, kind, src in jobs.values():                      # sizes from the archives' index (no reading)
        a = files.where.get(src)
        e = a.entries[a.index[src]] if a else {}
        if 'fmt' not in e: continue                         # (a loose .dds: its header says, when it's written)
        lay = LAYOUT.get(e['fmt'])
        k = 'rough' if kind == 'rough' else 'normal' if kind == 'normal' else {'bc1': 'color', 'bc3': 'alpha'}.get(lay)
        if k: combos.add((k, e['w'], e['h'], _mips(e['w'], e['h']) if k == 'rough' else e['mips']))
    make_heads(combos)
    print(len(jobs), 'textures,', len(combos), 'headers (%.0fs)' % (time.time() - t0), flush=True)
    import budget
    todo, res = list(jobs.values()), []
    paths.progress('textures', 0, len(todo))
    with Pool(workers or budget.workers(1.5)) as pool:      # (a big texture's decode: measured ~1.4 GB a worker, 2026-10-02)
        for r in pool.imap_unordered(_one, todo, chunksize=8):
            res.append(r)
            paths.progress('textures', len(res), len(todo))
    print(dict(collections.Counter(r if not r.startswith('error') else 'error' for _, r in res)), '(%.0fs)' % (time.time() - t0), flush=True)
    for n, r in res:
        if r.startswith('error'): print('  ', n, r)


if __name__ == '__main__' and not [a for a in sys.argv[1:] if a != '--force']:
    main()
elif __name__ == '__main__':
    import convert
    tex, out, kind = sys.argv[1:4]
    dds = convert.Files().read(tex)
    w, h, mips, fmt, body = dds_parts(dds)
    if kind == 'rough':
        body, mips = rough_bc4(dds, 1.0)
    else:
        body = flip(body, w, h, mips, LAYOUT[fmt])
    make_heads([(kind, w, h, mips)])
    write(out, kind, w, h, mips, body)
    print(kind, w, h, mips, LAYOUT.get(fmt), len(body), '->', out)
