#pragma once
#include "MCLAGPUFaultJournal.h"
#include <vector>
#include <utility>
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

namespace mcla::metal {
inline std::string FaultText(NSString* text, size_t limit = 1024) {
  const char* bytes = text.UTF8String;
  return GPUFaultJournal::Quote(bytes ? bytes : "", limit);
}
inline bool StartGPUFaultCapture(GPUFaultJournal& journal, NSString* directory,
    NSDictionary* info, NSString* gpu, bool detailedLogging) {
  const std::string identity =
      "\"session\":" + FaultText(NSUUID.UUID.UUIDString, 64) +
      ",\"pid\":" + std::to_string(getpid()) +
      ",\"build\":" + FaultText([info[@"CFBundleVersion"] description], 64) +
      ",\"version\":" + FaultText([info[@"CFBundleShortVersionString"] description], 64) +
      ",\"profile\":" + FaultText([info[@"MCLABringupProfile"] description], 128) +
      ",\"os\":" + FaultText(NSProcessInfo.processInfo.operatingSystemVersionString, 128) +
      ",\"gpu\":" + FaultText(gpu, 128) +
      ",\"detailed_logging\":" + (detailedLogging ? "true" : "false");
  return journal.Open(directory.fileSystemRepresentation, identity);
}
// This entry point is shared by the real completion handler and the native
// synthetic-error test. It never mutates a pipeline, resource, or shader.
inline bool CaptureGPUFailure(GPUFaultJournal& journal, id<MTLCommandBuffer> cb,
    uint64_t frame, uint64_t errors, bool active, unsigned thermal,
    const std::vector<std::pair<bool,uint64_t>>& automaticShaders) {
  std::string data = "{\"frame\":" + std::to_string(frame) +
      ",\"error_count\":" + std::to_string(errors) +
      ",\"command_buffer\":" + FaultText(cb.label, 256) +
      ",\"domain\":" + FaultText(cb.error.domain, 128) +
      ",\"code\":" + std::to_string(cb.error.code) +
      ",\"description\":" + FaultText(cb.error.localizedDescription, 1024) +
      ",\"active\":" + (active ? "true" : "false") +
      ",\"thermal\":" + std::to_string(thermal) +
      ",\"automatic_shader_count\":" + std::to_string(automaticShaders.size()) +
      ",\"automatic_shaders\":[";
  for (size_t i = 0; i < std::min<size_t>(24, automaticShaders.size()); ++i) {
    char name[24];
    std::snprintf(name, sizeof(name), "%s-%016llX", automaticShaders[i].first ? "vs" : "ps",
        (unsigned long long)automaticShaders[i].second);
    if (i) data += ',';
    data += GPUFaultJournal::Quote(name);
  }
  data += "],\"encoders\":[";
  id records = cb.error.userInfo[MTLCommandBufferEncoderInfoErrorKey];
  unsigned reported = 0, candidates = 0;
  if ([records isKindOfClass:NSArray.class]) {
    for (id<MTLCommandBufferEncoderInfo> encoder in records)
      if (encoder.errorState != MTLCommandEncoderErrorStateCompleted) ++candidates;
    // Keep the actual faulted encoders ahead of affected/pending encoders.
    for (unsigned priority = 0; priority < 2; ++priority)
      for (id<MTLCommandBufferEncoderInfo> encoder in records) {
        if (reported >= 12 || encoder.errorState == MTLCommandEncoderErrorStateCompleted ||
            ((encoder.errorState == MTLCommandEncoderErrorStateFaulted) != (priority == 0))) continue;
        if (reported++) data += ',';
        data += "{\"state\":" + std::to_string(encoder.errorState) +
            ",\"label\":" + FaultText(encoder.label, 768) +
            ",\"signposts\":" + FaultText([encoder.debugSignposts componentsJoinedByString:@" | "], 256) + "}";
      }
  }
  data += "],\"encoders_omitted\":" + std::to_string(candidates - reported) + "}";
  return journal.Record("gpu_error", data);
}
}
