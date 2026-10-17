#pragma once
#include "mcla_metal_shader_info.h"
#include <cstdint>
#include <string>
#include <vector>

namespace mcla::shader {
struct Input {
  uint64_t hash=0;
  bool vertex=false;
  std::vector<uint8_t> microcode;
  std::vector<uint32_t> elements, interpolators;
  uint32_t outputs=0;
};
struct Generated {
  MCLAMetalShaderInfo info{};
  std::string source;
};
// Pure CPU translation. Invalid or unsupported programs return an explanation.
bool Generate(const Input& input, Generated& output, std::string& error);
const char* Revision();
}
