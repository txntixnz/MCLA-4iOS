#!/usr/bin/env python3
"""Run the production vertex-binding branch with diagnostics both on and off.

On macOS also render a triangle through that branch and verify GPU readback.
--cpu-only permits the control-flow regression to run on other build hosts.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
COMMON=r'''
#include "MCLADiagnostics.h"
#include <array>
#include <cstdio>
#include <cstddef>
'''
CPU=r'''
struct Encoder { unsigned calls=0; void Bind(int,size_t,unsigned) {++calls;} };
int main(){
  struct Binding{int buffer=0;size_t offset=0;};
  std::array<Binding,17> boundVertices_{};
  unsigned vertexBindSkips_=0;
  Encoder encoder_;
  auto bind=[&](int buffer,size_t offset,unsigned s){
    Binding b{buffer,0};
BIND
  };
  bind(1,0,0);
  if(boundVertices_[0].buffer!=1 || encoder_.calls!=1){puts("FAIL: first vertex buffer was not bound");return 1;}
  bind(1,0,0);
  if(encoder_.calls!=1 || vertexBindSkips_!=(mcla::kGameplayOnly?0u:1u))return 2;
  bind(1,24,0);
  if(boundVertices_[0].offset!=24 || encoder_.calls!=2)return 3;
  bind(2,0,0);
  if(boundVertices_[0].buffer!=2 || encoder_.calls!=3)return 4;
  puts("PASS: production branch binds first/changed buffers and offsets; identical bindings are reused");
}
'''
GPU=r'''
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstring>
int main(){@autoreleasepool {
  id<MTLDevice> device=MTLCreateSystemDefaultDevice();if(!device)return 77;
  NSError* error=nil;
  NSString* source=@"#include <metal_stdlib>\nusing namespace metal;\nvertex float4 v(uint i [[vertex_id]], const device float2* p [[buffer(9)]]) { return float4(p[i],0,1); }\nfragment half4 f(){return half4(1,0,0,1);}";
  auto library=[device newLibraryWithSource:source options:nil error:&error];
  if(!library){fprintf(stderr,"%s\n",error.description.UTF8String);return 10;}
  auto pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[library newFunctionWithName:@"v"];pd.fragmentFunction=[library newFunctionWithName:@"f"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
  auto pipeline=[device newRenderPipelineStateWithDescriptor:pd error:&error];if(!pipeline)return 11;
  auto td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:8 height:8 mipmapped:NO];td.storageMode=MTLStorageModeShared;td.usage=MTLTextureUsageRenderTarget;
  auto target=[device newTextureWithDescriptor:td];
  auto rp=[MTLRenderPassDescriptor renderPassDescriptor];rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  auto queue=[device newCommandQueue];auto cb=[queue commandBuffer];auto encoder_=[cb renderCommandEncoderWithDescriptor:rp];[encoder_ setRenderPipelineState:pipeline];
  const float points[]={3,3,4,3,3,4, -1,-1,1,-1,0,1};
  auto a=[device newBufferWithBytes:points length:sizeof(points) options:MTLResourceStorageModeShared];
  auto b2=[device newBufferWithBytes:points+6 length:24 options:MTLResourceStorageModeShared];
  [encoder_ setVertexBuffer:a offset:0 atIndex:9];
  struct Binding{id<MTLBuffer> buffer=nil;size_t offset=0;};std::array<Binding,17> boundVertices_{};unsigned vertexBindSkips_=0;
  auto bind=[&](id<MTLBuffer> buffer,size_t offset,unsigned s){Binding b{buffer,0};
BIND
  };
  bind(a,0,0);
  if(boundVertices_[0].buffer!=a){puts("FAIL: first vertex buffer was not bound");return 1;}
  bind(a,0,0);
  if(vertexBindSkips_!=(mcla::kGameplayOnly?0u:1u))return 2;
  bind(a,24,0);if(boundVertices_[0].offset!=24)return 3;
  bind(b2,0,0);if(boundVertices_[0].buffer!=b2)return 4;
  [encoder_ drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[encoder_ endEncoding];[cb commit];[cb waitUntilCompleted];
  if(cb.status!=MTLCommandBufferStatusCompleted)return 12;
  unsigned char pixels[8*8*4]{};[target getBytes:pixels bytesPerRow:32 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
  auto p=pixels+(4*8+4)*4;
  if(p[0]!=255 || p[1]!=0 || p[2]!=0 || p[3]!=255){fprintf(stderr,"FAIL: triangle center %u,%u,%u,%u\n",p[0],p[1],p[2],p[3]);return 13;}
  puts("PASS: actual production vertex binding renders the expected triangle on Metal");
}}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--renderer',type=Path,default=ROOT/'MCLAApp/runtime/MCLAMetalRenderer.mm');p.add_argument('--cpu-only',action='store_true');a=p.parse_args()
 source=a.renderer.read_text();start=source.index('        if(boundVertices_[s].buffer==b.buffer && boundVertices_[s].offset==offset)');end=source.index('      }\n    mark(3);',start);block=source[start:end]
 if a.cpu_only:
  block=block.replace('[encoder_ setVertexBuffer:b.buffer offset:offset atIndex:9+s];','encoder_.Bind(b.buffer,offset,9+s);')
 with tempfile.TemporaryDirectory(prefix='mcla-vertex-binding-') as d:
  d=Path(d);src=d/('test.cpp' if a.cpu_only else 'test.mm');src.write_text(COMMON+(CPU if a.cpu_only else GPU).replace('BIND',block))
  for gameplay in (0,1):
   binary=d/('test'+str(gameplay));cmd=(['c++'] if a.cpu_only else ['xcrun','clang++'])+['-std=c++20','-O2','-DMCLA_GAMEPLAY_ONLY='+str(gameplay),'-I'+str(ROOT/'MCLAApp/runtime'),str(src),'-o',str(binary)]
   if not a.cpu_only:cmd+=['-fobjc-arc','-fblocks','-framework','Foundation','-framework','Metal']
   subprocess.run(cmd,check=True)
   result=subprocess.run([str(binary)])
   if result.returncode:return result.returncode
   print('PASS: gameplay_only='+str(gameplay),flush=True)
 return 0
if __name__=='__main__':raise SystemExit(main())
