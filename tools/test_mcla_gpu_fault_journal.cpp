#include "../MCLAApp/runtime/MCLAGPUFaultJournal.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <thread>
#include <vector>

using mcla::metal::GPUFaultJournal;
int main(int argc, char** argv) {
  assert(argc == 2);
  const std::filesystem::path root = argv[1];
  GPUFaultJournal journal;
  assert(!journal.Record("before_open"));
  assert(GPUFaultJournal::Quote("a\n\"b\\") == "\"a\\u000a\\\"b\\\\\"");
  assert(GPUFaultJournal::Quote("測試", 3) == "\"測\"");
  assert(journal.Open(root / "concurrent", "\"session\":\"first\",\"build\":\"26\",\"pid\":123"));
  std::vector<std::thread> threads;
  for (int t = 0; t < 6; ++t) threads.emplace_back([&,t] {
    for (int n = 0; n < 20; ++n)
      assert(journal.Record("worker", "{\"thread\":" + std::to_string(t) +
          ",\"n\":" + std::to_string(n) + "}"));
  });
  for (auto& thread : threads) thread.join();
  const auto current = root / "concurrent/gpu-faults.jsonl";
  const auto priorSize = std::filesystem::file_size(current);
  assert(!journal.Record("oversize", std::string(GPUFaultJournal::kRecordBytes, 'x')));
  assert(std::filesystem::file_size(current) == priorSize);
  { std::ofstream f(current, std::ios::app); f << "{\"interrupted\":"; }
  GPUFaultJournal reopened;
  assert(reopened.Open(root / "concurrent", "\"session\":\"second\",\"build\":\"26\",\"pid\":124"));
  assert(reopened.Record("recovery_complete", "{\"frame\":694}"));
  GPUFaultJournal rotating;
  assert(rotating.Open(root / "rotation", "\"session\":\"rotation\"", 4096));
  for (int n = 0; n < 100; ++n)
    assert(rotating.Record("bounded", "{\"n\":" + std::to_string(n) +
        ",\"payload\":" + GPUFaultJournal::Quote(std::string(400, 'x')) + "}"));
  for (auto name : {"gpu-faults.jsonl", "gpu-faults.previous.jsonl"})
    assert(std::filesystem::file_size(root / "rotation" / name) <= 4096);
  { std::ofstream(root / "not-a-directory") << 'x'; }
  GPUFaultJournal bad;
  assert(!bad.Open(root / "not-a-directory/logs", "\"session\":\"bad\""));
  std::cout << "PASS: concurrent JSONL records, reopen, interrupted-tail repair, rotation bounds and write errors\n";
}
