#include "MCLAAutomaticShaders.h"
#import <CommonCrypto/CommonDigest.h>
#import <Foundation/Foundation.h>
#import <QuartzCore/QuartzCore.h>
#include <array>
#include <atomic>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <cstdlib>
#include "shader_identity.h"
#ifdef MCLA_AUTOMATIC_SHADER_TEST
#define REXLOG_INFO(...) ((void)0)
#define REXLOG_WARN(...) ((void)0)
#else
#include <rex/logging.h>
#include "MCLAQuietLogging.h"
#endif

namespace mcla::shader {
namespace {
using Key=std::pair<bool,uint64_t>;
using Digest=std::array<uint8_t,CC_SHA256_DIGEST_LENGTH>;
Digest SHA(const void* p,size_t n) {Digest d{};CC_SHA256(p,CC_LONG(n),d.data());return d;}
Digest Signature(const Input& in) {
  CC_SHA256_CTX c;CC_SHA256_Init(&c);
  auto add=[&](const void* p,size_t n){CC_SHA256_Update(&c,p,CC_LONG(n));};
  const uint32_t counts[]={uint32_t(in.vertex),uint32_t(in.microcode.size()),uint32_t(in.elements.size()),uint32_t(in.interpolators.size()),in.outputs};
  add(counts,sizeof(counts));add(in.microcode.data(),in.microcode.size());add(in.elements.data(),in.elements.size()*4);add(in.interpolators.data(),in.interpolators.size()*4);
  Digest d{};CC_SHA256_Final(d.data(),&c);return d;
}
NSString* Name(Key key) {return [NSString stringWithFormat:@"%s-%016llX",key.first?"vs":"ps",(unsigned long long)key.second];}
NSString* Root() {
#ifdef MCLA_AUTOMATIC_SHADER_TEST
  if(const char* path=std::getenv("MCLA_AUTOMATIC_SHADER_TEST_CACHE"))return [NSString stringWithUTF8String:path];
#endif
  return [[NSHomeDirectory() stringByAppendingPathComponent:@"Library/Caches/MCLA/AutomaticShaders"] stringByAppendingPathComponent:[NSString stringWithUTF8String:Revision()]];
}
NSString* Path(Key key,NSString* extension){return [[Root() stringByAppendingPathComponent:Name(key)] stringByAppendingPathExtension:extension];}
struct Entry {
  std::atomic<bool> ready{false},suspended{false};
  MCLAMetalShaderInfo info{};
  id<MTLLibrary> library=nil;
};
class Compiler {
  std::mutex mutex_;
  std::map<Key,std::unique_ptr<Entry>> entries_;
  dispatch_queue_t queue_=dispatch_queue_create("com.txntixnz.mcla.shader-generation",dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_SERIAL,QOS_CLASS_UTILITY,0));
  std::atomic<unsigned> pending_{0},ready_{0},failed_{0},cacheHits_{0};
  void Notify() {
    const unsigned pending=pending_.load(),ready=ready_.load(),failed=failed_.load();
    dispatch_async(dispatch_get_main_queue(),^{
      [[NSNotificationCenter defaultCenter] postNotificationName:@"MCLAAutomaticShadersChanged" object:nil
        userInfo:@{@"pending":@(pending),@"ready":@(ready),@"failed":@(failed)}];
    });
  }
  bool Load(Key key,const Digest& signature,Generated& out) {
    NSDictionary* attrs=[[NSFileManager defaultManager] attributesOfItemAtPath:Path(key,@"cache") error:nil];
    const auto size=[attrs[NSFileSize] unsignedLongLongValue];
    if(size<80 || size>600*1024)return false;
    NSData* data=[NSData dataWithContentsOfFile:Path(key,@"cache") options:0 error:nil];
    if(!data || data.length!=size)return false;
    auto bytes=static_cast<const uint8_t*>(data.bytes);
    if(std::memcmp(bytes,"MCLASD01",8) || std::memcmp(bytes+8,signature.data(),32))return false;
    auto digest=SHA(bytes,size-32);if(std::memcmp(bytes+size-32,digest.data(),32))return false;
    uint32_t n=0,count=0,colors=0;std::memcpy(&n,bytes+40,4);std::memcpy(&count,bytes+44,4);std::memcpy(&colors,bytes+48,4);
    if(n>512*1024 || count>31 || colors>15 || (!key.first && count) || (key.first && colors) || size!=52+count*4+n+32)return false;
    MCLAMetalShaderInfo info{};info.hash=key.second;info.vertex=key.first;info.count=count;info.colors=colors;info.textures=0x3FFFFFF;
    for(auto& mask:info.constants)mask=UINT64_MAX;
    for(unsigned i=0;i<count;++i) {
      auto p=bytes+52+i*4;
      if(p[0]>32 || p[1]!=i || p[2]<1 || p[2]>4 || p[3]>2)return false;
      info.attributes[i]={p[0],p[1],p[2],p[3]};
    }
    std::string source(reinterpret_cast<const char*>(bytes+52+count*4),n);
    if(source.find("while (true)")!=std::string::npos)return false;
    out={info,std::move(source)};return true;
  }
  void Save(Key key,const Digest& signature,const Generated& out) {
    [[NSFileManager defaultManager] createDirectoryAtPath:Root() withIntermediateDirectories:YES attributes:nil error:nil];
    // Bound the persistent corpus at 128 entries (under 76 MiB).
    NSArray* files=[[NSFileManager defaultManager] contentsOfDirectoryAtPath:Root() error:nil];
    unsigned caches=0;for(NSString* f in files)if([f.pathExtension isEqualToString:@"cache"])++caches;
    if(caches>=128 && ![[NSFileManager defaultManager] fileExistsAtPath:Path(key,@"cache")])return;
    NSMutableData* data=[NSMutableData dataWithBytes:"MCLASD01" length:8];
    [data appendBytes:signature.data() length:32];
    uint32_t n=uint32_t(out.source.size()),count=out.info.count,colors=out.info.colors;
    [data appendBytes:&n length:4];[data appendBytes:&count length:4];[data appendBytes:&colors length:4];
    for(unsigned i=0;i<count;++i) {auto a=out.info.attributes[i];const uint8_t bytes[]={a.semantic,a.location,a.components,a.numeric};[data appendBytes:bytes length:4];}
    [data appendBytes:out.source.data() length:n];auto digest=SHA(data.bytes,data.length);[data appendBytes:digest.data() length:32];
    [data writeToFile:Path(key,@"cache") options:NSDataWritingAtomic error:nil];
  }
  void Work(Key key,std::shared_ptr<Input> input,Entry* entry) {
    @autoreleasepool {
      const auto started=CACurrentMediaTime();Generated generated;std::string error;
      bool success=false,hit=false;
      try {
        if(native_gfx::ShaderIdentity(input->microcode.data(),input->microcode.size())!=key.second)throw std::runtime_error("microcode identity mismatch");
        if([[NSFileManager defaultManager] fileExistsAtPath:Path(key,@"suspended")])throw std::runtime_error("suspended after prior GPU error");
        const auto signature=Signature(*input);hit=Load(key,signature,generated);
        if(!hit && !Generate(*input,generated,error))throw std::runtime_error(error);
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();
        MTLCompileOptions* options=[MTLCompileOptions new];options.languageVersion=MTLLanguageVersion3_0;options.fastMathEnabled=YES;
        options.preprocessorMacros=@{@"__air__":@1,@"GTA4_RECOMP":@1};
        NSError* metalError=nil;
        NSString* source=[[NSString alloc] initWithBytes:generated.source.data() length:generated.source.size() encoding:NSUTF8StringEncoding];
        id<MTLLibrary> library=source?[device newLibraryWithSource:source options:options error:&metalError]:nil;
        if(!library)throw std::runtime_error(metalError.localizedDescription.UTF8String?:"Metal source compilation failed");
        uint32_t specialization=0;MTLFunctionConstantValues* values=[MTLFunctionConstantValues new];
        [values setConstantValue:&specialization type:MTLDataTypeUInt atIndex:0];
        id<MTLFunction> function=[library newFunctionWithName:@"shaderMain" constantValues:values error:&metalError];
        if(!function || function.functionType!=(input->vertex?MTLFunctionTypeVertex:MTLFunctionTypeFragment))throw std::runtime_error("compiled shader entry point/stage mismatch");
        if(!entry->suspended.load()) {
          entry->info=generated.info;entry->library=library;
          if(!hit)Save(key,signature,generated);
          entry->ready.store(true,std::memory_order_release);++ready_;success=true;
          if(hit)++cacheHits_;
        }
      }catch(const std::exception& e){error=e.what();}
      if(!success)++failed_;
      REXLOG_INFO("MCLA AUTO SHADER {} name={} cache={} ms={:.2f} reason={}",success?"ready":"rejected",Name(key).UTF8String,hit,(CACurrentMediaTime()-started)*1000,error);
      --pending_;Notify();
    }
  }
public:
  Statistics StatisticsNow(){return {pending_.load(),ready_.load(),failed_.load(),cacheHits_.load()};}
  Entry* Find(Key key) {std::lock_guard lock(mutex_);auto it=entries_.find(key);return it==entries_.end()?nullptr:it->second.get();}
  void RequestInput(Input input) {
    Key key{input.vertex,input.hash};Entry* entry;
    {
      std::lock_guard lock(mutex_);
      if(entries_.contains(key) || entries_.size()>=128)return;
      entry=entries_.emplace(key,std::make_unique<Entry>()).first->second.get();++pending_;
    }
    auto owned=std::make_shared<Input>(std::move(input));Notify();
    dispatch_async(queue_,^{Work(key,owned,entry);});
  }
  void Suspend(Key key) {
    Entry* entry=Find(key);if(!entry || entry->suspended.exchange(true))return;
    REXLOG_WARN("MCLA AUTO SHADER suspended after GPU error name={} (not proof of causation)",Name(key).UTF8String);
    dispatch_async(queue_,^{@autoreleasepool {
      [[NSFileManager defaultManager] createDirectoryAtPath:Root() withIntermediateDirectories:YES attributes:nil error:nil];
      [@"Suspended after a GPU error in a frame using this program.\n" writeToFile:Path(key,@"suspended") atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }});
  }
};
Compiler& Shared(){static Compiler* c=new Compiler;return *c;}
}
bool Enabled(){static bool value=[] {auto p=std::getenv("MCLA_AUTOMATIC_SHADERS");if(p)return std::strcmp(p,"0")!=0;
    NSUserDefaults* defaults=NSUserDefaults.standardUserDefaults;return ![defaults objectForKey:@"MCLAAutomaticShaders"] || [defaults boolForKey:@"MCLAAutomaticShaders"];}();return value;}
Statistics GetStatistics(){return Shared().StatisticsNow();}
void Request(Input input) {
  if(!Enabled() || !input.hash || input.microcode.empty() || input.microcode.size()>65532 || input.elements.size()>31 || input.interpolators.size()>31)return;
  for(const auto& info:kMCLAMetalShaders)if(info.hash==input.hash && info.vertex==input.vertex)return;
  Shared().RequestInput(std::move(input));
}
const MCLAMetalShaderInfo* ReadyInfo(uint64_t hash,bool vertex) {
  if(!Enabled())return nullptr;auto e=Shared().Find({vertex,hash});
  return e && e->ready.load(std::memory_order_acquire) && !e->suspended.load()?&e->info:nullptr;
}
id<MTLLibrary> ReadyLibrary(uint64_t hash,bool vertex) {
  auto info=ReadyInfo(hash,vertex);if(!info)return nil;return Shared().Find({vertex,hash})->library;
}
bool Suspended(uint64_t hash,bool vertex){auto e=Shared().Find({vertex,hash});return e && e->suspended.load();}
void SuspendAfterGPUError(uint64_t hash,bool vertex){Shared().Suspend({vertex,hash});}
}
