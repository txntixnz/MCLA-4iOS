#!/usr/bin/env python3
"""Extract intact LLVM AIR modules for compiler inspection; never retarget bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def extract(data):
    if not data.startswith(b'MTLB'):
        raise ValueError('Expected a Metal library')
    cursor, modules = 0, []
    while True:
        cursor = data.find(bytes.fromhex('dec0170b'), cursor)
        if cursor < 0:
            break
        if cursor + 20 > len(data):
            break
        magic, version, offset, length, cpu = struct.unpack_from('<5I', data, cursor)
        begin, end = cursor + offset, cursor + offset + length
        if version == 0 and offset >= 20 and end <= len(data) and data[begin:begin+4] == b'BC\xc0\xde':
            modules.append(data[begin:end])
            cursor = end
        else:
            cursor += 4
    if not modules:
        raise ValueError('No intact LLVM bitcode wrappers found')
    return modules


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('library', type=Path)
    ap.add_argument('output', type=Path)
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    source = a.library.read_bytes()
    modules = extract(source)
    report = {'source': a.library.name, 'source_sha256': hashlib.sha256(source).hexdigest(),
              'retargeting_performed': False, 'modules': []}
    for i, module in enumerate(modules):
        filename = f'module-{i:03}.bc'
        (a.output / filename).write_bytes(module)
        report['modules'].append({'file': filename, 'bytes': len(module),
                                  'sha256': hashlib.sha256(module).hexdigest()})
    (a.output / 'extraction.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Extracted {len(modules)} intact AIR module(s); no targets or instructions changed')


if __name__ == '__main__':
    main()
