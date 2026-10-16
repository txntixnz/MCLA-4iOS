#!/usr/bin/env python3
"""Reuse MCLA's existing floating parser fallback for Linux libc++18 host codegen.

The public iOS dependency patch already includes this implementation for
REX_PLATFORM_IOS. Do not duplicate or replace its parser.
"""
from pathlib import Path

path = Path("theft4-foundation/glue/rexglue-sdk-main/include/rex/string/numeric.h")
text = path.read_text()
old = "#if REX_PLATFORM_IOS\n  // libc++ marks floating-point from_chars as iOS 26+"
new = ("#if REX_PLATFORM_IOS || (defined(__linux__) && defined(_LIBCPP_VERSION))\n"
       "  // libc++ marks floating-point from_chars as iOS 26+")
assert text.count(old) == 1, "Expected patched ReXGlue floating parser guard not found"
path.write_text(text.replace(old, new))
print("Shared the existing iOS floating parser fallback with Linux libc++18 host codegen")
