#!/usr/bin/env python3
"""Portable journal tests; parse every retained record with an independent JSON decoder."""
import json, os, pathlib, shlex, subprocess, tempfile
root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mcla-fault-journal-') as directory:
    tmp = pathlib.Path(directory)
    binary = tmp/'journal'
    subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
        '-std=c++20', '-O1', '-pthread', '-fsanitize=undefined',
        '-fno-sanitize-recover=all', str(root/'tools/test_mcla_gpu_fault_journal.cpp'),
        '-o', str(binary)], check=True)
    subprocess.run([str(binary), str(tmp)], check=True)
    records = [json.loads(line) for line in (tmp/'concurrent/gpu-faults.jsonl').read_text().splitlines()]
    assert len(records) == 123
    workers = [r for r in records if r['event'] == 'worker']
    assert len({(r['data']['thread'],r['data']['n']) for r in workers}) == 120
    assert [r['session'] for r in records if r['event'] == 'session'] == ['first','second']
    assert records[-1]['event'] == 'recovery_complete' and records[-1]['pid'] == 124
    for path in (tmp/'rotation').glob('*.jsonl'):
        assert path.stat().st_size <= 4096
        for line in path.read_text().splitlines():
            record = json.loads(line)
            assert record['session'] == 'rotation' and record['utc_ms'] > 0
    print('PASS: independent JSON parsing, exact concurrent event count and per-record session identity')
