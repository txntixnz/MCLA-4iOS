#!/usr/bin/env python3
"""Compile native evidence capture, then verify actual bytes when Metal exists."""
import json,pathlib,struct,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mcla-visual-') as d:
    d=pathlib.Path(d);binary=d/'capture';output=d/'VisualFrame'
    subprocess.run(['xcrun','clang++','-std=c++20','-fobjc-arc','-fblocks',
        str(root/'tools/test_mcla_visual_frame_capture.mm'),'-framework','Foundation',
        '-framework','Metal','-o',str(binary)],check=True)
    result=subprocess.run([str(binary),str(output)])
    if result.returncode==77:
        print('SKIP: native compilation passed; this host has no Metal GPU')
        raise SystemExit(0)
    result.check_returncode()
    m=json.loads((output/'manifest.json').read_text());data=(output/'draws.bin').read_bytes()
    assert m['gpu_completed'] and m['frame']==7 and m['draw_count']==2
    assert len(data)==2*m['draw_record_bytes']==1872
    assert struct.unpack_from('<QQQ',data)==(42,0x123456789ABCDEF0,0xFEDCBA9876543210)
    assert struct.unpack_from('<I',data,32)[0]==0x12340000
    assert struct.unpack_from('<6I',data,48)==(0x123,0x18280186,0x40,0,640,360)
    assert m['constant_banks']==1 and len((output/'constants.bin').read_bytes())==4096
    assert not m['truncated'] and len(m['images'])==2
    for im in m['images']:
        b=(output/im['file']).read_bytes();assert len(b)==im['bytes']
        at=180*im['row_bytes']+320*4;assert b[at:at+4]==bytes([255,32,48,255])
        assert b[:4]==bytes([16,32,48,255])
    limits=json.loads((pathlib.Path(str(output)+'-limits')/'manifest.json').read_text())
    assert limits['truncated'] and limits['draw_count']==8192 and limits['dropped_draws']==1
    assert limits['constant_banks']<=256 and len(limits['images'])==8
    assert limits['images'][-1]['phase']=='present-source'
print('PASS: decoded manifest, state/texture layout, bank references and actual bright-patch pixels')
