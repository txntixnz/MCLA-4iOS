#pragma once
#include <cstdint>
#include <string>
struct MCLAXexExtent { uint64_t offset = 0, size = 0; };
bool MCLAFindXbox360Xex(const char* isoPath, MCLAXexExtent* result, std::string* error);
