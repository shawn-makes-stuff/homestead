"""Fallout 4 .ba2 archives (BTDX): list and read files. GNRL (meshes, sounds, strings...) and DX10 (textures, rebuilt
as .dds with a DX10 header). Versions 1 (original) and 7 / 8 (2024 next-gen update) share one layout.
Layout: FO4_RESEARCH.md, section 1 (xEdit wbBSArchive.pas; the Rust ba2 crate).
  python tools/fo4/ba2.py <archive> [substring]      list (files whose path contains substring)
"""
import mmap, os, struct, sys, zlib

SENTINEL = 0xBAADF00D


class Archive:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        self.m = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        magic, self.version, self.kind, count, names = struct.unpack_from('<4sI4sIQ', self.m, 0)
        assert magic == b'BTDX' and self.version in (1, 7, 8), (path, magic, self.version)
        self.kind = self.kind.decode()
        self.entries, off = [], 0x18
        for _ in range(count):
            if self.kind == 'GNRL':
                h, ext, dh, _mod, nchunk, _hs, data, packed, size, sent = struct.unpack_from('<I4sIBBHQIII', self.m, off)
                assert sent == SENTINEL and nchunk == 1, (path, off)
                self.entries.append({'chunks': [(data, packed, size)]})
                off += 36
            else:
                h, ext, dh, _mod, nchunk, _hs, height, width, mips, fmt, flags, _tile = struct.unpack_from('<I4sIBBHHHBBBB', self.m, off)
                off += 24
                chunks = []
                for _ in range(nchunk):
                    data, packed, size, _m0, _m1, sent = struct.unpack_from('<QIIHHI', self.m, off)
                    assert sent == SENTINEL, (path, off)
                    chunks.append((data, packed, size))
                    off += 24
                self.entries.append({'chunks': chunks, 'w': width, 'h': height, 'mips': mips, 'fmt': fmt, 'cube': flags & 1})
        self.names = []
        if names:
            o = names
            for _ in range(count):
                n, = struct.unpack_from('<H', self.m, o)
                self.names.append(self.m[o + 2:o + 2 + n].decode('cp1252').replace('/', '\\').lower())
                o += 2 + n
        self.index = {n: i for i, n in enumerate(self.names)}

    def _chunk(self, data, packed, size):
        raw = self.m[data:data + (packed or size)]
        if not packed: return raw
        try: return zlib.decompress(raw)
        except zlib.error: return zlib.decompress(raw, -15)

    def read(self, name):
        """a file's bytes by its path (as in the archive, any case); textures come back as a whole .dds"""
        e = self.entries[self.index[name.lower().replace('/', '\\')]]
        body = b''.join(self._chunk(*c) for c in e['chunks'])
        if self.kind == 'GNRL': return body
        return dds_header(e['w'], e['h'], e['mips'], e['fmt'], e['cube']) + body


# DXGI format -> the classic FourCC most tools read (BC1-5); everything else (BC7, sRGB, ...) gets the DX10 header
LEGACY = {70: b'DXT1', 71: b'DXT1', 72: b'DXT1', 73: b'DXT3', 74: b'DXT3', 75: b'DXT3', 76: b'DXT5', 77: b'DXT5', 78: b'DXT5',
          79: b'BC4U', 80: b'BC4U', 81: b'BC4S', 82: b'ATI2', 83: b'ATI2', 84: b'BC5S'}


def dds_header(w, h, mips, fmt, cube):
    """'DDS ' + DDS_HEADER (+ DDS_HEADER_DXT10 unless a classic FourCC fits)"""
    four = LEGACY.get(fmt, b'DX10')
    caps = 0x1000 | (0x400008 if mips > 1 else 0) | (0x8 if cube else 0)
    hdr = struct.pack('<7I44x', 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000, h, w, 0, 1, max(mips, 1))
    pf = struct.pack('<2I4s5I', 32, 0x4, four, 0, 0, 0, 0, 0)
    tail = struct.pack('<4I4x', caps, 0xFE00 if cube else 0, 0, 0)
    dx10 = struct.pack('<5I', fmt, 3, 4 if cube else 0, 1, 0) if four == b'DX10' else b''
    return b'DDS ' + hdr + pf + tail + dx10


if __name__ == '__main__':
    a = Archive(sys.argv[1])
    sub = sys.argv[2].lower() if len(sys.argv) > 2 else ''
    print('%s: BTDX v%d %s, %d files, names %s' % (os.path.basename(a.path), a.version, a.kind, len(a.entries), bool(a.names)))
    for n in a.names:
        if sub in n: print(n)
