// Synthetic descriptor-pressure regression. No title shaders or GPU required.
// On Apple, also exercise the actual Objective-C++ Metal data-loader boundary.
#include "../MCLAApp/runtime/MCLAShaderLibraryBytes.h"
#include <array>
#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <string>
#include <sys/resource.h>
#if defined(__OBJC__) && defined(__APPLE__)
#include "../MCLAApp/runtime/MCLAMetalLibrary.h"
#endif

namespace {
constexpr unsigned kFiles = 640;
unsigned OpenFiles() {
  unsigned count = 0;
  for (int fd = 0; fd < 64; ++fd)
    if (fcntl(fd, F_GETFD) != -1 || errno != EBADF) ++count;
  return count;
}
std::array<uint8_t, 513> Payload(unsigned index) {
  std::array<uint8_t, 513> bytes{};
  for (unsigned i = 0; i < bytes.size(); ++i) bytes[i] = uint8_t(index + i * 17);
  return bytes;
}
void Write(const std::filesystem::path& path, const void* bytes, size_t size) {
  int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0600);
  assert(fd >= 0);
  assert(write(fd, bytes, size) == ssize_t(size));
  assert(close(fd) == 0);
}
}

#if defined(__OBJC__) && defined(__APPLE__)
@interface MCLATestLibrary : NSObject
@property(nonatomic, strong) dispatch_data_t bytes;
@end
@implementation MCLATestLibrary
@end

@interface MCLATestDevice : NSObject
@property(nonatomic) unsigned expectedDescriptors;
@property(nonatomic) bool failNext;
- (id<MTLLibrary>)newLibraryWithData:(dispatch_data_t)data error:(NSError**)error;
@end
@implementation MCLATestDevice
- (id<MTLLibrary>)newLibraryWithData:(dispatch_data_t)data error:(NSError**)error {
  // The input descriptor must be closed before Metal can retain any bytes.
  assert(OpenFiles() == self.expectedDescriptors);
  if (self.failNext) {
    self.failNext = false;
    if (error) *error = [NSError errorWithDomain:@"MCLATest" code:1 userInfo:nil];
    return nil;
  }
  auto library = [MCLATestLibrary new];
  library.bytes = data;
  return (id<MTLLibrary>)library;
}
@end
#endif

int main() {
#if defined(__OBJC__) && defined(__APPLE__)
  @autoreleasepool {
#endif
  rlimit original{};
  assert(getrlimit(RLIMIT_NOFILE, &original) == 0);
  auto limited = original;
  limited.rlim_cur = 64;
  assert(setrlimit(RLIMIT_NOFILE, &limited) == 0);
  std::string pattern = (std::filesystem::temp_directory_path() / "mcla-libraries-XXXXXX").string();
  char* directory = mkdtemp(pattern.data());
  assert(directory);
  const std::filesystem::path root(directory);
  struct Cleanup {
    std::filesystem::path path;
    rlimit limit;
    ~Cleanup() { std::filesystem::remove_all(path); setrlimit(RLIMIT_NOFILE, &limit); }
  } cleanup{root, original};
  for (unsigned i = 0; i < kFiles; ++i) {
    auto bytes = Payload(i);
    Write(root / std::to_string(i), bytes.data(), bytes.size());
  }
  const unsigned baseline = OpenFiles();
  std::vector<std::vector<uint8_t>> retained;
#if defined(__OBJC__) && defined(__APPLE__)
  auto device = [MCLATestDevice new];
  device.expectedDescriptors = baseline;
  std::vector<id<MTLLibrary>> libraries;
#endif
  for (unsigned i = 0; i < kFiles; ++i) {
    const auto path = root / std::to_string(i);
    auto file = mcla::metal::ReadShaderLibraryBytes(path.c_str());
    auto expected = Payload(i);
    assert(file && file.data.size() == expected.size());
    assert(std::equal(file.data.begin(), file.data.end(), expected.begin()));
    retained.push_back(std::move(file.data));
    assert(OpenFiles() == baseline);
#if defined(__OBJC__) && defined(__APPLE__)
    NSError* error = nil;
    auto url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:path.c_str()]];
    auto library = mcla::metal::NewLibraryFromFileBytes((id<MTLDevice>)device, url, &error);
    assert(library && !error);
    libraries.push_back(library);
#endif
  }
  assert(OpenFiles() == baseline);
#if defined(__OBJC__) && defined(__APPLE__)
  for (unsigned i = 0; i < kFiles; ++i) {
    auto library = (MCLATestLibrary*)libraries[i];
    const void* bytes = nullptr;
    size_t size = 0;
    auto mapped = dispatch_data_create_map(library.bytes, &bytes, &size);
    auto expected = Payload(i);
    assert(mapped && size == expected.size());
    assert(memcmp(bytes, expected.data(), size) == 0);
  }
  NSError* error = nil;
  auto url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:(root / "0").c_str()]];
  device.failNext = true;
  assert(!mcla::metal::NewLibraryFromFileBytes((id<MTLDevice>)device, url, &error) && error);
  assert(mcla::metal::NewLibraryFromFileBytes((id<MTLDevice>)device, url, &error) && !error);
#endif
  assert(mcla::metal::ReadShaderLibraryBytes(nullptr).error == EINVAL);
  assert(mcla::metal::ReadShaderLibraryBytes((root / "missing").c_str()).error == ENOENT);
  Write(root / "empty", nullptr, 0);
  assert(mcla::metal::ReadShaderLibraryBytes((root / "empty").c_str()).error == EINVAL);
  assert(mcla::metal::ReadShaderLibraryBytes(root.c_str()).error == EINVAL);
  int large = open((root / "large").c_str(), O_WRONLY | O_CREAT, 0600);
  assert(large >= 0 && ftruncate(large, 64 * 1024 * 1024 + 1) == 0);
  close(large);
  assert(mcla::metal::ReadShaderLibraryBytes((root / "large").c_str()).error == EFBIG);
  assert(OpenFiles() == baseline);
  // Force EMFILE, then free a slot and prove the next load recovers.
  std::vector<int> held;
  for (;;) {
    int fd = open((root / "0").c_str(), O_RDONLY);
    if (fd < 0) { assert(errno == EMFILE); break; }
    held.push_back(fd);
  }
  assert(mcla::metal::ReadShaderLibraryBytes((root / "0").c_str()).error == EMFILE);
  close(held.back()); held.pop_back();
  assert(mcla::metal::ReadShaderLibraryBytes((root / "0").c_str()));
  for (int fd : held) close(fd);
  assert(OpenFiles() == baseline);
  std::cout << "PASS: 640 retained shader inputs with a 64-descriptor limit; "
               "byte ownership, failure cleanup and EMFILE recovery\n";
#if defined(__OBJC__) && defined(__APPLE__)
  std::cout << "PASS: actual Objective-C++ loader passes owned dispatch data "
               "after closing each file; retained bytes survive input destruction\n";
  }
#endif
}
