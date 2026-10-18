#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "../MCLAApp/runtime/MCLAVisualFrameCapture.h"
#include <cassert>
#include <thread>
#include <vector>
int main(int argc,const char** argv) { @autoreleasepool {
  assert(argc==2);
  id<MTLDevice> device=MTLCreateSystemDefaultDevice();
  if(!device){std::puts("SKIP: no Metal device; native GPU readback not exercised");return 77;}
  auto queue=[device newCommandQueue];auto commands=[queue commandBuffer];
  auto descriptor=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:640 height:360 mipmapped:NO];
  descriptor.storageMode=MTLStorageModeShared;
  auto texture=[device newTextureWithDescriptor:descriptor];assert(texture);
  std::vector<uint8_t> pixels(640*360*4,0);
  for(unsigned y=0;y<360;++y)for(unsigned x=0;x<640;++x){
    size_t at=(y*640+x)*4;pixels[at]=(x>=280&&x<360&&y>=140&&y<220)?255:16;
    pixels[at+1]=32;pixels[at+2]=48;pixels[at+3]=255;
  }
  [texture replaceRegion:MTLRegionMake2D(0,0,640,360) mipmapLevel:0 withBytes:pixels.data() bytesPerRow:640*4];
  auto& request=mcla::metal::visualCaptureRequest;
  assert(request.Request(0)&&request.Begin(3000000000ull));
  mcla::metal::VisualFrameCapture capture;capture.Start(7);
  std::array<uint8_t,16384> state{};state[12432]=0x12;state[12433]=0x34;
  capture.Draw(state.data(),42,0x123456789ABCDEF0ull,0xFEDCBA9876543210ull,4,6,texture);
  capture.Draw(state.data(),43,0x123456789ABCDEF0ull,0xFEDCBA9876543210ull,4,6,texture);
  assert(capture.Snapshot(commands,texture,@"guest-pass-end",0x12340000,43));
  assert(capture.Snapshot(commands,texture,@"present-source",0x4567,43,true));
  NSString* root=[NSString stringWithUTF8String:argv[1]];
  capture.Finish(commands,root);
  assert(!capture.Active()&&request.Get()==mcla::metal::VisualCaptureRequest::State::Saving);
  [commands commit];[commands waitUntilCompleted];
  for(int i=0;i<1000 && request.Get()==mcla::metal::VisualCaptureRequest::State::Saving;++i)
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  assert(request.Get()==mcla::metal::VisualCaptureRequest::State::Saved);
  NSData* readback=[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:@"image-01.bin"]];
  assert(readback.length==pixels.size()&&!std::memcmp(readback.bytes,pixels.data(),pixels.size()));
  std::puts("PASS: actual Metal fence/readback, two snapshots, state trace, deduplicated constants, saved result");
} }
