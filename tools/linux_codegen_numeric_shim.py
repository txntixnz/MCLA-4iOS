#!/usr/bin/env python3
"""Host-only Linux libc++18 code generator compatibility workaround.

The original game runtime sources remain untouched in the repository.
"""
from pathlib import Path

path = Path("theft4-foundation/glue/rexglue-sdk-main/include/rex/string/numeric.h")
s = path.read_text()
header = "#include <charconv>"
assert s.count(header) == 1, "Unexpected pinned SDK header"
s = s.replace(header, header + "\n#include <cerrno>\n#include <cstdlib>\n#include <type_traits>")
old = """    auto [p, error] = std::from_chars(range.data(), range.data() + range.size(), result,
                                      std::chars_format::general);
    // TODO(gibbed): do something more with errors?
    if (error != std::errc()) {
      assert_always();
      return T();
    }"""
new = """#if defined(__linux__) && defined(_LIBCPP_VERSION)
    // Linux codegen only: libc++18 lacks floating-point from_chars.
    // Prefer fixed C numeric locale in CI; reject partial strings and overflow.
    std::string input(range);
    char* end = nullptr;
    errno = 0;
    if constexpr (std::is_same_v<T, float>) {
      result = std::strtof(input.c_str(), &end);
    } else {
      result = std::strtod(input.c_str(), &end);
    }
    if (errno == ERANGE || end == input.c_str() || end != input.c_str() + input.size()) {
      assert_always();
      return T();
    }
#else
    auto [p, error] = std::from_chars(range.data(), range.data() + range.size(), result,
                                      std::chars_format::general);
    if (error != std::errc()) {
      assert_always();
      return T();
    }
#endif"""
assert s.count(old) == 1, "Unexpected pinned SDK floating-point parser source"
path.write_text(s.replace(old, new))
print("Applied pinned host-only libc++18 float parsing fallback")
