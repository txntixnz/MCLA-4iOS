#pragma once
#include <algorithm>
#include <cstdint>

namespace mcla::metal {
// The payload may be a small slice of a much larger flight upload buffer.
// Validate the slice, rather than the allocation's remaining mapped pages.
struct VertexIndexRange {
  uint32_t first = UINT32_MAX, last = 0;
  bool empty = true;
  void Include(uint32_t index) {
    first = std::min(first, index);
    last = std::max(last, index);
    empty = false;
  }
};

inline bool VertexFetchFits(uint64_t payloadBytes, uint64_t streamOffset,
                            uint32_t stride, uint32_t attributeEnd,
                            const VertexIndexRange& indices, int32_t baseVertex) {
  if (indices.empty) return true;
  const int64_t first = int64_t(indices.first) + baseVertex;
  const int64_t last = int64_t(indices.last) + baseVertex;
  if (first < 0 || last < first || !stride || !attributeEnd ||
      streamOffset > payloadBytes || attributeEnd > payloadBytes - streamOffset)
    return false;
  // Division avoids overflow even with malformed 32-bit indices/strides.
  return uint64_t(last) <= (payloadBytes - streamOffset - attributeEnd) / stride;
}
}
