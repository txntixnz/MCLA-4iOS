#include "mcla_runtime_shader_fixture.h"
#include <iostream>
int main(int argc,char** argv) {
  try {
    if(argc!=3)return 2;auto input=ReadRuntimeShaderFixture(argv[1]);
    mcla::shader::Generated out;std::string error;
    if(!mcla::shader::Generate(input,out,error))throw std::runtime_error(error);
    std::ofstream file(argv[2],std::ios::binary);file<<out.source;file.close();
    auto invalid=input;invalid.hash^=1;
    if(mcla::shader::Generate(invalid,out,error))throw std::runtime_error("identity rejection missing");
    invalid=input;invalid.microcode.pop_back();
    if(mcla::shader::Generate(invalid,out,error))throw std::runtime_error("truncation rejection missing");
    invalid=input;invalid.interpolators.assign(32,0);
    if(mcla::shader::Generate(invalid,out,error))throw std::runtime_error("descriptor rejection missing");
    std::cout<<"PASS: generated source; identity/truncation/descriptor rejections.\n";
    return 0;
  }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
