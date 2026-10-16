#!/usr/bin/env python3
"""Verify every private title object is device ARM64 with an iOS 16-safe target.

Reads archive and Mach-O metadata only. It does not disassemble or print game
instructions. A passing archive is a CPU compilation result, not a linked IPA.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

AR_MAGIC = b'!<arch>\n'
MH_MAGIC_64 = 0xfeedfacf
CPU_TYPE_ARM64 = 0x0100000c
MH_OBJECT = 1
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN_IPHONEOS = 0x25


def version(value):
    return value >> 16, (value >> 8) & 255, value & 255


def members(data):
    if not data.startswith(AR_MAGIC):
        raise ValueError('Expected a thin Unix static archive')
    cursor, names = len(AR_MAGIC), b''
    while cursor < len(data):
        if cursor + 60 > len(data):
            raise ValueError('Truncated archive member header')
        header = data[cursor:cursor + 60]
        if header[58:60] != b'`\n':
            raise ValueError('Invalid archive member marker')
        try:
            size = int(header[48:58].decode('ascii').strip())
        except (UnicodeDecodeError, ValueError) as error:
            raise ValueError('Invalid archive member size') from error
        start, end = cursor + 60, cursor + 60 + size
        if size < 0 or end > len(data):
            raise ValueError('Archive member extends beyond file')
        name = header[:16].decode('ascii').strip()
        payload = data[start:end]
        if name.startswith('#1/'):
            length = int(name[3:])
            if length < 0 or length > len(payload):
                raise ValueError('Invalid BSD archive name')
            name = payload[:length].rstrip(b'\0').decode('utf-8')
            payload = payload[length:]
        elif name == '//':
            names = payload
        elif name.startswith('/') and name[1:].isdigit():
            offset = int(name[1:])
            if offset >= len(names):
                raise ValueError('Invalid GNU archive name offset')
            finish = names.find(b'/\n', offset)
            if finish < 0:
                raise ValueError('Unterminated GNU archive name')
            name = names[offset:finish].decode('utf-8')
        elif name not in ('/', '//', '/SYM64/'):
            name = name.rstrip('/')
        if name not in ('/', '//', '/SYM64/') and not name.startswith('__.SYMDEF'):
            yield name, payload
        cursor = end + (size & 1)
    if cursor != len(data):
        raise ValueError('Truncated archive alignment padding')


def inspect_object(name, data, maximum=(16, 0, 0)):
    if len(data) < 32:
        raise ValueError(f'{name}: truncated object')
    magic, cpu, subtype, kind, count, command_bytes, flags, reserved = struct.unpack_from('<8I', data)
    if magic != MH_MAGIC_64 or cpu != CPU_TYPE_ARM64 or kind != MH_OBJECT:
        raise ValueError(f'{name}: expected an ARM64 Mach-O object')
    if 32 + command_bytes > len(data):
        raise ValueError(f'{name}: truncated Mach-O commands')
    cursor, targets = 32, []
    for _ in range(count):
        if cursor + 8 > 32 + command_bytes:
            raise ValueError(f'{name}: invalid Mach-O command count')
        command, size = struct.unpack_from('<II', data, cursor)
        if size < 8 or cursor + size > 32 + command_bytes:
            raise ValueError(f'{name}: invalid Mach-O command size')
        if command == LC_BUILD_VERSION:
            if size < 24:
                raise ValueError(f'{name}: truncated build version')
            platform, minimum, sdk, tools = struct.unpack_from('<4I', data, cursor + 8)
            if platform != 2:
                raise ValueError(f'{name}: platform {platform}, expected iOS device (2)')
            targets.append(version(minimum))
        elif command == LC_VERSION_MIN_IPHONEOS:
            if size < 16:
                raise ValueError(f'{name}: truncated iPhoneOS version')
            targets.append(version(struct.unpack_from('<I', data, cursor + 8)[0]))
        cursor += size
    if cursor != 32 + command_bytes or len(targets) != 1:
        raise ValueError(f'{name}: missing or ambiguous iOS deployment target')
    if targets[0] > maximum:
        raise ValueError(f'{name}: target {targets[0]} exceeds {maximum}')
    return {'member': name, 'architecture': 'arm64', 'platform': 'iOS device',
            'minimum_ios': '.'.join(map(str, targets[0])), 'bytes': len(data)}


def verify(path, expected_count=62):
    data = path.read_bytes()
    objects = [inspect_object(name, payload) for name, payload in members(data)]
    if len(objects) != expected_count:
        raise ValueError(f'{len(objects)} objects found, expected {expected_count}')
    names = [obj['member'] for obj in objects]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate archive object names')
    return {'status': 'PASS', 'archive': path.name,
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
            'object_count': len(objects), 'architecture': 'arm64',
            'platform': 'iOS device', 'maximum_allowed_ios': '16.0.0',
            'linking_tested': False, 'gameplay_tested': False, 'objects': objects}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    ap.add_argument('--expected-objects', type=int, default=62)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    try:
        report = verify(a.archive, a.expected_objects)
    except (ValueError, OSError) as error:
        ap.exit(2, str(error) + '\n')
    if a.json:
        a.json.write_text(json.dumps(report, indent=2) + '\n')
    print(f"PASS: {report['object_count']} ARM64 title objects; all target iOS 16.0 or earlier")


if __name__ == '__main__':
    main()
