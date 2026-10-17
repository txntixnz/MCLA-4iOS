#pragma once

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dispatch/dispatch.h>
#include "MCLAShaderLibraryBytes.h"

namespace mcla::metal {

inline id<MTLLibrary> NewLibraryFromFileBytes(id<MTLDevice> device,
                                             NSURL* url, NSError** error) {
  if (error) *error = nil;
  auto fail = [&](int code) -> id<MTLLibrary> {
    if (error) *error = [NSError errorWithDomain:NSPOSIXErrorDomain code:code
        userInfo:url ? @{NSURLErrorKey:url} : nil];
    return nil;
  };
  if (!device || !url.isFileURL) return fail(EINVAL);
  auto bytes = ReadShaderLibraryBytes(url.fileSystemRepresentation);
  if (!bytes) return fail(bytes.error);
  // DEFAULT copies the vector into owned dispatch storage. Metal may retain
  // it for deferred function creation, after the vector has been destroyed.
  dispatch_data_t data = dispatch_data_create(bytes.data.data(), bytes.data.size(),
                                              nullptr, DISPATCH_DATA_DESTRUCTOR_DEFAULT);
  if (!data) return fail(ENOMEM);
  return [device newLibraryWithData:data error:error];
}

} // namespace mcla::metal
