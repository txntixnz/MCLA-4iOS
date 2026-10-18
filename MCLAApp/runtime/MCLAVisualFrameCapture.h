#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "MCLAVisualCaptureRequest.h"
#include <functional>
#include <string_view>
#include <array>
#include <cstring>
#include <vector>

namespace mcla::metal {
// Explicit single-frame evidence. No shader, cache, draw or resolve overrides.
// Target snapshots are ordered after existing encoders. Buffers are read only
// after successful GPU completion, then written on a serial utility queue.
class VisualFrameCapture {
public:
  static constexpr size_t kMaxDraws = 8192, kMaxBanks = 256;
  static constexpr size_t kImageBytes = 16 * 1024 * 1024;
  static constexpr size_t kTotalImageBytes = 48 * 1024 * 1024;
  static constexpr std::array<unsigned,32> kStateOffsets = {
    10376,10436,10440,10460,10492,10496,10500,10548,
    10552,10556,10564,10568,10584,10588,10592,10832,
    10836,10840,10844,11844,11868,11872,12432,12448,
    12640,12644,12648,12652,12660,12664,12668,12672};
  struct DrawRecord {
    uint64_t draw, vs, ps;
    uint32_t primitive, count, surface, width, height, format;
    std::array<uint32_t,32> state;
    std::array<std::array<uint32_t,7>,26> textures; // handle then six fetch words
    uint32_t vsBank, psBank;
  };
  static_assert(sizeof(DrawRecord) == 912);
private:
  bool active_ = false, truncated_ = false;
  uint64_t frame_ = 0, droppedDraws_ = 0;
  size_t imageBytes_ = 0;
  std::vector<DrawRecord> draws_;
  std::vector<std::array<uint8_t,4096>> banks_;
  std::vector<uint64_t> bankHashes_;
  NSMutableArray<NSDictionary*> *images_ = nil;
  NSMutableArray<id<MTLBuffer>> *buffers_ = nil;
  NSString *token_ = nil;
  static uint32_t BE(const uint8_t* p) {
    return (uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3];
  }
  uint32_t Bank(const uint8_t* source) {
    const auto hash = std::hash<std::string_view>{}(std::string_view(reinterpret_cast<const char*>(source),4096));
    for (size_t i=0; i<banks_.size(); ++i)
      if (bankHashes_[i]==hash && !std::memcmp(banks_[i].data(),source,4096)) return uint32_t(i);
    if (banks_.size()==kMaxBanks) {truncated_=true;return UINT32_MAX;}
    std::array<uint8_t,4096> bytes; std::memcpy(bytes.data(),source,4096);
    bankHashes_.push_back(hash); banks_.push_back(bytes); return uint32_t(banks_.size()-1);
  }
public:
  bool Active() const {return active_;}
  void Start(uint64_t frame) {
    active_=true; truncated_=false; frame_=frame; droppedDraws_=0; imageBytes_=0;
    draws_.clear(); banks_.clear(); bankHashes_.clear();
    images_=[NSMutableArray array]; buffers_=[NSMutableArray array];
    token_=NSUUID.UUID.UUIDString;
  }
  void Draw(const uint8_t* state, uint64_t draw, uint64_t vs, uint64_t ps,
      uint32_t primitive, uint32_t count, id<MTLTexture> target) {
    if (!active_) return;
    if (draws_.size()==kMaxDraws) {truncated_=true;++droppedDraws_;return;}
    DrawRecord record{};
    record.draw=draw;record.vs=vs;record.ps=ps;record.primitive=primitive;record.count=count;
    record.surface=BE(state+12432);record.width=uint32_t(target.width);
    record.height=uint32_t(target.height);record.format=uint32_t(target.pixelFormat);
    for (size_t i=0;i<kStateOffsets.size();++i) record.state[i]=BE(state+kStateOffsets[i]);
    for (unsigned i=0;i<26;++i) {
      record.textures[i][0]=BE(state+12536+i*4);
      for(unsigned j=0;j<6;++j) record.textures[i][j+1]=BE(state+1152+i*24+j*4);
    }
    record.vsBank=Bank(state+1920);record.psBank=Bank(state+6016);
    draws_.push_back(record);
  }
  bool Snapshot(id<MTLCommandBuffer> commands, id<MTLTexture> target,
      NSString* phase, uint32_t surface, uint64_t draw, bool final = false) {
    if (!active_ || !commands || !target || target.textureType!=MTLTextureType2D ||
        target.sampleCount!=1 || target.width<640 || target.height<360 ||
        (target.pixelFormat!=MTLPixelFormatRGBA8Unorm &&
         target.pixelFormat!=MTLPixelFormatRGBA16Float)) return false;
    const size_t pixelBytes=target.pixelFormat==MTLPixelFormatRGBA16Float ? 8 : 4;
    const size_t row=(target.width*pixelBytes+255)&~size_t(255);
    const size_t bytes=row*target.height;
    const size_t budget=final ? kTotalImageBytes : kTotalImageBytes-kImageBytes;
    if (images_.count >= (final ? 8u : 7u) || bytes>kImageBytes || imageBytes_+bytes>budget) {
      truncated_=true;return false;
    }
    auto buffer=[commands.device newBufferWithLength:bytes options:MTLResourceStorageModeShared];
    auto blit=buffer ? [commands blitCommandEncoder] : nil;
    if (!blit) {truncated_=true;return false;}
    [blit copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
      sourceSize:MTLSizeMake(target.width,target.height,1) toBuffer:buffer destinationOffset:0
      destinationBytesPerRow:row destinationBytesPerImage:bytes];
    [blit endEncoding];
    [images_ addObject:@{@"file":[NSString stringWithFormat:@"image-%02lu.bin",(unsigned long)images_.count],
      @"phase":phase,@"surface":@(surface),@"draw":@(draw),@"width":@(target.width),
      @"height":@(target.height),@"row_bytes":@(row),@"bytes":@(bytes),
      @"format":pixelBytes==8 ? @"rgba16f-le" : @"rgba8"}];
    [buffers_ addObject:buffer];imageBytes_+=bytes;return true;
  }
  void Finish(id<MTLCommandBuffer> commands, NSString* root = nil) {
    if (!active_) return;
    active_=false;
    if (!commands || !visualCaptureRequest.Saving()) {visualCaptureRequest.Fail();return;}
    NSData* drawData=[NSData dataWithBytes:draws_.data() length:draws_.size()*sizeof(DrawRecord)];
    NSData* bankData=[NSData dataWithBytes:banks_.data() length:banks_.size()*4096];
    NSMutableArray* offsets=[NSMutableArray array]; for(auto offset:kStateOffsets)[offsets addObject:@(offset)];
    NSDictionary* manifest=@{@"schema":@1,@"token":token_,@"frame":@(frame_),
      @"utc_ms":@((uint64_t)(NSDate.date.timeIntervalSince1970*1000)),
      @"build":[NSBundle.mainBundle objectForInfoDictionaryKey:@"CFBundleVersion"] ?: @"test",
      @"profile":[NSBundle.mainBundle objectForInfoDictionaryKey:@"MCLABringupProfile"] ?: @"test",
      @"pid":@(NSProcessInfo.processInfo.processIdentifier),@"gpu":commands.device.name ?: @"unknown",
      @"draw_count":@(draws_.size()),@"draw_record_bytes":@(sizeof(DrawRecord)),
      @"byte_order":@"little",@"state_offsets":offsets,@"constant_bank_bytes":@4096,
      @"constant_byte_order":@"big",@"constant_banks":@(banks_.size()),
      @"missing_bank":@(UINT32_MAX),@"truncated":@(truncated_),@"dropped_draws":@(droppedDraws_),
      @"images":[images_ copy],@"record_layout":@{@"draw":@0,@"vs":@8,@"ps":@16,
        @"primitive":@24,@"count":@28,@"surface":@32,@"width":@36,@"height":@40,
        @"format":@44,@"state_words":@48,@"texture_handle_and_fetch_words":@176,
        @"vs_bank":@904,@"ps_bank":@908}};
    NSArray* buffers=[buffers_ copy];
    NSString* destination=root ?: [NSHomeDirectory() stringByAppendingPathComponent:@"Documents/Diagnostics/VisualFrame"];
    [commands addCompletedHandler:^(id<MTLCommandBuffer> cb) {
      if (cb.status!=MTLCommandBufferStatusCompleted) {visualCaptureRequest.Complete(false);return;}
      static dispatch_queue_t writer=dispatch_queue_create("mcla.visual-evidence",dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_SERIAL,QOS_CLASS_UTILITY,0));
      dispatch_async(writer, ^{
        @autoreleasepool {
          NSFileManager* fm=NSFileManager.defaultManager;
          // Repeated requests replace only this dedicated diagnostic directory.
          NSError* error=nil;
          BOOL ok=[fm createDirectoryAtPath:destination withIntermediateDirectories:YES attributes:nil error:&error];
          for (NSString* name in [fm contentsOfDirectoryAtPath:destination error:&error])
            if (![fm removeItemAtPath:[destination stringByAppendingPathComponent:name] error:&error]) ok=NO;
          if (ok) ok=[drawData writeToFile:[destination stringByAppendingPathComponent:@"draws.bin"] atomically:YES] &&
            [bankData writeToFile:[destination stringByAppendingPathComponent:@"constants.bin"] atomically:YES];
          NSArray* images=manifest[@"images"];
          for(NSUInteger i=0;ok && i<buffers.count;++i) {
            id<MTLBuffer> buffer=buffers[i];
            ok=[[NSData dataWithBytes:buffer.contents length:buffer.length]
              writeToFile:[destination stringByAppendingPathComponent:images[i][@"file"]] atomically:YES];
          }
          if (ok) {
            NSMutableDictionary* completed=[manifest mutableCopy];completed[@"gpu_completed"]=@YES;
            NSData* json=[NSJSONSerialization dataWithJSONObject:completed options:NSJSONWritingPrettyPrinted error:&error];
            ok=json && [json writeToFile:[destination stringByAppendingPathComponent:@"manifest.json"] atomically:YES];
          }
          visualCaptureRequest.Complete(ok);
        }
      });
    }];
    // Completion owns immutable copies; normal play retains no trace storage.
    std::vector<DrawRecord>().swap(draws_);
    std::vector<std::array<uint8_t,4096>>().swap(banks_);
    std::vector<uint64_t>().swap(bankHashes_);
    images_=nil;buffers_=nil;
  }
  void Abort() {
    if (!active_) return;
    active_=false;visualCaptureRequest.Fail();
    std::vector<DrawRecord>().swap(draws_);
    std::vector<std::array<uint8_t,4096>>().swap(banks_);
    std::vector<uint64_t>().swap(bankHashes_);
    images_=nil;buffers_=nil;
  }
};
}
