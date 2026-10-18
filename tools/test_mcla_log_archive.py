#!/usr/bin/env python3
"""Exercise the actual streaming ZIP exporter with synthetic app storage."""
import json, pathlib, subprocess, tempfile, zipfile
root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mcla-log-test-') as tmp:
    tmp = pathlib.Path(tmp)
    binary = tmp/'export'
    subprocess.run(['xcrun', 'clang++', '-std=c++17', '-fobjc-arc',
        str(root/'MCLAApp/tests/MCLALogArchiveTests.mm'),
        str(root/'MCLAApp/ios/MCLALogArchive.mm'), '-framework', 'Foundation', '-lz', '-o', str(binary)], check=True)
    home = tmp/'home'
    support = home/'Library/Application Support/MCLA'
    diagnostics = home/'Documents/Diagnostics'
    support.mkdir(parents=True)
    diagnostics.mkdir(parents=True)
    expected = {'Library/Application Support/MCLA/runtime.log': b'failure details\n',
        'Library/Application Support/MCLA/logs/gpu-faults.jsonl': b'{"event":"session","build":"26"}\n',
        'Library/Application Support/MCLA/logs/gpu-faults.previous.jsonl': b'{"event":"gpu_error","build":"25"}\n',
        'Library/Application Support/MCLA/runtime.log.1': b'previous log\n',
        'Library/Application Support/MCLA/native-frame-capture/nested/frame.json': b'{}',
        'Library/Application Support/MCLA/runtime-status.txt': b'Xbox/AOT runtime setup failed.\n',
        'Documents/Diagnostics/nested/測試.csv': b'frame,ms\n' * 20000,
        'Documents/Diagnostics/empty.txt': b'',
        'Documents/Diagnostics/VisualFrame/manifest.json': b'{"gpu_completed":true}',
        'Documents/Diagnostics/VisualFrame/draws.bin': b'draw trace',
        'Documents/Diagnostics/VisualFrame/constants.bin': b'constant bank',
        'Documents/Diagnostics/VisualFrame/image-00.bin': b'pixel readback',
        'Library/Application Support/MCLA/native-capture/manifest.jsonl': b'{"test":true}\n',
        'Library/Application Support/MCLA/native-capture/shaders/vs-0123456789ABCDEF.bin': bytes(range(256)),
        'Library/Application Support/MCLA/native-capture/metadata/vs-elements-0123456789ABCDEF.bin': b'\x01\x00\x00\x00',
        'Library/Application Support/MCLA/native-capture/fetch/fetch-0123456789ABCDEF.bin': b'fetch data',
        'Library/Application Support/MCLA/native-capture/declarations/decl-0123456789ABCDEF.bin': b'declaration',
        'Documents/mcla-render-probe.json': b'{}'}
    for name, data in expected.items():
        path = home/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for name in ['Library/Application Support/MCLA/saves/private.txt',
        'Library/Application Support/MCLA/cache/private.log',
        'Documents/MCLA_Game_Files/default.xex',
        'Documents/Diagnostics/raw.rpf',
        'Documents/Diagnostics/VisualFrame/raw.bin',
        'Documents/Diagnostics/VisualFrame/unrelated.json',
        'Documents/Diagnostics/VisualFrame/nested/manifest.json',
        'Documents/Diagnostics/VisualFrame/image-08.bin']:
        path = home/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'EXCLUDE')
    for name, data in [
        ('shaders/vs-FEDCBA9876543210.bin', bytes(65537)),
        ('shaders/not-a-shader.bin', b'EXCLUDE'),
        ('shaders/nested/vs-0123456789ABCDEF.bin', b'EXCLUDE'),
        ('geometry/vs-0123456789ABCDEF.bin', b'EXCLUDE'),
        ('shaders/vs-0123456789ABCDEF.bin.tmp', b'EXCLUDE')]:
        path=support/'native-capture'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (diagnostics/'VisualFrame/image-07.bin').write_bytes(bytes(16*1024*1024+1))
    outside = tmp/'outside.txt'
    outside.write_text('EXCLUDE')
    (diagnostics/'symlink.txt').symlink_to(outside)
    archive = tmp/'logs.zip'
    subprocess.run([str(binary), str(home), str(archive)], check=True)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == set(expected) | {'report.txt','shader-gap-export.json'}, z.namelist()
        capture=json.loads(z.read('shader-gap-export.json'))
        assert capture['included_files']==4 and capture['skipped_by_limit']==1
        for name, data in expected.items():
            assert z.read(name) == data
    empty_home = tmp/'empty'
    empty_home.mkdir()
    subprocess.run([str(binary), str(empty_home), str(archive)], check=True)
    with zipfile.ZipFile(archive) as z:
        assert z.namelist() == ['report.txt'] and z.testzip() is None
    assert subprocess.run([str(binary), str(home), str(tmp/'missing/output.zip')]).returncode != 0
print('PASS: ZIP integrity, multi-chunk and Unicode files, empty diagnostics, game/save exclusion, symlink exclusion, output errors')
