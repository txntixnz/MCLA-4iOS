#include "../../tools/mcla-xenosrecomp/pch.h"
#include "../../tools/mcla-xenosrecomp/shader_recompiler.h"
#include "../../tools/mcla_shader_container_builder.h"
#include "../../tools/mcla_shader_constant_abi.h"
#include "../../tools/mcla_vertex_id_abi.h"
#include "MCLARuntimeShaderSource.h"
#include "MCLARuntimeShaderAssets.h"
#include "shader_identity.h"
#include <functional>
#include <regex>
#include <sstream>
#include <stdexcept>

namespace mcla::shader {
namespace {
void Require(bool condition, const char* why) { if(!condition)throw std::runtime_error(why); }
unsigned Replace(std::string& text, std::string_view from, std::string_view to) {
  unsigned count=0;size_t at=0;
  while((at=text.find(from,at))!=std::string::npos) {text.replace(at,from.size(),to);at+=to.size();++count;}
  return count;
}
unsigned Transform(std::string& text, const std::regex& pattern,
                   const std::function<std::string(const std::smatch&)>& f) {
  std::string result;size_t end=0;unsigned count=0;
  for(std::sregex_iterator it(text.begin(),text.end(),pattern),last;it!=last;++it) {
    result.append(text,end,it->position()-end);result+=f(*it);end=it->position()+it->length();++count;
  }
  result.append(text,end,std::string::npos);text=std::move(result);return count;
}
bool Semantic(unsigned kind,unsigned index) {
  if(kind==0 || kind==3 || kind==6)return index<4;
  if(kind==5)return index<16;
  if(kind==10)return index<2;
  return (kind==7 || kind==1 || kind==2) && index==0;
}
void Validate(const Input& in) {
  Require(in.hash && !in.microcode.empty() && in.microcode.size()<=65532 && in.microcode.size()%12==0,"invalid microcode size");
  Require(native_gfx::ShaderIdentity(in.microcode.data(),in.microcode.size())==in.hash,"microcode identity mismatch");
  Require(in.elements.size()<=31 && in.interpolators.size()<=31 && !(in.outputs&~31u),"invalid descriptor counts");
  Require(!in.vertex || !native_gfx::HasComputedVertexFetchIndex(in.microcode.data(),in.microcode.size()),"computed vertex fetch needs an audited conversion contract");
  std::unordered_set<unsigned> addresses,semantics;
  for(auto e:in.elements) {
    Require(Semantic((e>>12)&15,(e>>16)&15),"unsupported vertex semantic");
    Require(addresses.insert(e&4095).second && semantics.insert((e>>12)&255).second,"duplicate vertex descriptor");
  }
  semantics.clear();
  for(auto e:in.interpolators) {
    const unsigned kind=(e>>4)&15,index=e&15;
    Require((kind==5 && index<16) || (kind==10 && index<2),"unsupported varying semantic");
    Require(semantics.insert(e&255).second,"duplicate varying descriptor");
  }
  // New programs with loops/calls/jumps are captured for offline review.
  // Their integer/control-flow ABI must not be guessed during gameplay.
  struct Exec {unsigned address,count,sequence;};std::vector<Exec> execs;
  size_t limit=in.microcode.size()/12;bool ended=false;
  for(size_t group=0;group<limit;++group) {
    auto p=in.microcode.data()+group*12;
    uint32_t d0=LoadBe32(p),d1=LoadBe32(p+4),d2=LoadBe32(p+8);
    uint32_t w0[2]={d0,(d1>>16)|(d2<<16)},w1[2]={d1&65535,d2>>16};
    for(unsigned half=0;half<2;++half) {
      const unsigned op=(w1[half]>>12)&15;
      Require(op==0 || op==1 || op==2 || op==3 || op==4 || op==12 || op==13 || op==14 || op==15,"control flow requires offline review");
      if(op==1 || op==2 || op==3 || op==4 || op==13 || op==14) {
        unsigned a=w0[half]&4095,n=(w0[half]>>12)&7;
        Require(a>group && n<=6 && size_t(a)+n<=in.microcode.size()/12,"out-of-range instruction block");
        limit=std::min(limit,size_t(a));execs.push_back({a,n,(w0[half]>>16)&4095});
        ended|=op==2 || op==4 || op==14;
      }
    }
  }
  Require(ended && !execs.empty(),"missing shader end");
  for(auto e:execs) {
    Require(e.address>=limit,"instruction overlaps control flow");
    for(unsigned i=0;i<e.count;++i) if((e.sequence>>(2*i))&1) {
      auto p=in.microcode.data()+size_t(e.address+i)*12;auto a=LoadBe32(p),b=LoadBe32(p+4);
      unsigned op=a&31;
      if(op==0) {
        Require(in.vertex,"vertex fetch in pixel shader");
        if((b&4095)==4095)continue;
        Require(addresses.contains(e.address+i),"missing vertex fetch descriptor");
        Require(((a>>5)&63)==0 && (a>>30)==0 && !(a&(1u<<11)),"unsupported vertex fetch index");
      } else {
        Require(op==1 || op==19,"unsupported texture fetch opcode");
        Require(((a>>20)&31)<26,"texture slot exceeds renderer descriptor bank");
      }
    }
  }
}
void Gamma(std::string& text) {
  const std::string marker="struct AtomicUintBuffer\n{\n    device atomic_uint* buffer;\n};";
  Require(Replace(text,marker,marker+"\n"+kGamma)==1,"gamma helper insertion mismatch");
  Replace(text,"textureHeap[resourceDescriptorIndex]","textureHeap[mclaTextureIndex(resourceDescriptorIndex)]");
  std::vector<int> branches;std::string rewritten;
  unsigned dimensions=0;
  for(size_t at=0;at<text.size();) {
    auto end=text.find('\n',at);if(end==std::string::npos)end=text.size();else ++end;
    std::string line=text.substr(at,end-at),directive=line;
    directive.erase(0,directive.find_first_not_of(" \t\r\n"));
    directive.erase(directive.find_last_not_of(" \t\r\n")+1);
    if(directive.starts_with("#if ") || directive.starts_with("#ifdef ") || directive.starts_with("#ifndef "))
      branches.push_back(directive=="#ifdef __air__"?1:directive=="#ifndef __air__"?0:-1);
    else if(directive=="#else" && !branches.empty() && branches.back()!=-1)branches.back()=!branches.back();
    else if(directive=="#endif" && !branches.empty())branches.pop_back();
    if(std::find(branches.begin(),branches.end(),1)!=branches.end() && std::find(branches.begin(),branches.end(),0)==branches.end())
      dimensions+=Replace(line,"getTexture2DDimensions(texture)","mclaLogicalTexture2DDimensions(texture, resourceDescriptorIndex)");
    rewritten+=line;at=end;
  }
  Require(dimensions==6,"logical texture dimensions mismatch");text=std::move(rewritten);
  auto sample=[](const std::smatch& m){return "return mclaDecodeTextureSample("+m[1].str()+", resourceDescriptorIndex);";};
  Require(Transform(text,std::regex(R"(return (texture\.sample\([\s\S]*?\));)"),sample)==10,"texture sample ABI mismatch");
  Require(Transform(text,std::regex(R"(return (textureHeap\[mclaTextureIndex\(resourceDescriptorIndex\)\]\.tex\.sample\([\s\S]*?\));)"),sample)==1,"cube sample ABI mismatch");
}
}
const char* Revision(){return kRevision;}
bool Generate(const Input& input,Generated& output,std::string& error) {
  try {
    Validate(input);auto container=BuildContainer(!input.vertex,input.microcode,input.elements,input.interpolators,input.outputs);
    ShaderRecompiler compiler;compiler.recompile(container.data(),kCommon);
    auto patched=input.vertex?MCLAVertexIdABI(compiler.out):MCLAFullPixelBank(compiler.out);
    Require(patched.has_value(),"constant/vertex ID ABI mismatch");std::string text=std::move(*patched);
    // Container preparation already removes all-KEEP vertex fetch operations.
    Gamma(text);MCLAMetalShaderInfo info{};info.hash=input.hash;info.vertex=input.vertex;info.textures=0x3FFFFFF;
    for(auto& mask:info.constants)mask=UINT64_MAX;
    Transform(text,std::regex(R"((float[1-4]?|uint[1-4]?|int[1-4]?)\s+(\w+)\s+\[\[attribute\((\d+)\)\]\])"),[&](const std::smatch& m){
      Require(info.count<31,"too many vertex attributes");auto index=info.count++;
      auto type=m[1].str();info.attributes[index]={uint8_t(std::stoul(m[3].str())),uint8_t(index),uint8_t(std::isdigit(type.back())?type.back()-'0':1),uint8_t(type.starts_with("uint")?1:type.starts_with("int")?2:0)};
      return type+" "+m[2].str()+" [[attribute("+std::to_string(index)+")]]";
    });
    Replace(text,"[[early_fragment_tests]]","");
    if(!input.vertex) {
      std::string epilogue="#ifdef __air__\n";
      for(unsigned i=0;i<4;++i) if(input.outputs&(1u<<i)) {
        auto n=std::to_string(i);auto offset=864+i*48;info.colors|=1u<<i;
        epilogue+="output.oC"+n+" *= *reinterpret_cast<device float4*>(g_PushConstants.SharedConstants + "+std::to_string(offset)+");\n";
        epilogue+="float4 lo"+n+"=*reinterpret_cast<device float4*>(g_PushConstants.SharedConstants + "+std::to_string(offset+16)+");\n";
        epilogue+="float4 hi"+n+"=*reinterpret_cast<device float4*>(g_PushConstants.SharedConstants + "+std::to_string(offset+32)+");\n";
        epilogue+="output.oC"+n+" = select(output.oC"+n+", clamp(output.oC"+n+", lo"+n+", hi"+n+"), lo"+n+" <= hi"+n+");\n";
      }
      epilogue+="#endif\n\treturn output;";
      Require(Replace(text,"\treturn output;",epilogue)>0,"missing shader epilogue");
    }
    Require(text.size()<=512*1024 && text.find("while (true)")==std::string::npos,"unbounded shader source");
    output={info,std::move(text)};error.clear();return true;
  }catch(const std::exception& e){error=e.what();return false;}
}
}
