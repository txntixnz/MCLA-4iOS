#pragma once

#include <cerrno>
#include <cstdint>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace mcla::metal {

struct ShaderLibraryBytes {
  std::vector<uint8_t> data;
  int error = 0;
  explicit operator bool() const { return !error && !data.empty(); }
};

// A library's input must own bytes, never a live bundle file. The descriptor
// closes before returning, including on failed/short reads. Keeping hundreds
// of resulting Metal libraries alive cannot keep these descriptors alive.
inline ShaderLibraryBytes ReadShaderLibraryBytes(const char* path) {
  if (!path) return {{}, EINVAL};
  struct File {
    int fd;
    ~File() { if (fd >= 0) close(fd); }
  } file{open(path, O_RDONLY | O_CLOEXEC)};
  if (file.fd < 0) return {{}, errno};
  struct stat info{};
  if (fstat(file.fd, &info) != 0) return {{}, errno};
  if (!S_ISREG(info.st_mode) || info.st_size <= 0) return {{}, EINVAL};
  constexpr uint64_t kMaximumLibraryBytes = 64 * 1024 * 1024;
  if (uint64_t(info.st_size) > kMaximumLibraryBytes) return {{}, EFBIG};
  ShaderLibraryBytes result;
  result.data.resize(size_t(info.st_size));
  size_t offset = 0;
  while (offset < result.data.size()) {
    const auto count = read(file.fd, result.data.data() + offset,
                            result.data.size() - offset);
    if (count < 0 && errno == EINTR) continue;
    if (count <= 0) return {{}, count < 0 ? errno : EIO};
    offset += size_t(count);
  }
  return result;
}

} // namespace mcla::metal
