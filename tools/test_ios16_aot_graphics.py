#!/usr/bin/env python3
"""Synthetic linker regression for named and address-based native overrides."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from ios16_bind_aot_graphics import HOOKS, bindings, header


def write_tables(root, naming):
    symbols = [(a, h if naming == 'named' else f'rex_sub_{a:08X}') for a, h in HOOKS]
    (root / 'larecomp_init.h').write_text('\n'.join(f'DECLARE_REX_FUNC({s});' for _, s in symbols))
    (root / 'larecomp_init.cpp').write_text('\n'.join(f'{{ 0x{a:08X}, {s} }},' for a, s in symbols))
    (root / 'larecomp_register.cpp').write_text('\n'.join(f'registrar->SetFunction(0x{a:08X}, {s});' for a, s in symbols))
    return symbols


class GraphicsBindingsTest(unittest.TestCase):
    def test_real_linker_overrides_direct_and_table_calls(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'A host C compiler is required')
        for naming in ('address', 'named'):
            with self.subTest(naming=naming), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                symbols = write_tables(root, naming)
                report = bindings(root)
                self.assertEqual(report['naming'], naming)
                self.assertEqual(report['hook_count'], 13)
                (root / 'MCLAAOTGraphicsBindings.h').write_text(header(report))
                guest = ['int hooks[13], originals[13];']
                hooks = ['#include "MCLAAOTGraphicsBindings.h"',
                         'extern int hooks[13];']
                main = ['extern int hooks[13], originals[13];', 'void table_call(void);']
                for i, ((_, hook), (_, symbol)) in enumerate(zip(HOOKS, symbols)):
                    guest += [f'void rex_generated_{symbol}(void) {{ ++originals[{i}]; }}',
                              f'__attribute__((weak,noinline)) void {symbol}(void) {{ rex_generated_{symbol}(); }}']
                    hooks += [f'void rex_generated_{hook}(void);',
                              f'void {hook}(void) {{ ++hooks[{i}]; rex_generated_{hook}(); }}']
                    main += [f'void {symbol}(void);']
                guest += ['void (*mapping[13])(void) = {' + ','.join(s for _, s in symbols) + '};',
                          'void table_call(void) { for(int i=0;i<13;++i) mapping[i](); }']
                main += ['int main(void) { table_call();']
                main += [f'{s}();' for _, s in symbols]
                main += ['for(int i=0;i<13;++i) if(hooks[i]!=2 || originals[i]!=2) return 1;', 'return 0; }']
                for name, source in [('guest', guest), ('hooks', hooks), ('main', main)]:
                    (root / f'{name}.c').write_text('\n'.join(source))
                subprocess.run([compiler, '-O2', 'guest.c', 'hooks.c', 'main.c', '-o', 'probe'],
                               cwd=root, check=True, capture_output=True, text=True)
                subprocess.run([str(root / 'probe')], check=True)

    def test_mismatch_is_rejected(self):
        for mutation in ('missing', 'wrong_registration', 'wrong_declaration', 'mixed', 'duplicate'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_tables(root, 'address')
                path = root / 'larecomp_init.cpp'
                if mutation == 'wrong_registration':
                    path = root / 'larecomp_register.cpp'
                if mutation == 'wrong_declaration':
                    path = root / 'larecomp_init.h'
                text = path.read_text()
                if mutation == 'missing':
                    text = text.replace('0x82419E98', '0x82419E94')
                elif mutation == 'duplicate':
                    text += '\n{ 0x82419E98, rex_sub_82419E98 },'
                elif mutation == 'mixed':
                    for item in root.iterdir():
                        item.write_text(item.read_text().replace('rex_sub_82419E98', 'D3DDevice_Swap'))
                    text = path.read_text()
                else:
                    text = text.replace('rex_sub_82419E98', 'wrong_swap')
                path.write_text(text)
                with self.assertRaises(ValueError):
                    bindings(root)


if __name__ == '__main__':
    unittest.main()
