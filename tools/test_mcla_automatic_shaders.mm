#include "mcla_runtime_shader_fixture.h"
#include "../MCLAApp/runtime/MCLAAutomaticShaders.h"
#import <Foundation/Foundation.h>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <thread>

int main(int argc,char** argv) {
  @autoreleasepool {
    try {
      if(argc!=5)return 2;
      const std::filesystem::path fixtures=argv[1];
      const unsigned expectedHits=unsigned(std::stoul(argv[3]));
      const bool expectSuspended=std::string(argv[4])=="suspended";
      setenv("MCLA_AUTOMATIC_SHADER_TEST_CACHE",argv[2],1);
      std::vector<mcla::shader::Input> inputs;
      for(const auto& p:std::filesystem::directory_iterator(fixtures))if(p.path().extension()==".fixture")inputs.push_back(ReadRuntimeShaderFixture(p.path().c_str()));
      if(inputs.size()!=17)throw std::runtime_error("Expected 17 withheld captured shaders");
      for(const auto& input:inputs) {
        mcla::shader::Request(input);mcla::shader::Request(input); // coalesce duplicate requests
      }
      auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(90);
      while(mcla::shader::GetStatistics().pending && std::chrono::steady_clock::now()<deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
      const auto stats=mcla::shader::GetStatistics();
      if(stats.pending || stats.ready!=(expectSuspended?16u:17u) || stats.rejected!=(expectSuspended?1u:0u) || stats.cacheHits!=expectedHits)throw std::runtime_error("Automatic shader stats mismatch: ready="+std::to_string(stats.ready)+" rejected="+std::to_string(stats.rejected)+" hits="+std::to_string(stats.cacheHits));
      unsigned ready=0;
      for(const auto& input:inputs)if(const auto* info=mcla::shader::ReadyInfo(input.hash,input.vertex)) {
        if(info->hash!=input.hash || info->vertex!=input.vertex || !mcla::shader::ReadyLibrary(input.hash,input.vertex))throw std::runtime_error("Invalid published shader");
        ++ready;
      }
      if(ready!=stats.ready)throw std::runtime_error("Ready shader lookup mismatch");
      if(std::string(argv[4])=="suspend") {
        const auto& input=inputs.front();mcla::shader::SuspendAfterGPUError(input.hash,input.vertex);
        if(mcla::shader::ReadyInfo(input.hash,input.vertex))throw std::runtime_error("Suspended shader still exposed");
        bool persisted=false;
        for(unsigned i=0;i<500 && !persisted;++i) {
          for(const auto& p:std::filesystem::directory_iterator(argv[2]))if(p.path().extension()==".suspended")persisted=true;
          std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        if(!persisted)throw std::runtime_error("Suspension not persisted");
      }
      std::cout<<"{\"status\":\"PASS\",\"ready\":"<<stats.ready<<",\"rejected\":"<<stats.rejected<<",\"cache_hits\":"<<stats.cacheHits<<",\"pending\":"<<stats.pending<<"}\n";
      return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
  }
}
