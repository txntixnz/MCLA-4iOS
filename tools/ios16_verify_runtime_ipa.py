#!/usr/bin/env python3
"""Independently inspect a private native runtime IPA; does not test execution."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import struct
import zipfile

from ios16_verify_aot_archive import version
from mcla_metal_target import validate_library


def inspect_executable(data):
    if len(data) < 32:
        raise ValueError('Truncated Mach-O executable')
    magic, cpu, subtype, kind, count, length, flags, reserved = struct.unpack_from('<8I', data)
    if magic != 0xFEEDFACF or cpu != 0x0100000C or kind != 2:
        raise ValueError('Expected an ARM64 Mach-O executable')
    if 32 + length > len(data):
        raise ValueError('Truncated Mach-O command region')
    cursor, deployment, signature = 32, [], None
    for _ in range(count):
        command, size = struct.unpack_from('<II', data, cursor)
        if size < 8 or cursor + size > 32 + length:
            raise ValueError('Malformed Mach-O command')
        if command == 0x32:
            platform, minimum, sdk, tools = struct.unpack_from('<4I', data, cursor + 8)
            if platform != 2:
                raise ValueError('Executable is not an iOS device build')
            deployment.append(version(minimum))
        if command == 0x1D:
            offset, blob_size = struct.unpack_from('<2I', data, cursor + 8)
            if offset + blob_size > len(data):
                raise ValueError('Truncated code signature')
            signature = data[offset:offset + blob_size]
        cursor += size
    if cursor != 32 + length or deployment != [(16, 0, 0)]:
        raise ValueError(f'Expected one iOS 16.0 deployment command: {deployment}')
    if signature is None or len(signature) < 12:
        raise ValueError('No embedded code signature')
    magic, total, slots = struct.unpack_from('>3I', signature)
    if magic != 0xFADE0CC0 or total > len(signature) or 12 + slots * 8 > total:
        raise ValueError('Malformed signature container')
    entitlements = None
    for index in range(slots):
        kind, offset = struct.unpack_from('>2I', signature, 12 + index * 8)
        if kind != 5:
            continue
        if offset + 8 > total:
            raise ValueError('Malformed entitlement slot')
        magic, blob_size = struct.unpack_from('>2I', signature, offset)
        if magic != 0xFADE7171 or offset + blob_size > total:
            raise ValueError('Malformed entitlement blob')
        entitlements = plistlib.loads(signature[offset + 8:offset + blob_size])
    if not entitlements:
        raise ValueError('Missing native test entitlements')
    for name in ('get-task-allow', 'com.apple.developer.kernel.increased-memory-limit',
                 'com.apple.developer.kernel.extended-virtual-addressing'):
        if entitlements.get(name) is not True:
            raise ValueError(f'Missing memory/debug entitlement: {name}')
    return {'architecture': 'arm64', 'platform': 'iOS device', 'minimum_ios': '16.0.0',
        'executable_sha256': hashlib.sha256(data).hexdigest(),
        'signature_container_present': True, 'entitlements': entitlements,
        'note': 'Structure inspected; Apple codesign verification is recorded by the private build.'}


def verify(path, shader_evidence):
    expected = json.loads(shader_evidence.read_text())
    if expected.get('compiler_passes') != 604 or expected.get('rejections') != 0:
        raise ValueError('Expected complete private shader compilation evidence')
    by_name = {item['library']: item['output_sha256'] for item in expected['results']}
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('IPA CRC check failed')
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate IPA entries')
        for name in names:
            part = PurePosixPath(name)
            if part.is_absolute() or '..' in part.parts:
                raise ValueError('Unsafe IPA entry')
            if part.suffix.lower() in ('.iso', '.xex', '.rpf', '.mobileprovision', '.p12', '.p8'):
                raise ValueError(f'Unexpected source game or provisioning file: {name}')
        roots = [name[:-len('Info.plist')] for name in names
                 if re_app_info(name)]
        if len(roots) != 1:
            raise ValueError('Expected exactly one app bundle')
        root = roots[0]
        info = plistlib.loads(archive.read(root + 'Info.plist'))
        if info.get('MinimumOSVersion') != '16.0':
            raise ValueError('Info.plist minimum is not iOS 16.0')
        if info.get('CFBundleIdentifier') != 'com.txntixnz.mcla.ios16.preview':
            raise ValueError('Unexpected bundle identity; must reuse the isolated preview container')
        executable = info['CFBundleExecutable']
        if PurePosixPath(executable).name != executable:
            raise ValueError('Invalid executable path')
        result = inspect_executable(archive.read(root + executable))
        libraries = [name for name in names if name.endswith('.metallib')]
        if len(libraries) != 604:
            raise ValueError('Expected 603 title libraries and FSR')
        for name in libraries:
            relative = name.removeprefix(root)
            data = archive.read(name)
            validate_library(data, '16.0')
            if by_name.get(relative) != hashlib.sha256(data).hexdigest():
                raise ValueError(f'Shader differs from compiled evidence: {relative}')
        for name in ('mcla_vertex_elements.map', 'mcla_native_shaders.mspv'):
            if root + name not in names:
                raise ValueError(f'Missing native metadata: {name}')
    result.update(status='PASS', ipa=path.name,
        ipa_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        bundle_identifier=info['CFBundleIdentifier'], metal_libraries=604,
        shader_hashes_match_compiler_evidence=True, source_game_files_included=False,
        experimental=True, resource_masks_conservative=True,
        device_launch_tested=False, gameplay_tested=False, performance_tested=False)
    return result


def re_app_info(name):
    parts = PurePosixPath(name).parts
    return len(parts) == 3 and parts[0] == 'Payload' and parts[1].endswith('.app') and parts[2] == 'Info.plist'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ipa', type=Path)
    parser.add_argument('--shader-evidence', required=True, type=Path)
    parser.add_argument('--json', required=True, type=Path)
    args = parser.parse_args()
    report = verify(args.ipa, args.shader_evidence)
    args.json.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'entitlements'}, indent=2))
