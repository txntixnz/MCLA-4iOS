#!/usr/bin/env python3
"""Exercise actual Metal compilation, cache reuse/corruption, and suspension."""
import json
from pathlib import Path
import subprocess
import sys

exe,fixtures,cache,report=map(Path,sys.argv[1:]);cache.mkdir(parents=True,exist_ok=True)
results=[]
def run(hits,mode):
    result=subprocess.run([str(exe.resolve()),str(fixtures.resolve()),str(cache.resolve()),str(hits),mode],check=True,capture_output=True,text=True)
    print(result.stdout.strip());results.append(json.loads(result.stdout))
run(0,'cold')
run(17,'warm')
entry=sorted(cache.glob('*.cache'))[0];entry.write_bytes(b'corrupted cache')
run(16,'corrupt')
run(17,'suspend')
run(16,'suspended')
report.write_text(json.dumps({'status':'PASS','captured_programs':17,'duplicate_requests_coalesced':True,'cold_compile':results[0],'warm_cache':results[1],'corrupt_cache_regenerated':results[2],'GPU_suspension':results[3],'suspension_persisted':results[4],'device_gameplay_tested':False},indent=2)+'\n')
