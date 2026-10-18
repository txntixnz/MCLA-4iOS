#import <Foundation/Foundation.h>
#include "../runtime/MCLAGPUFaultCapture.h"
#import "../ios/MCLALogArchive.h"
#include <cassert>

@interface FaultEncoderFixture : NSObject
@property MTLCommandEncoderErrorState errorState;
@property(copy) NSString* label;
@property(copy) NSArray<NSString*>* debugSignposts;
@end
@implementation FaultEncoderFixture
@end
@interface FaultCommandFixture : NSObject
@property(strong) NSError* error;
@property(copy) NSString* label;
@end
@implementation FaultCommandFixture
@end

int main(int argc, char** argv) {
  @autoreleasepool {
    assert(argc == 3);
    NSString* home = [NSString stringWithUTF8String:argv[1]];
    NSString* directory = [home stringByAppendingPathComponent:@"Library/Application Support/MCLA/logs"];
    NSDictionary* app = @{@"CFBundleVersion":@"26", @"CFBundleShortVersionString":@"1.0.4",
        @"MCLABringupProfile":@"synthetic-fault-test"};
    mcla::metal::GPUFaultJournal journal;
    assert(mcla::metal::StartGPUFaultCapture(journal,directory,app,@"synthetic GPU",false));
    // Rotate real files, then preserve a synthetic Metal error through reopen
    // and the shipping Export Logs implementation. No GPU hang is injected.
    for (int i=0;i<300;++i)
      assert(journal.Record("rotation_fixture", "{\"payload\":" +
          mcla::metal::GPUFaultJournal::Quote(std::string(700,'x')) + "}"));
    NSMutableArray* encoders = [NSMutableArray array];
    for (int i=0;i<20;++i) {
      auto fixture = [FaultEncoderFixture new];
      fixture.errorState = i==19 ? MTLCommandEncoderErrorStateFaulted :
          i==1 ? MTLCommandEncoderErrorStateCompleted : MTLCommandEncoderErrorStateAffected;
      fixture.label = i==19 ? @"fault \"label\" 測試" :
          [@"long-label" stringByPaddingToLength:1600 withString:@"測試" startingAtIndex:0];
      fixture.debugSignposts = @[@"first\nsecond",@"quote\"",@"測試"];
      [encoders addObject:fixture];
    }
    auto command = [FaultCommandFixture new];
    command.label = @"MCLA handwritten Metal frame 692";
    command.error = [NSError errorWithDomain:MTLCommandBufferErrorDomain
        code:MTLCommandBufferErrorPageFault userInfo:@{
          NSLocalizedDescriptionKey:@"Synthetic invalid GPU read; not a hardware test",
          MTLCommandBufferEncoderInfoErrorKey:encoders}];
    std::vector<std::pair<bool,uint64_t>> shaders{{true,0x0123456789ABCDEFull}};
    assert(mcla::metal::CaptureGPUFailure(journal,(id<MTLCommandBuffer>)command,
        692,1,true,0,shaders));
    assert(journal.Record("recovery_begin","{\"frame\":694}"));
    assert(journal.Record("recovery_complete","{\"frame\":694}"));
    mcla::metal::GPUFaultJournal reopened;
    assert(mcla::metal::StartGPUFaultCapture(reopened,directory,app,@"synthetic GPU",false));
    NSError* error = nil;
    const BOOL exported = [MCLALogArchive exportHome:[NSURL fileURLWithPath:home]
        report:@"Synthetic capture regression" toURL:[NSURL fileURLWithPath:
            [NSString stringWithUTF8String:argv[2]]] error:&error];
    if (!exported) NSLog(@"%@",error);
    assert(exported);
  }
  puts("PASS: shipping Metal error serializer + retained Retail Mode journal + actual ZIP exporter (synthetic errors)");
}
