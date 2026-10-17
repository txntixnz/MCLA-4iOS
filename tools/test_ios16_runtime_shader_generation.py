#!/usr/bin/env python3
"""Replay private captured programs through the actual in-app CPU translator."""
import base64
import json
from pathlib import Path
import struct
import subprocess
import sys

inputs, expected, executable, output = map(Path, sys.argv[1:])
data=json.loads(inputs.read_text());output.mkdir(parents=True,exist_ok=True)
def read(name): return base64.b64decode(data['files'][name]['base64'],validate=True)
records=[json.loads(line) for line in read('manifest.jsonl').decode().splitlines()]
for name in data['missing']:
    vertex=name.startswith('vs-');identity=name[3:];key='vs' if vertex else 'ps'
    r=next(r for r in records if r[key]==identity)
    microcode=read('shaders/'+name+'.bin')
    def metadata(prefix,count):
        raw=read(f'metadata/{prefix}-{identity}.bin') if count else b''
        assert len(raw)==count*4
        return raw
    elements=metadata('vs-elements',r['vs_elements']) if vertex else b''
    interpolators=metadata(key+'-interpolators',r[key+'_interpolators'])
    fixture=struct.pack('<Q5I',int(identity,16),vertex,len(microcode),len(elements)//4,len(interpolators)//4,0 if vertex else r['ps_outputs'])+microcode+elements+interpolators
    (output/(name+'.fixture')).write_bytes(fixture)
    generated=output/(name+'.metal')
    subprocess.run([str(executable.resolve()),str(output/(name+'.fixture')),str(generated)],check=True)
    original=(expected/(name+'.metal')).read_bytes()
    if generated.read_bytes()!=original:
        import difflib
        print(''.join(difflib.unified_diff(original.decode().splitlines(True),generated.read_text().splitlines(True),n=2))[:4000])
        raise ValueError('Runtime source differs from audited offline source: '+name)
print(f'PASS: {len(data["missing"])} runtime MSL sources exactly match the audited offline compiler.')
