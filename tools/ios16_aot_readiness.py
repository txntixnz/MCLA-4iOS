#!/usr/bin/env python3
"""Check private MCLA AOT and shader inputs without copying or uploading game data."""
import argparse
import json
from pathlib import Path
import re

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--aot',type=Path,help='private AOT directory, defaults to ROOT/MCLAApp/generated')
    ap.add_argument('--json',dest='output',type=Path)
    a=ap.parse_args()
    root=a.root.resolve()
    generated=(a.aot or root/'MCLAApp/generated').resolve()
    checks=[]
    def check(label,ok,detail):
        checks.append({'name':label,'status':'PASS' if ok else 'BLOCKED','detail':str(detail)})
    config=root/'MCLAApp/CMakePresets.json'
    try:
        j=json.loads(config.read_text())
        preset=next(x for x in j['configurePresets'] if x['name']=='ios16-device-release')
        cache=preset['cacheVariables']
        valid=(cache.get('CMAKE_OSX_DEPLOYMENT_TARGET')=='16.0' and
               cache.get('CMAKE_OSX_ARCHITECTURES')=='arm64' and
               cache.get('MCLA_RUNTIME_ENABLED')=='ON')
    except (OSError, ValueError, KeyError, StopIteration):
        valid=False
    check('iOS16 ARM64 full-runtime preset',valid,'iOS16/arm64 runtime target')
    sources=generated/'sources.cmake'
    cpp={p.name for p in generated.glob('*.cpp')}
    units={int(m.group(1)) for p in cpp
           if (m:=re.fullmatch(r'larecomp_recomp\.(\d+)\.cpp',p))}
    listed=set(re.findall(r'\$\{CMAKE_CURRENT_LIST_DIR\}/([^\s\)]+\.cpp)',
                          sources.read_text() if sources.is_file() else ''))
    ok=(sources.is_file() and (generated/'larecomp_init.h').is_file()
        and {'larecomp_init.cpp','larecomp_register.cpp'} <= cpp
        and units==set(range(60)) and listed==cpp)
    check('Private PowerPC-to-C++ AOT',ok,f'{len(units)}/60 translations; {len(listed)} listed files')
    for p,label in [
        ('artifacts/mcla-native-metadata/mcla_vertex_elements.map','MCLA vertex-layout map'),
        ('artifacts/mcla-native-metadata/mcla_native_shaders.mspv','MCLA native SPIR-V pack'),
        ('MCLAApp/generated/mcla_metal_shader_info.h','Generated shader ABI metadata'),
        ('artifacts/mcla-metal-upscale/MCLAFsr.metallib','FSR offline Metal library'),
    ]:
        check(label,(root/p).is_file(),p)
    libs=list((root/'artifacts/mcla-metal-shaders').glob('*.metallib'))
    check('Title Metal shader libraries',len(libs)>=603,f'{len(libs)}/603 present; AIR target must also be audited')
    inputs=list((root/'artifacts/mcla-alu-order-compiled/hlsl').glob('*.hlsl'))
    check('Captured HLSL inputs',len(inputs)>=534,f'{len(inputs)} files; historical minimum 534')
    for item in checks:
        print(f"{item['status']:7} {item['name']}: {item['detail']}")
    if a.output:
        a.output.write_text(json.dumps({'checks':checks},indent=2))
    return 0 if all(x['status']=='PASS' for x in checks) else 2

if __name__=='__main__':
    raise SystemExit(main())
