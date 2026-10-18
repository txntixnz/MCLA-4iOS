#pragma once
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <mutex>
#include <string>
#include <string_view>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace mcla::metal {
// Only session/fault/recovery events reach disk. Two bounded JSONL files remain
// available without ReX logging, including after the process is reopened.
class GPUFaultJournal {
public:
  static constexpr size_t kFileBytes = 128 * 1024;
  static constexpr size_t kRecordBytes = 16 * 1024;
  static std::string Quote(std::string_view text, size_t limit = 1024) {
    std::string out = "\"";
    for (size_t i = 0; i < text.size();) {
      const unsigned char c = text[i];
      std::string token;
      size_t width = 1;
      if (c == '"' || c == '\\') { token = '\\'; token += char(c); }
      else if (c < 32) {
        constexpr char hex[] = "0123456789abcdef";
        token = "\\u00"; token += hex[c >> 4]; token += hex[c & 15];
      } else {
        // Foundation supplies valid UTF-8. Keep whole codepoints at the cap.
        if (c >= 0xC2 && c <= 0xF4)
          width = c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
        width = std::min(width, text.size() - i);
        token.assign(text.substr(i, width));
      }
      if (out.size() - 1 + token.size() > limit) {
        if (out.size() - 1 + 3 <= limit) out += "...";
        break;
      }
      out += token; i += width;
    }
    out += '"';
    return out;
  }
  bool Open(const std::filesystem::path& directory,
            std::string identityFields, size_t fileBytes = kFileBytes) noexcept {
    try {
      std::lock_guard lock(mutex_);
      if (fileBytes < 1024 || fileBytes > kFileBytes || identityFields.size() > 4096)
        return false;
      std::error_code error;
      std::filesystem::create_directories(directory, error);
      if (error) return false;
      current_ = directory / "gpu-faults.jsonl";
      previous_ = directory / "gpu-faults.previous.jsonl";
      identity_ = std::move(identityFields);
      limit_ = fileBytes;
      sequence_ = 0;
      return Append("session", "{}");
    } catch (...) { return false; }
  }
  bool Record(std::string_view event, std::string_view data = "{}") noexcept {
    try {
      std::lock_guard lock(mutex_);
      return Append(event, data);
    } catch (...) { return false; }
  }
private:
  std::mutex mutex_;
  std::filesystem::path current_, previous_;
  std::string identity_;
  uint64_t sequence_ = 0;
  size_t limit_ = kFileBytes;
  static bool RepairTail(int fd, off_t& length) {
    if (!length) return true;
    const size_t size = std::min<uint64_t>(uint64_t(length), kRecordBytes);
    std::string tail(size, '\0');
    if (pread(fd, tail.data(), size, length - size) != ssize_t(size)) return false;
    if (tail.back() == '\n') return true;
    const auto newline = tail.rfind('\n');
    length = newline == std::string::npos ? 0 : length - size + newline + 1;
    return ftruncate(fd, length) == 0;
  }
  bool Append(std::string_view event, std::string_view data) {
    if (current_.empty()) return false;
    const auto now = std::chrono::system_clock::now().time_since_epoch();
    const auto monotonic = std::chrono::steady_clock::now().time_since_epoch();
    std::string line = "{\"schema\":1," + identity_ +
        ",\"utc_ms\":" + std::to_string(std::chrono::duration_cast<std::chrono::milliseconds>(now).count()) +
        ",\"monotonic_ns\":" + std::to_string(std::chrono::duration_cast<std::chrono::nanoseconds>(monotonic).count()) +
        ",\"sequence\":" + std::to_string(++sequence_) +
        ",\"event\":" + Quote(event, 64) + ",\"data\":" + std::string(data) + "}\n";
    if (line.size() > kRecordBytes || line.size() > limit_) return false;
    int fd = open(current_.c_str(), O_RDWR | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return false;
    struct Close { int& fd; ~Close() { if (fd >= 0) close(fd); } } closeFile{fd};
    struct stat stat{};
    if (fstat(fd, &stat) || !S_ISREG(stat.st_mode)) return false;
    off_t length = stat.st_size;
    // Do not carry externally oversized files into the bounded previous slot.
    if (length > off_t(limit_)) {
      if (ftruncate(fd, 0)) return false;
      length = 0;
    }
    if (!RepairTail(fd, length)) return false;
    if (uint64_t(length) + line.size() > limit_) {
      close(fd); fd = -1;
      if (rename(current_.c_str(), previous_.c_str())) return false;
      fd = open(current_.c_str(), O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
      if (fd < 0) return false;
    }
    size_t offset = 0;
    while (offset < line.size()) {
      const auto written = write(fd, line.data() + offset, line.size() - offset);
      if (written < 0 && errno == EINTR) continue;
      if (written <= 0) return false;
      offset += size_t(written);
    }
    return fsync(fd) == 0;
  }
};
}
