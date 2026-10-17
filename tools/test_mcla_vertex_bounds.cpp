#include "../MCLAApp/runtime/MCLAVertexBounds.h"
#include <cassert>
#include <cstdio>

int main() {
  using namespace mcla::metal;
  VertexIndexRange mesh;
  mesh.Include(100); mesh.Include(103); mesh.Include(101);
  // A valid negative base vertex is common in shared title index buffers.
  assert(VertexFetchFits(64, 0, 16, 16, mesh, -100));
  assert(!VertexFetchFits(63, 0, 16, 16, mesh, -100));
  assert(!VertexFetchFits(64, 0, 16, 16, mesh, -101));
  assert(!VertexFetchFits(64, 0, 16, 16, mesh, 0));
  VertexIndexRange triangle;
  triangle.Include(0); triangle.Include(2);
  assert(VertexFetchFits(60, 4, 20, 16, triangle, 0));
  assert(!VertexFetchFits(59, 4, 20, 16, triangle, 0));
  // A ring allocation's tail must not make a truncated upload slice valid.
  assert(!VertexFetchFits(32, 0, 16, 16, triangle, 0));
  assert(VertexFetchFits(4 * 1024 * 1024, 0, 16, 16, triangle, 0));
  for (uint32_t bad : {0xFFFFu, 0xFFFFFFu, UINT32_MAX}) {
    VertexIndexRange indices; indices.Include(0); indices.Include(bad);
    assert(!VertexFetchFits(64, 0, 16, 16, indices, 0));
  }
  assert(!VertexFetchFits(64, UINT64_MAX, UINT32_MAX, 16, mesh, 0));
  assert(!VertexFetchFits(64, 0, 0, 16, triangle, 0));
  assert(!VertexFetchFits(64, 0, 16, 0, triangle, 0));
  assert(VertexFetchFits(0, 0, 0, 0, {}, INT32_MIN));
  // Exhaustive small cases against a byte-by-byte fetch reference.
  for (uint32_t size=0;size<80;++size)
    for (uint32_t offset=0;offset<10;++offset)
      for (int32_t base=-3;base<=3;++base) {
        bool reference=true;
        for(uint32_t index : {0u,1u,2u}) {
          int64_t address=int64_t(offset)+(int64_t(index)+base)*16;
          reference &= int64_t(index)+base>=0 && address>=0 && address+12<=size;
        }
        assert(VertexFetchFits(size,offset,16,12,triangle,base)==reference);
      }
  std::puts("PASS: vertex payload limits, stream offsets, negative base vertices, malformed indices and overflow.");
}
