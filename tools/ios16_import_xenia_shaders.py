#!/usr/bin/env python3
"""Import a private Xenia dump into MCLA's guest-byte-order shader corpus.

Xenia .ucode.bin files contain host-order (little-endian) dwords. The title
renderer hashes big-endian guest bytes after normalizing vertex fetches.
Keep all raw variants: multiple patched declarations can share one identity.
Reference iOS 18 libraries are compared by name only, never installed as iOS 16
build inputs. An inventory match is not a successful translation or compilation.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

NAME = re.compile(r'shader_([0-9A-Fa-f]{16})\.ucode\.bin\.(vert|frag)$')
MASK64 = (1 << 64) - 1


def guest_bytes(raw, order='little'):
    if not raw or len(raw) % 12 or len(raw) > 65536:
        raise ValueError('Microcode must contain 1..65536 bytes in 96-bit instructions')
    if order == 'big':
        return raw
    return b''.join(raw[i:i+4][::-1] for i in range(0, len(raw), 4))


def exec_blocks(data):
    """Keep parity with pinned larecomp/src/native_gfx/shader_identity.cpp."""
    limit, i = len(data) // 4, 0
    blocks = []
    while i + 2 < limit:
        d0, d1, d2 = struct.unpack_from('>III', data, i * 4)
        pairs = ((d0, d1 & 65535), ((d1 >> 16) | ((d2 << 16) & 0xffffffff), d2 >> 16))
        for w0, w1 in pairs:
            opcode = (w1 >> 12) & 15
            if not (1 <= opcode <= 7 or opcode in (13, 14)):
                continue
            address = w0 & 4095
            if address and address * 3 < limit:
                limit = address * 3
            if address:
                blocks.append((address, (w0 >> 12) & 7, (w0 >> 16) & 4095))
        i += 3
    return blocks


def vertex_fetches(data):
    found = {}
    for address, count, sequence in exec_blocks(data):
        for k in range(min(count, 6)):
            offset = (address + k) * 12
            if not (sequence >> (k * 2)) & 1 or offset + 12 > len(data):
                continue
            w0, w1, w2 = struct.unpack_from('>III', data, offset)
            if w0 & 31:
                continue
            found[address + k] = {
                'address': address + k, 'fetch_slot': (w0 >> 20) & 127,
                'offset_bytes': ((w2 >> 8) & 0x7fffff) * 4,
                'stride_bytes': (w2 & 255) * 4, 'format': (w1 >> 16) & 63,
                'destination_swizzle': w1 & 4095,
                'computed_index': bool(((w0 >> 5) & 63) or ((w0 >> 30) & 3)),
            }
    return [found[key] for key in sorted(found)]


def normalize(data):
    result = bytearray(data)
    for fetch in vertex_fetches(data):
        offset = fetch['address'] * 12
        result[offset:offset + 12] = bytes(12)
    return bytes(result)


def identity(data):
    h = 0xcbf29ce484222325
    for value in normalize(data):
        h = ((h ^ value) * 0x100000001b3) & MASK64
    return f'{h:016X}'


def read_vertex_map(path):
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError('Truncated vertex map')
    magic, version, count, refs = struct.unpack_from('<4sIII', data)
    end = 16 + count * 16
    if magic != b'MVEM' or version != 1 or len(data) != end + refs * 4:
        raise ValueError('Unsupported vertex map')
    result = {}
    for i in range(count):
        key, first, length = struct.unpack_from('<QII', data, 16 + i * 16)
        if first + length > refs or f'{key:016X}' in result:
            raise ValueError('Invalid vertex map entry')
        result[f'{key:016X}'] = list(struct.unpack_from(f'<{length}I', data, end + first * 4))
    return result


def source_files(path):
    if path.is_dir():
        for file in sorted(path.rglob('*')):
            if file.is_file() and NAME.fullmatch(file.name):
                yield file.name, file.read_bytes()
    else:
        with zipfile.ZipFile(path) as archive:
            seen = set()
            for item in sorted(archive.infolist(), key=lambda item: item.filename):
                name = Path(item.filename).name
                if not NAME.fullmatch(name):
                    continue
                if name in seen or item.file_size > 65536:
                    raise ValueError('Duplicate shader name or oversized microcode')
                seen.add(name)
                yield name, archive.read(item)


def import_dump(source, output, order='little', reference_app=None):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be a new or empty private directory')
    output.mkdir(parents=True, exist_ok=True)
    for name in ('shaders', 'variants'):
        (output / name).mkdir()
    libraries, vertex_map = set(), {}
    if reference_app:
        libraries = {p.stem for p in (reference_app / 'MCLAMetalShaders').glob('*.metallib')}
        vertex_map = read_vertex_map(reference_app / 'mcla_vertex_elements.map')
    records, programs = [], {}
    for filename, raw in source_files(source):
        match = NAME.fullmatch(filename)
        stage = 'vs' if match[2] == 'vert' else 'ps'
        data = guest_bytes(raw, order)
        key = stage + '-' + identity(data)
        canonical = output / 'shaders' / (key + '.bin')
        previous = programs.get(key)
        if previous is not None and normalize(previous) != normalize(data):
            raise ValueError('Normalized identity collision: ' + key)
        if previous is None:
            programs[key] = data
            canonical.write_bytes(data)
        variant = 'variants/' + key + '-' + match[1].upper() + '.bin'
        (output / variant).write_bytes(data)
        fetches = vertex_fetches(data)
        elements = vertex_map.get(key[3:]) if stage == 'vs' else None
        records.append({
            'source': filename, 'xenia_hash': match[1].upper(), 'stage': stage,
            'identity': key[3:], 'bytes': len(data), 'guest_sha256': hashlib.sha256(data).hexdigest(),
            'canonical': 'shaders/' + key + '.bin', 'variant': variant,
            'reference_library_present': key in libraries if reference_app else None,
            'reference_vertex_elements': elements,
            'vertex_fetches': fetches if stage == 'vs' else [],
        })
    if not records:
        raise ValueError('No Xenia microcode files found')
    stages = Counter(r['stage'] for r in records)
    unique = Counter(key[:2] for key in programs)
    missing = sorted({r['stage'] + '-' + r['identity'] for r in records
                      if r['reference_library_present'] is False})
    summary = {
        'input_dword_order': order, 'output_dword_order': 'big',
        'captured_variants': len(records), 'variant_stages': dict(stages),
        'normalized_programs': len(programs), 'normalized_stages': dict(unique),
        'reference_comparison': bool(reference_app),
        'variants_matching_reference_libraries': sum(r['reference_library_present'] is True for r in records),
        'programs_without_reference_library': missing,
        'vertex_programs_with_reference_elements': len({r['identity'] for r in records
                            if r['reference_vertex_elements'] is not None}),
        'metal_sources_generated': 0, 'ios16_libraries_compiled': 0,
        'remaining_inputs': ['Vertex and pixel interpolator descriptors',
                            'Vertex element metadata not covered by the reference map',
                            'Real loop/integer constants where shaders use loops',
                            'Offline Metal 3.0 compilation and validation for iOS 16'],
    }
    manifest = {'format': 'MCLA-Xenia-import-v1', 'summary': summary, 'programs': records}
    (output / 'shader_import.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--input-dword-order', choices=('little', 'big'), default='little')
    ap.add_argument('--reference-app', type=Path, help='Optional extracted upstream app, comparison only')
    a = ap.parse_args()
    try:
        manifest = import_dump(a.source, a.output, a.input_dword_order, a.reference_app)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        ap.exit(2, str(error) + '\n')
    print(json.dumps(manifest['summary'], indent=2))


if __name__ == '__main__':
    main()
