#!/usr/bin/env python3
"""GPU readback of the actual renderer Clear method with synthetic targets.

Requires macOS/Metal and the pinned foundation submodule. --renderer permits
running the same assertions against the pre-fix method as a regression check.
"""
import argparse
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PREFIX = r'''
#import <Metal/Metal.h>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unordered_map>
#include "MCLAMetalHelpers.h"
#include "MCLAMetalPresentation.h"
#include "native_color_output.h"
namespace rex::graphics::gta4_native {
constexpr unsigned kGuestDeviceSize=0x5780;
struct SurfaceDescriptor { uint32_t handle=0,address=0,width=8,height=8; };
struct ClearCommand {
  uint32_t device=1,flags=0,color_bits[4]{},stencil=0;
  uint64_t depth_bits=0;
  int32_t left=0,top=0,right=8,bottom=8;
};
}
namespace ng=rex::graphics::gta4_native;
static void Require(bool ok,const char* message) {
  if(!ok){std::fprintf(stderr,"FAIL: %s\n",message);std::exit(1);}
}
static uint32_t R(const uint8_t* p,unsigned at) {
  return uint32_t(p[at])<<24|uint32_t(p[at+1])<<16|uint32_t(p[at+2])<<8|p[at+3];
}
static void Word(uint8_t* p,unsigned at,uint32_t v) {
  for(unsigned i=0;i<4;++i)p[at+i]=uint8_t(v>>(24-i*8));
}
static const uint8_t* MCLANativeCanonicalDevice(const uint8_t* p){return p;}
static unsigned MCLAGraphicsRenderHeight(){return 720;}
static void MCLAGraphicsGuestVideoSize(uint32_t* w,uint32_t* h){*w=1280;*h=720;}
static uint64_t Hash(const void* p,size_t n,uint64_t h) {
  for(auto q=static_cast<const uint8_t*>(p);n--;){h^=*q++;h*=1099511628211ull;}return h;
}
#define REXLOG_ERROR(...) ((void)0)
class ClearHarness {
public:
  id<MTLDevice> device_;
  id<MTLCommandBuffer> commands_;
  id<MTLLibrary> helpers_;
  std::array<id<MTLTexture>,4> targets{};
  std::array<ng::SurfaceDescriptor,4> surfaces{};
  std::array<uint8_t,ng::kGuestDeviceSize> state{};
  std::unordered_map<uint64_t,id<MTLRenderPipelineState>> pipelines_;
  std::unordered_map<uint64_t,id<MTLDepthStencilState>> depths_;
  const uint8_t* P(uint32_t,size_t){return state.data();}
  ng::SurfaceDescriptor Describe(uint32_t h){return h?surfaces.at(h-1):ng::SurfaceDescriptor{};}
  id<MTLTexture> Target(ng::SurfaceDescriptor d,bool){return d.handle?targets.at(d.handle-1):nil;}
  void EndEncoder(){}
  bool Begin(){return true;}
  bool Fail(const char* message){Require(false,message);return false;}
  id<MTLRenderCommandEncoder> RenderEncoder(MTLRenderPassDescriptor* p,const char*) {
    auto e=[commands_ renderCommandEncoderWithDescriptor:p];Require(e!=nil,"create production clear encoder");return e;
  }
'''
SUFFIX = r'''
};
int main(){@autoreleasepool {
  ClearHarness h;h.device_=MTLCreateSystemDefaultDevice();
  if(!h.device_){std::puts("SKIP: no Metal GPU");return 77;}
  NSError* error=nil;
  h.helpers_=[h.device_ newLibraryWithSource:kMCLAMetalHelpers options:nil error:&error];
  if(error)std::fprintf(stderr,"%s\n",error.localizedDescription.UTF8String);
  Require(h.helpers_!=nil,"compile production clear shaders");
  auto queue=[h.device_ newCommandQueue];
  const uint32_t info[]={0x430400u,(62u<<20)|(12u<<16)|0x401u,0x402u,0x440403u};
  for(unsigned i=0;i<4;++i){
    h.surfaces[i]={i+1,info[i],8,8};Word(h.state.data(),12432+4*i,i+1);
    auto d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:8 height:8 mipmapped:NO];
    d.storageMode=MTLStorageModeShared;d.usage=MTLTextureUsageRenderTarget;
    h.targets[i]=[h.device_ newTextureWithDescriptor:d];Require(h.targets[i]!=nil,"allocate MRT target");
  }
  // Independent expected values: captured neutral clear scaled by16, negative
  // exponent /4, unscaled normalized clamp, and fixed16 alpha storage.
  const float input[]={127.f/255.f,.25f,1.5f,.5f};
  const float expected[4][4]={{127.f*16/255,4,24,1},
    {127.f/(255*4),.0625f,.375f,.125f},{127.f/255,.25f,1,.5f},
    {127.f*16/255,4,24,8}};
  const std::array<float,4> sentinel{.125f,.375f,.625f,.25f};
  for(bool partial:{false,true})for(uint32_t flags:{3u,15u}){
    std::array<__fp16,8*8*4> pixels{};
    for(unsigned p=0;p<64;++p)for(unsigned c=0;c<4;++c)pixels[p*4+c]=sentinel[c];
    for(auto texture:h.targets)[texture replaceRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0 withBytes:pixels.data() bytesPerRow:8*8];
    ng::ClearCommand clear;clear.flags=flags;
    if(partial){clear.left=2;clear.top=1;clear.right=5;clear.bottom=5;}
    for(unsigned c=0;c<4;++c)clear.color_bits[c]=std::bit_cast<uint32_t>(input[c]);
    h.commands_=[queue commandBuffer];Require(h.Clear(clear),"production Clear accepted");
    [h.commands_ commit];[h.commands_ waitUntilCompleted];
    if(h.commands_.error)std::fprintf(stderr,"%s\n",h.commands_.error.localizedDescription.UTF8String);
    Require(h.commands_.status==MTLCommandBufferStatusCompleted,"GPU clear completed");
    for(unsigned i=0;i<4;++i){
      [h.targets[i] getBytes:pixels.data() bytesPerRow:8*8 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
      for(unsigned y=0;y<8;++y)for(unsigned x=0;x<8;++x)for(unsigned c=0;c<4;++c){
        const bool written=(flags&(1u<<i))&&(!partial||(x>=2&&x<5&&y>=1&&y<5));
        const float want=float(__fp16(written?expected[i][c]:sentinel[c]));
        const float got=pixels[(y*8+x)*4+c];
        if(got!=want){std::fprintf(stderr,"partial=%d flags=%u target=%u x=%u y=%u channel=%u got=%g expected=%g\n",partial,flags,i,x,y,c,got,want);return 1;}
      }
    }
    std::printf("PASS: actual Clear partial=%d flags=%u, per-target signed exponent/clamp, alpha and untouched pixels\n",partial,flags);
  }
}}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer', type=pathlib.Path,
                        default=ROOT/'MCLAApp/runtime/MCLAMetalRenderer.mm')
    args = parser.parse_args()
    source = args.renderer.read_text()
    start = source.index('  bool Clear(const ng::ClearCommand &c) {')
    end = source.index('  bool CopyColor(', start)
    with tempfile.TemporaryDirectory(prefix='mcla-clear-exponent-') as directory:
        directory = pathlib.Path(directory)
        source_path, binary = directory/'test.mm', directory/'test'
        source_path.write_text(PREFIX + source[start:end] + SUFFIX)
        subprocess.run(['xcrun','clang++','-std=c++20','-fobjc-arc','-fblocks',
                        '-I'+str(ROOT/'MCLAApp/runtime'),
                        '-I'+str(ROOT/'theft4-foundation/glue/rexglue-sdk-main/src/graphics/gta4_native'),
                        str(source_path),'-framework','Foundation','-framework','Metal',
                        '-o',str(binary)],check=True)
        return subprocess.run([str(binary)]).returncode


if __name__ == '__main__':
    raise SystemExit(main())
