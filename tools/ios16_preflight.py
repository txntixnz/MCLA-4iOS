#!/usr/bin/env python3
"""Inspect the experimental iOS 16 build without guessing that an IPA is playable."""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess
import sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--app', type=Path, help='Built MCLAApp.app to verify, if one exists')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks = []
    preset = json.loads((root/'MCLAApp/CMakePresets.json').read_text())
    build = next((p for p in preset['configurePresets'] if p['name'] == 'ios16-device-release'), None)
    checks.append(('iOS 16 ARM64 preset', bool(build and build['cacheVariables'].get('CMAKE_OSX_DEPLOYMENT_TARGET') == '16.0')))
    shader_sources = list((root/'artifacts/mcla-alu-order-compiled/hlsl').glob('*.hlsl'))
    checks.append((f'Private original-game-derived HLSL sources ({len(shader_sources)} found; 534+ required)', len(shader_sources) >= 534))
    checks.append(('Private generated AOT sources', (root/'MCLAApp/generated/sources.cmake').is_file()))
    libs = list((root/'artifacts/mcla-metal-shaders').glob('*.metallib'))
    checks.append((f'Native title shaders ({len(libs)} found; 603 expected)', len(libs) >= 603))
    checks.append(('Native FSR library', (root/'artifacts/mcla-metal-upscale/MCLAFsr.metallib').is_file()))
    if args.app:
        app = args.app.resolve()
        try:
            info = plistlib.loads((app/'Info.plist').read_bytes())
            checks.append(('Actual app MinimumOSVersion 16.0', info.get('MinimumOSVersion') == '16.0'))
            proc = subprocess.run([sys.executable, str(root/'tools/verify_mcla_metal_targets.py'), str(app)], capture_output=True, text=True)
            print(proc.stdout + proc.stderr)
            checks.append(('Packaged Metal library AIR target audit', proc.returncode == 0))
        except (OSError, KeyError, ValueError) as e:
            print('Could not verify built app:', e)
            checks.append(('Built app audit', False))
    for name, valid in checks:
        print(f'{"PASS" if valid else "BLOCKED"}: {name}')
    return 0 if all(ok for _,ok in checks) else 2

if __name__ == '__main__':
    raise SystemExit(main())
