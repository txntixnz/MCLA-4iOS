#!/bin/bash
# Public synthetic source only. Establish a local compiler comparison baseline.
set -euo pipefail
output="${1:?Usage: probe_ios16_air.sh output-directory}"
script_dir="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$output"
cp "$script_dir/fixtures/ios16_air_probe.metal" "$output/synthetic.metal"
for config in ios18 ios16; do
  if [[ "$config" == ios18 ]]; then
    minimum=18.0; standard=metal3.1
  else
    minimum=16.0; standard=metal3.0
  fi
  xcrun -sdk iphoneos metal -std="$standard" -mios-version-min="$minimum" \
    -c "$output/synthetic.metal" -o "$output/$config.air"
  xcrun -sdk iphoneos metal -std="$standard" -mios-version-min="$minimum" \
    -S -emit-llvm "$output/synthetic.metal" -o "$output/$config.ll"
  xcrun -sdk iphoneos metal -mios-version-min="$minimum" \
    "$output/$config.air" -o "$output/$config.metallib"
done
python3 "$script_dir/ios16_air_compat.py" compare \
  "$output/ios18.ll" "$output/ios16.ll" "$output/baseline-proof.json"
