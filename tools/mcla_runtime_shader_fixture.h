#pragma once
#include "../MCLAApp/runtime/MCLARuntimeShaderSource.h"
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
inline mcla::shader::Input ReadRuntimeShaderFixture(const char* path) {
  std::ifstream f(path,std::ios::binary);std::vector<uint8_t> b{std::istreambuf_iterator<char>(f),{}};
  if(b.size()<28)throw std::runtime_error("fixture header");
  mcla::shader::Input in;std::memcpy(&in.hash,b.data(),8);
  uint32_t words[5];std::memcpy(words,b.data()+8,20);
  if(words[0]>1 || words[1]>65532 || words[2]>31 || words[3]>31 || b.size()!=28+words[1]+4*(words[2]+words[3]))throw std::runtime_error("fixture bounds");
  in.vertex=words[0];in.outputs=words[4];in.microcode.assign(b.begin()+28,b.begin()+28+words[1]);
  in.elements.resize(words[2]);in.interpolators.resize(words[3]);
  std::memcpy(in.elements.data(),b.data()+28+words[1],words[2]*4);
  std::memcpy(in.interpolators.data(),b.data()+28+words[1]+words[2]*4,words[3]*4);
  return in;
}
