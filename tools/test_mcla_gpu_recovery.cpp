#include "../MCLAApp/runtime/MCLAGPURecovery.h"
#include <cassert>
#include <thread>
#include <cstdio>

int main() {
  using mcla::metal::GPURecovery;
  GPURecovery state;
  assert(state.Get()==GPURecovery::State::Ready && !state.Start());
  state.Error(false); state.Error(false);
  assert(state.Start() && !state.Start());
  state.Error(false); // Other flight callbacks coalesce during the drain.
  assert(state.Finish() && state.Get()==GPURecovery::State::Ready);
  // A denial from any flight must win over successful worker cleanup.
  for(int i=0;i<1000;++i) {
    GPURecovery race; race.Error(false); assert(race.Start());
    std::thread callback([&]{race.Error(true);});
    race.Finish(); callback.join();
    assert(race.Get()==GPURecovery::State::Revoked && race.Terminal());
    race.Error(false); assert(!race.Start() && !race.Finish());
  }
  state.Error(false); assert(state.Start()); state.Fail();
  assert(state.Terminal() && !state.Finish());
  state.Error(false); assert(state.Get()==GPURecovery::State::Failed);
  std::puts("PASS: recovery drain coalescing, repeated errors, timeout failure and concurrent access revocation.");
}
