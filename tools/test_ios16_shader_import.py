#!/usr/bin/env python3
"""Synthetic endian/normalization checks; optional parity against the pinned C++ runtime."""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from ios16_import_xenia_shaders import guest_bytes, identity, normalize, vertex_fetches


class ImportChecks(unittest.TestCase):
    def test_xenia_word_order_and_runtime_patch_invariance(self):
        # Two CF instructions, one executed fetch at instruction address 1.
        guest = struct.pack('>IIIIII', 1 | (1 << 12) | (1 << 16), 0x1000, 0,
                            (1 << 19) | (3 << 20), 0x12340123, 0x45608)
        raw = b''.join(guest[i:i+4][::-1] for i in range(0, len(guest), 4))
        self.assertEqual(guest_bytes(raw), guest)
        self.assertEqual(vertex_fetches(guest)[0]['address'], 1)
        patched = guest[:12] + struct.pack('>III', (1 << 19) | (5 << 20), 0xfff, 0x9876)
        self.assertNotEqual(guest, patched)
        self.assertEqual(identity(guest), identity(patched))
        self.assertEqual(normalize(guest)[12:], bytes(12))

    def test_texture_fetch_is_not_normalized(self):
        guest = struct.pack('>IIIIII', 1 | (1 << 12) | (1 << 16), 0x1000, 0, 1, 2, 3)
        self.assertEqual(normalize(guest), guest)
        self.assertEqual(vertex_fetches(guest), [])

    def test_malformed_input(self):
        for raw in (b'', bytes(13), bytes(65544)):
            with self.assertRaises(ValueError):
                guest_bytes(raw)


def parity(corpus):
    root = Path(__file__).resolve().parents[1]
    runtime = root / 'larecomp/src/native_gfx'
    files = sorted((corpus / 'shaders').glob('*.bin'))
    if not files:
        raise ValueError('No imported shaders to compare')
    with tempfile.TemporaryDirectory(prefix='mcla-identity-') as temporary:
        tmp = Path(temporary)
        code = tmp / 'probe.cpp'
        code.write_text('''#include "shader_identity.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
#include <iomanip>
int main(int argc, char** argv) {
  for(int i=1;i<argc;++i) {
    std::ifstream in(argv[i],std::ios::binary);
    std::vector<uint8_t> data{std::istreambuf_iterator<char>(in),{}};
    if(data.empty()) return 2;
    mcla::native_gfx::NormalizeVertexFetches(data.data(),data.size());
    std::cout << std::hex << std::uppercase << std::setfill('0') << std::setw(16)
      << mcla::native_gfx::Fnv1a64(data.data(),data.size()) << '\\n';
  }
}
''')
        exe = tmp / 'probe'
        subprocess.run(['c++', '-std=c++20', '-O2', '-I' + str(runtime), str(code),
                        str(runtime / 'shader_identity.cpp'), '-o', str(exe)], check=True)
        hashes = subprocess.check_output([str(exe), *map(str, files)], text=True).splitlines()
        expected = [identity(file.read_bytes()) for file in files]
        if hashes != expected:
            raise AssertionError('Python/C++ shader identity mismatch')
        print(f'PASS: {len(files)} shader identities match the pinned C++ runtime')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', type=Path)
    a = ap.parse_args()
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ImportChecks))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if a.corpus:
        parity(a.corpus)
