#!/bin/sh
# Source-to-source translation needs fmt; DXC, compression and a GPU are not used.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
fmt_root=${MCLA_FMT_ROOT:-"$root/theft4-foundation/glue/rexglue-sdk-main/thirdparty/fmt"}
if [ ! -f "$fmt_root/include/fmt/format.h" ]; then
    echo "Initialize the pinned foundation fmt submodule first." >&2
    exit 2
fi
output="$root/tools/build-mcla-alu/mcla-xenosrecomp"
mkdir -p "$(dirname -- "$output")"
"${CXX:-clang++}" -std=c++20 -O2 -fms-extensions -DGTA4_RECOMP -DFMT_HEADER_ONLY \
    -Wno-switch -Wno-unused-variable -I"$fmt_root/include" \
    -include "$root/tools/mcla-xenosrecomp/pch.h" \
    "$root/tools/mcla-xenosrecomp/shader_recompiler.cpp" \
    "$root/tools/mcla-xenosrecomp/main.cpp" -o "$output"
echo "$output"
