#!/usr/bin/env python3
"""Compiler experiment for a restricted AIR 2.7 subset, never a shipping guarantee.

This extracts original modules, edits textual IR, and invokes Apple's compiler
and linker to create NEW libraries. It never patches a metallib container.
The comparison command requires the adaptation to match a direct iOS 16 source
compilation exactly. Device pipeline creation and rendering remain untested.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess

from ios16_extract_air import extract
from mcla_metal_target import validate_library

INTRINSICS = frozenset('''
air.any.v2i1 air.convert.f.f32.s.i32 air.convert.f.f32.u.i1
air.convert.f.f32.u.i32 air.convert.f.v2f16.f.v2f32
air.convert.f.v2f32.u.v2i1 air.convert.f.v2f32.u.v2i32
air.convert.f.v3f32.u.v3i1 air.convert.f.v4f32.u.v4i1
air.convert.s.i32.f.f32 air.convert.s.v2i32.f.v2f32
air.convert.u.v2i32.f.v2f32 air.discard_fragment
air.dot.v2f32 air.dot.v3f32 air.dot.v4f32 air.fast_clamp.f32
air.fast_clamp.v4f32 air.fast_cos.f32 air.fast_exp2.f32
air.fast_fabs.f32 air.fast_fabs.v2f32 air.fast_fabs.v3f32
air.fast_fabs.v4f32 air.fast_floor.f32 air.fast_floor.v2f32
air.fast_fmax.f32 air.fast_fmax.v2f32 air.fast_fmax.v3f32
air.fast_fmax.v4f32 air.fast_fmin.f32 air.fast_fmin.v2f32
air.fast_fmin.v3f32 air.fast_fmin.v4f32 air.fast_fract.f32
air.fast_log2.f32 air.fast_round.v2f32 air.fast_rsqrt.f32
air.fast_saturate.f32 air.fast_saturate.v2f32
air.fast_saturate.v3f32 air.fast_saturate.v4f32 air.fast_sin.f32
air.fast_sqrt.f32 air.fast_trunc.f32 air.fast_trunc.v2f32
air.fast_trunc.v3f32 air.floor.f32 air.fmin.f16 air.fmin.f32
air.gather_texture_2d.v4f32 air.get_height_texture_2d
air.get_width_texture_2d air.is_function_constant_defined
air.min.u.i32 air.read_texture_2d.v4f32 air.sample_texture_2d.v4f32
'''.split())
NAMED_METADATA = frozenset(('air.version', 'air.language_version',
    'air.compile_options', 'air.vertex', 'air.fragment',
    'air.function_constants', 'air.source_file_name'))
DATA_LAYOUT = ('e-p:64:64:64-i1:8:8-i8:8:8-i16:16:16-i32:32:32-i64:64:64-'
    'f32:32:32-f64:64:64-v16:16:16-v24:32:32-v32:32:32-v48:64:64-'
    'v64:64:64-v96:128:128-v128:128:128-v192:256:256-v256:256:256-'
    'v512:512:512-v1024:1024:1024-n8:16:32')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def nodes(text):
    return dict(re.findall(r'^!(\d+) = (!\{.*\})$', text, re.M))


def version_node(text, name, expected):
    references = re.findall(r'^!' + re.escape(name) + r' = !\{!(\d+)\}$', text, re.M)
    if len(references) != 1 or nodes(text).get(references[0]) != expected:
        raise ValueError(f'Unexpected {name}; refusing an unrecognized AIR dialect')
    return references[0]


def reflection(text):
    """Canonicalize stage I/O and function-constant metadata, ignoring node IDs."""
    table = nodes(text)
    def expand(value, active=()):
        def reference(match):
            key = match[1]
            if key in active or key not in table:
                raise ValueError('Invalid/cyclic shader reflection metadata')
            return expand(table[key], active + (key,))
        return re.sub(r'!(\d+)\b', reference, value)
    result = {}
    for name in ('air.vertex', 'air.fragment', 'air.function_constants'):
        values = re.findall(r'^!' + re.escape(name) + r' = (.*)$', text, re.M)
        if values:
            if len(values) != 1:
                raise ValueError('Duplicate stage metadata')
            result[name] = expand(values[0])
    if not any(name in result for name in ('air.vertex', 'air.fragment')):
        raise ValueError('Only vertex/fragment stages are included in this experiment')
    return result


def adapt(text):
    if re.findall(r'^target datalayout = "([^"]+)"$', text, re.M) != [DATA_LAYOUT]:
        raise ValueError('Unexpected data layout; host LLVM output is not valid shader input')
    if re.findall(r'^target triple = "([^"]+)"$', text, re.M) != ['air64_v27-apple-ios18.0.0']:
        raise ValueError('Expected an intact air64_v27 iOS 18 module')
    unknown = set(re.findall(r'^!(air\.[\w.]+) =', text, re.M)) - NAMED_METADATA
    if unknown:
        raise ValueError(f'Unreviewed AIR metadata: {sorted(unknown)}')
    declarations = set(re.findall(r'^declare .*?@([^ (]+)\(', text, re.M))
    if declarations - INTRINSICS:
        raise ValueError(f'Unreviewed external intrinsics: {sorted(declarations - INTRINSICS)}')
    air = version_node(text, 'air.version', '!{i32 2, i32 7, i32 0}')
    language = version_node(text, 'air.language_version', '!{!"Metal", i32 3, i32 1, i32 0}')
    before = reflection(text)
    text = text.replace('target triple = "air64_v27-apple-ios18.0.0"',
                        'target triple = "air64_v25-apple-ios16.0.0"', 1)
    text = re.sub(r'^!' + air + r' = .*$', f'!{air} = !{{i32 2, i32 5, i32 0}}', text, flags=re.M)
    text = re.sub(r'^!' + language + r' = .*$', f'!{language} = !{{!"Metal", i32 3, i32 0, i32 0}}', text, flags=re.M)
    # Removing an optimization assertion weakens assumptions. Do not change
    # instructions, values, floating-point flags, bindings, or quoted strings.
    parts = re.split(r'("(?:\\.|[^"\\])*")', text)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(r'\bnoundef +', '', parts[index])
    text = ''.join(parts)
    if reflection(text) != before:
        raise ValueError('Shader reflection changed during adaptation')
    return text


def compare(newer, baseline, report):
    original, expected = newer.read_text(), baseline.read_text()
    actual = adapt(original)
    # ModuleID is a disassembler comment, unrelated to executable semantics.
    clean = lambda value: re.sub(r'^; ModuleID = .*\n', '', value, flags=re.M)
    if clean(actual) != clean(expected):
        import difflib
        report.with_suffix('.diff').write_text(''.join(difflib.unified_diff(
            expected.splitlines(True), actual.splitlines(True))))
        raise ValueError('Adapted IR differs from the direct iOS 16 source baseline')
    result = {'experimental': True, 'direct_ios16_ir_exact': True,
              'newer_ir_sha256': sha(original.encode()),
              'baseline_ir_sha256': sha(expected.encode()),
              'adapted_ir_sha256': sha(actual.encode()),
              'scope': 'This synthetic source only; no general or device compatibility guarantee'}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + '\n')
    print('Adapted synthetic IR matches direct iOS 16 source compilation exactly.')


def run(args):
    result = subprocess.run(['xcrun', '-sdk', 'iphoneos', 'metal', *map(str, args)],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout + result.stderr


def compile_libraries(source, output, proof, workers):
    evidence = json.loads(proof.read_text())
    if evidence.get('direct_ios16_ir_exact') is not True or evidence.get('experimental') is not True:
        raise ValueError('A successful synthetic baseline comparison is required')
    paths = [source] if source.is_file() else sorted(source.rglob('*.metallib'))
    if not paths:
        raise ValueError('No input Metal libraries')
    base = source.parent if source.is_file() else source
    output.mkdir(parents=True, exist_ok=True)
    def build(path):
        relative = path.relative_to(base)
        workspace = output / 'modules' / relative.with_suffix('')
        workspace.mkdir(parents=True, exist_ok=True)
        result = {'library': str(relative), 'input_sha256': sha(path.read_bytes())}
        try:
            airs, records = [], []
            for index, bitcode in enumerate(extract(path.read_bytes())):
                prefix = workspace / f'module-{index:03}'
                bc, ll = prefix.with_suffix('.bc'), prefix.with_suffix('.ll')
                bc.write_bytes(bitcode)
                run(['-x', 'ir', '-mios-version-min=18.0', '-S', '-emit-llvm', bc, '-o', ll])
                original = ll.read_text()
                adapted = prefix.with_suffix('.ios16.ll')
                adapted.write_text(adapt(original))
                air = prefix.with_suffix('.ios16.air')
                run(['-x', 'ir', '-mios-version-min=16.0', '-O2', '-c', adapted, '-o', air])
                airs.append(air)
                records.append({'bitcode_sha256': sha(bitcode),
                    'original_reflection': reflection(original),
                    'adapted_ir_sha256': sha(adapted.read_bytes())})
            destination = output / 'libraries' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            run(['-mios-version-min=16.0', *airs, '-o', destination])
            targets = validate_library(destination.read_bytes(), '16.0')
            rebuilt = extract(destination.read_bytes())
            if len(rebuilt) != len(records):
                raise ValueError('Recompiled library module count changed')
            after_reflection = []
            for index, bitcode in enumerate(rebuilt):
                bc, ll = workspace / f'checked-{index:03}.bc', workspace / f'checked-{index:03}.ll'
                bc.write_bytes(bitcode)
                run(['-x', 'ir', '-mios-version-min=16.0', '-S', '-emit-llvm', bc, '-o', ll])
                checked = ll.read_text()
                version_node(checked, 'air.version', '!{i32 2, i32 5, i32 0}')
                version_node(checked, 'air.language_version', '!{!"Metal", i32 3, i32 0, i32 0}')
                after_reflection.append(reflection(checked))
            serialize = lambda items: sorted(json.dumps(x, sort_keys=True) for x in items)
            if serialize(after_reflection) != serialize(r['original_reflection'] for r in records):
                raise ValueError('Recompiled library reflection changed')
            result.update(status='compiler_pass', modules=len(records), targets=targets,
                output_sha256=sha(destination.read_bytes()), reflection_preserved=True,
                module_evidence=records)
        except Exception as error:
            result.update(status='rejected', error=str(error))
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(build, paths))
    errors = [item for item in results if item['status'] != 'compiler_pass']
    report = {'experimental': True, 'approved_for_shipping': False,
        'device_pipeline_creation_tested': False, 'rendering_tested': False,
        'baseline_comparison': evidence, 'libraries': len(results),
        'compiler_passes': len(results) - len(errors), 'rejections': len(errors),
        'results': results}
    (output / 'compatibility-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(results) - len(errors)}/{len(results)} libraries rebuilt and reflection checked; {len(errors)} rejected.')
    print('Experimental compiler result only. iOS 16 device rendering remains untested.')
    for error in errors[:3]:
        print(error['library'], error['error'][:2000])
    if errors:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    comparison = commands.add_parser('compare')
    for name in ('newer', 'baseline', 'report'):
        comparison.add_argument(name, type=Path)
    compiler = commands.add_parser('compile')
    compiler.add_argument('source', type=Path)
    compiler.add_argument('output', type=Path)
    compiler.add_argument('--baseline-proof', required=True, type=Path)
    compiler.add_argument('--allow-experimental-air-compat', required=True, action='store_true')
    compiler.add_argument('--workers', type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    if args.command == 'compare':
        compare(args.newer, args.baseline, args.report)
    else:
        compile_libraries(args.source, args.output, args.baseline_proof, args.workers)


if __name__ == '__main__':
    main()
