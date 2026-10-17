#pragma once
#include <atomic>

namespace mcla::metal {
// Completion callbacks request recovery; only the render worker resets resources
// after draining every flight. Access revocation is terminal for this process.
class GPURecovery {
public:
  enum class State { Ready, Pending, Draining, Revoked, Failed };
private:
  std::atomic<State> state_{State::Ready};
public:
  State Get() const { return state_.load(); }
  bool Terminal() const { auto s=Get(); return s==State::Revoked || s==State::Failed; }
  void Error(bool revoked) {
    if (revoked) { state_.store(State::Revoked); return; }
    auto expected=State::Ready;
    state_.compare_exchange_strong(expected,State::Pending);
  }
  bool Start() {
    auto expected=State::Pending;
    return state_.compare_exchange_strong(expected,State::Draining);
  }
  bool Finish() {
    auto expected=State::Draining;
    return state_.compare_exchange_strong(expected,State::Ready);
  }
  void Fail() {
    auto expected=State::Draining;
    state_.compare_exchange_strong(expected,State::Failed);
  }
};
}
