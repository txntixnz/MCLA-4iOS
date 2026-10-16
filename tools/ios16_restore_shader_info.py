#!/usr/bin/env python3
"""Recover native renderer interfaces from AIR reflection, with full resource masks.

Vertex semantics and output slots are read from compiler reflection. Resource
masks deliberately include every title texture slot and constant register;
they are conservative and may reduce performance. This does not reconstruct
the missing original Xenos interpolator or loop-constant metadata.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from ios16_air_compat import nodes, reflection


def semantic(name):
    match = re.fullmatch(r'i(Position|Normal|Tangent|Binormal|TexCoord|Color|BlendIndices|BlendWeight)(\d+)', name)
    if not match:
        raise ValueError(f'Unrecognized vertex semantic: {name}')
    kind, index = match[1], int(match[2])
    if kind in ('Position', 'Normal', 'Tangent') and index < 4:
        return {'Position': 0, 'Normal': 4, 'Tangent': 8}[kind] + index
    if kind == 'TexCoord' and index < 16:
        return (13 if index < 4 else 16) + index
    if kind == 'Color' and index < 2:
        return 32 if index else 17
    if index == 0 and kind in ('Binormal', 'BlendIndices', 'BlendWeight'):
        return {'Binormal': 12, 'BlendIndices': 18, 'BlendWeight': 19}[kind]
    raise ValueError(f'Unsupported vertex semantic: {name}')


def field(text, name):
    values = re.findall(r'!"' + re.escape(name) + r'", !"([^"]+)"', text)
    if len(values) != 1:
        raise ValueError(f'Expected one reflection field {name}')
    return values[0]


def decode(path):
    match = re.fullmatch(r'(vs|ps)-([0-9A-F]{16})\.000\.ll', path.name)
    if not match:
        raise ValueError(f'Unexpected title module filename: {path.name}')
    stage, identity = match.groups()
    text = path.read_text()
    reflect = reflection(text)
    expected = 'air.vertex' if stage == 'vs' else 'air.fragment'
    if expected not in reflect or len(set(reflect) & {'air.vertex', 'air.fragment'}) != 1:
        raise ValueError(f'{path.name}: shader stage mismatch')
    if not re.search(r'^define .* @shaderMain\(', text, re.M):
        raise ValueError(f'{path.name}: missing native shaderMain entry point')
    table = nodes(text)
    stage_ref = re.search(r'^!' + expected + r' = !\{!(\d+)\}$', text, re.M)
    entry = table[stage_ref[1]]
    entry_refs = re.findall(r'!(\d+)\b', entry)
    if len(entry_refs) != 2:
        raise ValueError('Unexpected stage reflection layout')
    output_nodes = [table[key] for key in re.findall(r'!(\d+)\b', table[entry_refs[0]])]
    argument_nodes = [table[key] for key in re.findall(r'!(\d+)\b', table[entry_refs[1]])]
    attributes, bindings = [], {}
    for argument in argument_nodes:
        if '!"air.vertex_input"' in argument:
            location = re.search(r'!"air.location_index", i32 (\d+), i32 1', argument)
            typ = re.fullmatch(r'(float|uint|int)([1-4]?)', field(argument, 'air.arg_type_name'))
            if location is None or typ is None:
                raise ValueError('Unsupported vertex input location/type')
            attributes.append({'semantic': semantic(field(argument, 'air.arg_name')),
                'location': int(location[1]), 'components': int(typ[2] or 1),
                'numeric': {'float': 0, 'uint': 1, 'int': 2}[typ[1]]})
        if '!"air.buffer"' in argument or '!"air.indirect_buffer"' in argument:
            location = re.search(r'!"air.location_index", i32 (\d+), i32 1', argument)
            if location is None:
                raise ValueError('Unsupported buffer binding')
            bindings[int(location[1])] = field(argument, 'air.arg_name')
    required = {0: 'g_Texture2DDescriptorHeap', 1: 'g_Texture2DArrayDescriptorHeap',
        2: 'g_Texture3DDescriptorHeap', 3: 'g_TextureCubeDescriptorHeap',
        4: 'g_SamplerDescriptorHeap', 8: 'g_PushConstants'}
    if bindings != required:
        raise ValueError(f'{path.name}: incompatible renderer buffer bindings: {bindings}')
    if len(attributes) > 31 or len({a['location'] for a in attributes}) != len(attributes):
        raise ValueError('Invalid/duplicate vertex input locations')
    if any(a['location'] >= 31 for a in attributes):
        raise ValueError('Vertex input location exceeds Metal device limit')
    if len({a['semantic'] for a in attributes}) != len(attributes):
        raise ValueError('Ambiguous duplicate vertex semantics')
    colors = 0
    for output in output_nodes:
        color = re.search(r'!"air.render_target", i32 (\d+), i32 0', output)
        if color:
            index = int(color[1])
            if index >= 4:
                raise ValueError('Unexpected title color output')
            colors |= 1 << index
    return {'hash': identity, 'vertex': stage == 'vs', 'attributes': attributes,
        'textures': 0x3FFFFFF, 'colors': colors, 'constants': [0xFFFFFFFFFFFFFFFF] * 4,
        'reflection_sha256': hashlib.sha256(json.dumps(reflect, sort_keys=True).encode()).hexdigest()}


def create(source, destination, report):
    paths = sorted(source.glob('*-[0-9A-F]*.000.ll'))
    if not paths:
        raise ValueError('No title AIR inspection modules found')
    entries = [decode(path) for path in paths]
    if len({(e['hash'], e['vertex']) for e in entries}) != len(entries):
        raise ValueError('Duplicate shader identity')
    lines = ['// Recovered AIR interfaces; conservative resource masks. Experimental.',
        '#pragma once', '#include <cstdint>',
        'struct MCLAMetalAttribute { uint8_t semantic, location, components, numeric; };',
        'struct MCLAMetalShaderInfo { uint64_t hash; bool vertex; uint32_t textures, colors; uint64_t constants[4]; uint32_t count; MCLAMetalAttribute attributes[32]; };',
        'inline constexpr MCLAMetalShaderInfo kMCLAMetalShaders[] = {']
    for entry in entries:
        attributes = ','.join('{%(semantic)d,%(location)d,%(components)d,%(numeric)d}' % a for a in entry['attributes'])
        masks = ','.join(f'0x{value:016X}ull' for value in entry['constants'])
        lines.append('{0x%sull,%s,0x%Xu,0x%Xu,{%s},%d,{%s}},' % (
            entry['hash'], str(entry['vertex']).lower(), entry['textures'], entry['colors'],
            masks, len(entry['attributes']), attributes))
    lines += ['};', '']
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(lines))
    result = {'experimental': True, 'conservative_resource_masks': True,
        'texture_slots_per_shader': 26, 'constant_registers_per_shader': 256,
        'device_validation_performed': False, 'shader_count': len(entries),
        'vertex_count': sum(e['vertex'] for e in entries),
        'pixel_count': sum(not e['vertex'] for e in entries),
        'header_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'entries': entries}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Restored {len(entries)} shader interfaces; resource masks are conservative, performance unmeasured.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    create(args.source, args.destination, args.report)
