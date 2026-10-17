#!/usr/bin/env python3
"""Build a PRIVATE, capture-derived supplement without replacing audited shaders."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from ios16_extract_air import extract
from ios16_restore_shader_info import decode
from mcla_metal_target import validate_library

ROOT = Path(__file__).resolve().parents[1]

def run(args):
    subprocess.run([str(a) for a in args], check=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(inputs, out):
    data = json.loads(inputs.read_text())
    missing = data['missing']
    if not missing or len(set(missing)) != len(missing) or any(
        not re.fullmatch(r'(vs|ps)-[0-9A-F]{16}', name) for name in missing):
        raise ValueError('Invalid observed missing-shader set')
    capture = out / 'capture'
    for name, item in data['files'].items():
        if name != 'manifest.jsonl' and not re.fullmatch(
            r'(shaders|metadata|declarations|fetch)/[a-z-]+[0-9A-F]{16}\.bin', name):
            raise ValueError(f'Unexpected capture path {name}')
        payload = base64.b64decode(item['base64'], validate=True)
        if len(payload) > 65536 or hashlib.sha256(payload).hexdigest() != item['sha256']:
            raise ValueError(f'Invalid captured bytes {name}')
        path = capture / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    containers = out / 'containers'
    compiler = out / 'shader-containers'
    patcher = out / 'patch-abi'
    run(['xcrun', 'clang++', '-std=c++20', '-O2', ROOT/'tools/mcla_shader_containers.cpp', '-o', compiler])
    run([compiler, capture, containers])
    run(['xcrun', 'clang++', '-std=c++20', '-O2', ROOT/'tools/patch_mcla_shader_abi.cpp', '-o', patcher])
    source = out / 'hlsl'
    source.mkdir(parents=True, exist_ok=True)
    for name in missing:
        path = source / (name+'.hlsl')
        run([ROOT/'tools/build-mcla-alu/mcla-xenosrecomp', containers/(name+'.bin'),
             path, ROOT/'tools/mcla-xenosrecomp/shader_common.h'])
        # Same audited no-op-fetch cleanup as add_mcla_shader_gap.py.
        text = re.sub(r'^[\t ]*r[0-9]+\. = .*\n', '', path.read_text(), flags=re.M)
        path.write_text(text)
        run([patcher, path, name[:2]])
    (out/'inputs.json').write_text(json.dumps(data, indent=2)+'\n')
    print(f'Prepared {len(missing)} observed shader sources from device metadata.', flush=True)

def varyings(text, vertex):
    # AIR metadata nodes preserve shader input/output names and numeric types.
    result = {}
    role = 'vertex_output' if vertex else 'fragment_input'
    for line in text.splitlines():
        if f'!"air.{role}"' not in line:
            continue
        name = re.search(r'!"user\(([^)]+)\)"', line)
        typ = re.search(r'!"air.arg_type_name", !"([^"]+)"', line)
        if name and typ:
            key = name[1].upper()
            if key in result: raise ValueError('Duplicate varying '+key)
            result[key] = typ[1]
    return result

def merge(base, work, out):
    data = json.loads((work/'inputs.json').read_text())
    report = json.loads((base/'compatibility-report.json').read_text())
    if report['compiler_passes'] != 604 or report['rejections'] or len(report['results']) != 604:
        raise ValueError('Expected complete audited 604-library baseline')
    for entry in report['results']:
        if sha(base/'libraries'/entry['library']) != entry['output_sha256']:
            raise ValueError('Baseline hash mismatch: '+entry['library'])
    shutil.copytree(base, out, dirs_exist_ok=True)
    original = {entry['library']:entry['output_sha256'] for entry in report['results']}
    generated = json.loads((work/'metal/manifest.json').read_text())
    if {entry['shader'] for entry in generated} != set(data['missing']) or any('error' in entry for entry in generated):
        raise ValueError('Incomplete captured supplement')
    flat = work/'reflection'
    flat.mkdir(exist_ok=True)
    added = []
    for name in data['missing']:
        relative = 'MCLAMetalShaders/'+name+'.metallib'
        if relative in original: raise ValueError('Refusing to replace audited shader '+name)
        library = work/'metal'/(name+'.metallib')
        validate_library(library.read_bytes(), '16.0')
        modules = extract(library.read_bytes())
        if len(modules) != 1: raise ValueError('Expected one shader module: '+name)
        directory = out/'modules/MCLAMetalShaders'/name
        directory.mkdir(parents=True, exist_ok=True)
        air = directory/'module-000.bc'
        air.write_bytes(modules[0])
        ll = directory/'module-000.ll'
        run(['xcrun','-sdk','iphoneos','metal','-x','ir','-mios-version-min=16.0',
             '-S','-emit-llvm',air,'-o',ll])
        inspection = flat/(name+'.000.ll')
        shutil.copyfile(ll, inspection)
        interface = decode(inspection)
        target = out/'libraries'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(library, target)
        entry = {'library':relative, 'output_sha256':sha(target),
                 'captured_source':name, 'reflection_verified':True,
                 'interface':interface}
        report['results'].append(entry)
        added.append(entry)
    # Check every observed pairing, including an existing companion PS.
    pairs = []
    for line in (work/'capture/manifest.jsonl').read_text().splitlines():
        item = json.loads(line)
        vs, ps = 'vs-'+item['vs'], 'ps-'+item['ps']
        if item['ps'] == '0000000000000000': continue
        vertex = out/'modules/MCLAMetalShaders'/vs/'module-000.ll'
        pixel = out/'modules/MCLAMetalShaders'/ps/'module-000.ll'
        if not vertex.exists() or not pixel.exists(): raise ValueError('Uncompiled observed shader pair')
        outputs, inputs = varyings(vertex.read_text(), True), varyings(pixel.read_text(), False)
        if any(outputs.get(name) != typ for name,typ in inputs.items()):
            raise ValueError('Observed varying mismatch: '+vs+' / '+ps)
        pair={'vs':vs,'ps':ps,'pixel_inputs':inputs}
        if pair not in pairs: pairs.append(pair)
    for name,digest in original.items():
        if sha(out/'libraries'/name) != digest: raise ValueError('Original shader changed during merge')
    report.update(compiler_passes=len(report['results']), rejections=0,
                  supplement={'added':len(added),'base_libraries_unchanged':604,
                              'observed_pairs':pairs})
    (out/'compatibility-report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'supplement-report.json').write_text(json.dumps({'added':added,'pairs':pairs},indent=2)+'\n')
    print(f'Verified {len(added)} new shaders; all 604 original libraries unchanged.', flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('inputs',type=Path);p.add_argument('out',type=Path)
    m=commands.add_parser('merge');m.add_argument('base',type=Path);m.add_argument('work',type=Path);m.add_argument('out',type=Path)
    args=parser.parse_args()
    if args.command=='prepare': prepare(args.inputs,args.out)
    else: merge(args.base,args.work,args.out)
