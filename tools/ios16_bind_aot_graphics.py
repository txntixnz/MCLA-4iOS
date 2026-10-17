#!/usr/bin/env python3
"""Bind native graphics hooks to the symbols in a private generated AOT table.

The desktop and XEO3 manifests name the same CE addresses differently. Inspect
both dispatch tables instead of assuming the desktop spelling. Translated
instruction bodies are neither read nor changed.
"""
import argparse
import json
from pathlib import Path
import re
import struct


HOOKS = (
    (0x8217B7B0, 'grcDevice_EndFrame'),
    (0x82412990, 'D3DDevice_BlockUntilIdle'),
    (0x824195E8, 'rex_sub_824195E8'),
    (0x82419E98, 'D3DDevice_Swap'),
    (0x8241BE78, 'D3DDevice_BeginTiling'),
    (0x8241C308, 'D3DDevice_EndTiling'),
    (0x8241CD88, 'D3DDevice_BeginVertices'),
    (0x8241D220, 'D3DDevice_EndVertices'),
    (0x8241D230, 'D3DDevice_DrawVertices'),
    (0x8241D620, 'D3DDevice_DrawIndexedVertices'),
    (0x82420BA8, 'D3DDevice_Resolve'),
    (0x82421F38, 'rex_sub_82421F38'),
    (0x824221D8, 'D3DResource_Release'),
)


def table(text, pattern):
    result = {}
    for address, symbol in re.findall(pattern, text):
        address = int(address, 16)
        if address in result:
            raise ValueError(f'Duplicate AOT address: {address:08X}')
        result[address] = symbol
    return result


def bindings(directory):
    mappings = table((directory / 'larecomp_init.cpp').read_text(),
                     r'\{\s*0x([0-9A-Fa-f]+)\s*,\s*(\w+)\s*\}')
    registered = table((directory / 'larecomp_register.cpp').read_text(),
                       r'SetFunction\(\s*0x([0-9A-Fa-f]+)\s*,\s*(\w+)\s*\)')
    declared = set(re.findall(r'DECLARE_REX_FUNC\((\w+)\)',
                             (directory / 'larecomp_init.h').read_text()))
    result, conventions = [], set()
    for address, hook in HOOKS:
        symbol = mappings.get(address)
        anonymous = f'rex_sub_{address:08X}'
        if symbol not in (hook, anonymous):
            raise ValueError(f'Missing or unexpected graphics mapping: {hook} at {address:08X}')
        if registered.get(address) != symbol or symbol not in declared:
            raise ValueError(f'Inconsistent graphics declaration/registration: {hook}')
        if hook != anonymous:
            conventions.add('named' if symbol == hook else 'address')
        result.append({'address': address, 'hook': hook, 'symbol': symbol})
    if len(conventions) != 1:
        raise ValueError('Mixed graphics naming conventions in the AOT tables')
    return {'naming': conventions.pop(), 'hook_count': len(result), 'hooks': result}


def header(report):
    lines = ['// Generated from the private AOT dispatch tables. Do not edit.',
             '#pragma once', '',
             f'#define MCLA_AOT_GRAPHICS_NAMING "{report["naming"]}"', '']
    for item in report['hooks']:
        hook, symbol = item['hook'], item['symbol']
        if hook != symbol:
            lines += [f'#define {hook} {symbol}',
                      f'#define rex_generated_{hook} rex_generated_{symbol}']
    lines += ['', '#define MCLA_FOR_EACH_AOT_GRAPHICS_HOOK(X) \\']
    for index, item in enumerate(report['hooks']):
        continuation = ' \\' if index + 1 < len(report['hooks']) else ''
        lines.append(f'    X(0x{item["address"]:08X}u, {item["hook"]}, "{item["hook"]}"){continuation}')
    return '\n'.join(lines) + '\n'


def macho_symbols(data):
    if len(data) < 32:
        raise ValueError('Truncated Mach-O header')
    magic, cpu, subtype, kind, count, length, flags, reserved = struct.unpack_from('<8I', data)
    if magic != 0xFEEDFACF or cpu != 0x0100000C or kind != 2:
        raise ValueError('Expected an ARM64 Mach-O executable')
    cursor, symtab = 32, None
    for _ in range(count):
        if cursor + 8 > min(32 + length, len(data)):
            raise ValueError('Truncated load commands')
        command, size = struct.unpack_from('<II', data, cursor)
        if size < 8 or cursor + size > min(32 + length, len(data)):
            raise ValueError('Malformed load command')
        if command == 2:
            if size != 24 or symtab is not None:
                raise ValueError('Malformed symbol table command')
            symtab = struct.unpack_from('<4I', data, cursor + 8)
        cursor += size
    if cursor != 32 + length or symtab is None:
        raise ValueError('Missing or malformed symbol table')
    offset, count, strings, string_bytes = symtab
    if offset + count * 16 > len(data) or strings + string_bytes > len(data):
        raise ValueError('Truncated symbol table')
    result = {}
    for index in range(count):
        name_offset, kind, section, description, value = struct.unpack_from('<IBBHQ', data, offset + index * 16)
        if name_offset >= string_bytes:
            raise ValueError('Invalid symbol name offset')
        end = data.find(b'\0', strings + name_offset, strings + string_bytes)
        if end < 0:
            raise ValueError('Unterminated symbol name')
        name = data[strings + name_offset:end].decode('utf-8')
        if not kind & 0xE0:  # Exclude debug symbols.
            result[name] = {'kind': kind, 'section': section, 'description': description, 'value': value}
    return result


def verify_executable(data, report):
    symbols = macho_symbols(data)
    checked = []
    for item in report['hooks']:
        symbol = symbols.get('_' + item['symbol'])
        # N_EXT | N_SECT, a real section, and no N_WEAK_DEF. A weak AOT
        # forwarding wrapper at the right address is precisely the old bug.
        if (symbol is None or symbol['kind'] != 0x0F or not symbol['section']
                or not symbol['value'] or symbol['description'] & 0x80):
            raise ValueError(f'Native graphics hook is absent or weak: {item["hook"]} ({item["symbol"]})')
        checked.append({'hook': item['hook'], 'symbol': item['symbol'], 'strong': True})
    return {'naming': report['naming'], 'strong_hook_count': len(checked), 'hooks': checked,
            'device_rendering_tested': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    generate = commands.add_parser('generate')
    generate.add_argument('generated', type=Path)
    generate.add_argument('--header', type=Path, required=True)
    generate.add_argument('--report', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('executable', type=Path)
    verify.add_argument('--bindings', type=Path, required=True)
    verify.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'generate':
        result = bindings(args.generated)
        args.header.parent.mkdir(parents=True, exist_ok=True)
        args.header.write_text(header(result))
        print(f'Bound {result["hook_count"]} native graphics hooks to {result["naming"]} AOT symbols.')
    else:
        result = verify_executable(args.executable.read_bytes(), json.loads(args.bindings.read_text()))
        print(f'Verified {result["strong_hook_count"]} strong graphics hook definitions in the linked executable.')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
