#!/usr/bin/env python3
"""Embed the exact offline compiler's shared source and gamma helpers."""
import ast
import hashlib
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
tree = ast.parse((root/'tools/build_mcla_metal_shaders.py').read_text())
gamma = next(ast.literal_eval(n.value) for n in tree.body
             if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'GAMMA_HELPERS' for t in n.targets))
common = (root/'tools/mcla-xenosrecomp/shader_common.h').read_text()
files = ['tools/build_mcla_metal_shaders.py', 'tools/mcla_shader_container_builder.h',
         'tools/mcla_shader_constant_abi.h', 'tools/mcla_vertex_id_abi.h',
         'MCLAApp/runtime/MCLARuntimeShaderSource.cpp', 'tools/generate_mcla_runtime_shader_assets.py']
files += [p.relative_to(root).as_posix() for p in sorted((root/'tools/mcla-xenosrecomp').glob('*.h'))]
files += ['tools/mcla-xenosrecomp/shader_recompiler.cpp']
revision = hashlib.sha256(b''.join((root/f).read_bytes() for f in files)).hexdigest()[:24]
dest = Path(sys.argv[1]); dest.parent.mkdir(parents=True, exist_ok=True)
for text in (common, gamma):
    assert ')MCLA_ASSET"' not in text
dest.write_text('#pragma once\nnamespace mcla::shader {\n'
                f'inline constexpr char kRevision[]="{revision}";\n'
                f'inline constexpr char kCommon[]=R"MCLA_ASSET({common})MCLA_ASSET";\n'
                f'inline constexpr char kGamma[]=R"MCLA_ASSET({gamma})MCLA_ASSET";\n}}\n')
print(f'Runtime shader assets: {revision}')
