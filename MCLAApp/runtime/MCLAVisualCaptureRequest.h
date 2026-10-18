#pragma once
#include <atomic>
#include <chrono>
#include <cstdint>
#include <mutex>

namespace mcla::metal {
// UIKit requests; the submission thread consumes at a command-buffer boundary.
// Terminal results remain visible until the next explicit request.
class VisualCaptureRequest {
public:
  enum class State { Idle, Armed, Capturing, Saving, Saved, Failed };
private:
  std::mutex requestMutex_;
  std::atomic<State> state_{State::Idle};
  std::atomic<uint64_t> readyAt_{0};
public:
  static uint64_t Now() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
  }
  State Get() const { return state_.load(std::memory_order_acquire); }
  bool Request(uint64_t now = Now()) {
    std::lock_guard lock(requestMutex_);
    const auto state = Get();
    if (state == State::Armed || state == State::Capturing || state == State::Saving)
      return false;
    readyAt_.store(now + 3000000000ull, std::memory_order_relaxed);
    state_.store(State::Armed, std::memory_order_release);
    return true;
  }
  bool Begin(uint64_t now = Now()) {
    if (Get() != State::Armed || now < readyAt_.load(std::memory_order_relaxed)) return false;
    auto expected = State::Armed;
    return state_.compare_exchange_strong(expected, State::Capturing,
        std::memory_order_acq_rel);
  }
  bool Saving() {
    auto expected = State::Capturing;
    return state_.compare_exchange_strong(expected, State::Saving,
        std::memory_order_acq_rel);
  }
  void Complete(bool success) {
    auto expected = State::Saving;
    state_.compare_exchange_strong(expected, success ? State::Saved : State::Failed,
        std::memory_order_acq_rel);
  }
  void Fail() {
    auto state = Get();
    while ((state == State::Capturing || state == State::Saving) &&
        !state_.compare_exchange_weak(state, State::Failed, std::memory_order_acq_rel)) {}
  }
};
inline VisualCaptureRequest visualCaptureRequest;
}
