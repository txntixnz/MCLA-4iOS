#include "../MCLAApp/runtime/MCLAVisualCaptureRequest.h"
#include <cassert>
#include <thread>
#include <vector>
#include <cstdio>
using Request=mcla::metal::VisualCaptureRequest;
int main() {
  Request r;
  assert(r.Get()==Request::State::Idle && !r.Begin(0));
  assert(r.Request(100));
  assert(!r.Request(101) && !r.Begin(3000000099ull));
  assert(r.Begin(3000000100ull) && !r.Begin(UINT64_MAX));
  assert(!r.Request(0) && r.Saving() && !r.Saving());
  assert(!r.Request(0));r.Complete(true);assert(r.Get()==Request::State::Saved);
  assert(r.Request(0) && r.Begin(3000000000ull));r.Fail();
  assert(r.Get()==Request::State::Failed);r.Complete(true);
  assert(r.Get()==Request::State::Failed);
  for (int round=0;round<100;++round) {
    Request concurrent;std::atomic<int> accepted=0, begun=0;
    std::vector<std::thread> workers;
    for(int i=0;i<8;++i)workers.emplace_back([&]{accepted+=concurrent.Request(0);});
    for(auto& worker:workers)worker.join();workers.clear();
    assert(accepted==1);
    for(int i=0;i<8;++i)workers.emplace_back([&]{begun+=concurrent.Begin(3000000000ull);});
    for(auto& worker:workers)worker.join();
    assert(begun==1 && concurrent.Saving());concurrent.Complete(false);
    assert(concurrent.Get()==Request::State::Failed);
  }
  std::puts("PASS: capture deadline, busy exclusion, completion/failure, concurrent single admission");
}
