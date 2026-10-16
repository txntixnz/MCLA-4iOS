#!/usr/bin/env python3
"""Audit private Stage 9 float16_4 warnings against independent host arithmetic.

The generated instruction bodies stay in the private output directory. This
checks emitted half conversion and register preservation, not ARM64 compilation
of the title, linking, or gameplay. No source statements are printed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def collect(package):
    audit = json.loads((package / 'PRIVATE_AOT_AUDIT.json').read_text())
    for entry in audit['manifest']:
        path = package / entry['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Stage 9 hash mismatch: ' + entry['path'])
    sites = []
    for file in sorted((package / 'generated').glob('larecomp_recomp.*.cpp')):
        lines = file.read_text().splitlines()
        address = None
        for i, line in enumerate(lines):
            function = re.match(r'DEFINE_REX_FUNC\(\w+_([0-9A-Fa-f]{8})\)', line)
            label = re.match(r'loc_([0-9A-Fa-f]{8}):', line)
            if function or label:
                address = int((function or label)[1], 16)
            instruction = re.match(r'\t// ([a-z][a-z0-9_.]*)(?: |$)', line)
            if not instruction:
                continue
            packed = re.match(r'\t// vpkd3d128 v(\d+),v(\d+),5,(\d+),(\d+)$', line)
            if packed and (int(packed[3]) != 2 or int(packed[4]) > 2):
                dst, src, mask, shift = map(int, packed.groups())
                if (mask, shift) != (3, 0) or dst == src:
                    raise ValueError('New packing case requires manual audit')
                end = i + 1
                while end < len(lines) and not lines[end].startswith('\t// '):
                    end += 1
                body = '\n'.join(lines[i + 1:end])
                if not body.strip() or 'goto' in body or 'loc_' in body:
                    raise ValueError('Unexpected generated instruction body')
                sites.append({'address': f'{address:08X}', 'file': file.name,
                              'line': i + 1, 'destination': dst, 'source': src,
                              'mask': mask, 'shift': shift, 'body': body})
            if address is not None:
                address += 4
    expected = set(audit['unhandled_float16_4_warning_sites'])
    if {site['address'] for site in sites} != expected or len(sites) != len(expected):
        raise ValueError('Warning sites differ from the Stage 9 audit')
    return sites


HARNESS = r'''
#include <array>
#include <bit>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
union V { uint8_t u8[16]; uint16_t u16[8]; uint32_t u32[4]; float f32[4]; };
union T { uint32_t u32; uint16_t u16; uint8_t u8[4]; float f32; };
struct Context { V vectors[128]; };
// Independent integer conversion: truncate mantissa, preserve signed zero,
// and use the pinned Xenon NaN/overflow result (0x7fff with the source sign).
uint16_t reference_half(uint32_t bits) {
  const uint32_t sign = (bits >> 16) & 0x8000, mag = bits & 0x7fffffff;
  if(mag > 0x477fe000) return sign | 0x7fff;
  const uint32_t exp = mag >> 23, fraction = mag & 0x7fffff;
  if(exp < 103) return sign;
  if(exp < 113) return sign | ((fraction | 0x800000) >> (126-exp));
  return sign | ((exp-112) << 10) | (fraction >> 13);
}
uint32_t random_word(uint32_t& state) {
  state ^= state << 13; state ^= state >> 17; state ^= state << 5;
  return state;
}
@FUNCTIONS@
int main() {
  using Function = void(*)(Context&);
  const Function functions[] = {@FUNCTION_LIST@};
  const unsigned destinations[] = {@DESTINATIONS@};
  const unsigned sources[] = {@SOURCES@};
  const uint32_t edge[] = {0,0x80000000,0x3f800000,0xbf800000,0x33800000,
    0x337fffff,0x38800000,0x387fffff,0x477fe000,0x477fe001,0xc77fe000,
    0x7f800000,0xff800000,0x7fc00000,0xffc00000,1,0x80000001};
  uint32_t random = 0x48414c46;
  size_t checked=0;
  for(size_t f=0; f<std::size(functions); ++f) {
    for(unsigned sample=0; sample<16384; ++sample) {
      Context ctx{};
      V input{}, expected{};
      for(unsigned lane=0;lane<4;++lane) {
        input.u32[lane] = sample < std::size(edge) ?
          edge[(sample+lane)%std::size(edge)] : random_word(random);
        expected.u32[lane] = random_word(random);
      }
      ctx.vectors[destinations[f]] = expected;
      ctx.vectors[sources[f]] = input;
      // Xenia's VPACK_64LO/shift=0 preserves the high guest words and writes
      // new packed words 2,3 into the low guest half (host words 1,0).
      expected.u32[1] = uint32_t(reference_half(input.u32[3]))<<16 |
                         reference_half(input.u32[2]);
      expected.u32[0] = uint32_t(reference_half(input.u32[1]))<<16 |
                         reference_half(input.u32[0]);
      functions[f](ctx);
      if(std::memcmp(&expected,&ctx.vectors[destinations[f]],16)) {
        std::cerr<<"Packing mismatch at function "<<f<<" sample "<<sample<<'\n';
        return 1;
      }
      ++checked;
    }
  }
  std::cout<<checked<<" generated instruction executions matched\n";
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('package', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--cxx', default='c++')
    a = ap.parse_args()
    sites = collect(a.package)
    a.output.mkdir(parents=True, exist_ok=True)
    functions = []
    for i, site in enumerate(sites):
        body = re.sub(r'ctx\.v(\d+)', r'ctx.vectors[\1]', site['body'])
        functions.append(f'void instruction_{i}(Context& ctx) {{ T temp{{}}; V vTemp{{}};\n{body}\n}}')
    text = HARNESS.replace('@FUNCTIONS@', '\n'.join(functions))
    text = text.replace('@FUNCTION_LIST@', ','.join(f'instruction_{i}' for i in range(len(sites))))
    text = text.replace('@DESTINATIONS@', ','.join(str(s['destination']) for s in sites))
    text = text.replace('@SOURCES@', ','.join(str(s['source']) for s in sites))
    source = a.output / 'private_pack_instruction_check.cpp'
    exe = a.output / 'private_pack_instruction_check'
    source.write_text(text)
    subprocess.run([a.cxx, '-std=c++20', '-O2', '-fsanitize=undefined',
                    '-fno-sanitize-recover=all', str(source), '-o', str(exe)], check=True)
    result = subprocess.check_output([str(exe)], text=True).strip()
    public = [{k: v for k, v in s.items() if k != 'body'} for s in sites]
    report = {'stage9_hashes_verified': True, 'warning_count': len(sites),
              'warnings_are_missing_instructions': False,
              'observed_case': 'float16_4, mask=3, shift=0, nonaliased source/destination',
              'host_execution_check': result, 'undefined_behavior_sanitizer': 'PASS',
              'whole_title_arm64_compile': 'NOT RUN', 'sites': public}
    (a.output / 'aot_pack_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'sites'}, indent=2))


if __name__ == '__main__':
    main()
