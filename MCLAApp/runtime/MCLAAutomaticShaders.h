#pragma once
#include "MCLARuntimeShaderSource.h"
#ifdef __OBJC__
#import <Metal/Metal.h>
#endif
namespace mcla::shader {
bool Enabled();
struct Statistics { unsigned pending,ready,rejected,cacheHits; };
Statistics GetStatistics();
void Request(Input input);
const MCLAMetalShaderInfo* ReadyInfo(uint64_t hash,bool vertex);
bool Suspended(uint64_t hash,bool vertex);
void SuspendAfterGPUError(uint64_t hash,bool vertex);
#ifdef __OBJC__
id<MTLLibrary> ReadyLibrary(uint64_t hash,bool vertex);
#endif
}
