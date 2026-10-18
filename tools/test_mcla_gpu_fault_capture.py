#!/usr/bin/env python3
"""Native synthetic error -> journal -> reopen -> shipping ZIP export regression."""
import json, pathlib, subprocess, tempfile, zipfile
root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mcla-fault-capture-') as directory:
    tmp = pathlib.Path(directory)
    binary = tmp/'capture'
    subprocess.run(['xcrun','clang++','-std=c++20','-fobjc-arc','-fblocks',
        str(root/'MCLAApp/tests/MCLAGPUFaultCaptureTests.mm'),
        str(root/'MCLAApp/ios/MCLALogArchive.mm'),'-framework','Foundation',
        '-framework','Metal','-lz','-o',str(binary)],check=True)
    subprocess.run([str(binary),str(tmp/'home'),str(tmp/'logs.zip')],check=True)
    with zipfile.ZipFile(tmp/'logs.zip') as archive:
        assert archive.testzip() is None
        paths = [n for n in archive.namelist() if n.endswith('.jsonl')]
        assert len(paths) == 2
        records=[]
        for name in sorted(paths, key=lambda n: 0 if '.previous.' in n else 1):
            contents = archive.read(name)
            assert len(contents) <= 128*1024
            records.extend(json.loads(line) for line in contents.decode().splitlines())
        faults=[r for r in records if r['event']=='gpu_error']
        assert len(faults)==1
        fault=faults[0]
        assert fault['build']=='26' and fault['detailed_logging'] is False
        assert fault['data']['frame']==692 and fault['data']['active'] is True
        assert fault['data']['automatic_shaders']==['vs-0123456789ABCDEF']
        assert len(fault['data']['encoders'])==12 and fault['data']['encoders_omitted']==7
        assert fault['data']['encoders'][0]['label']=='fault "label" 測試'
        assert {r['event'] for r in records}>={'gpu_error','recovery_begin','recovery_complete','session'}
        assert records[-1]['event']=='session' and records[-1]['session']!=fault['session']
    print('PASS: JSON escaping/Unicode, encoder priority/caps, two-file bounds, separate sessions and exported error/recovery records')
