// Public, synthetic CPU fixture. No original or generated game code.
#define REX_CONFIG_H_INCLUDED
#define REX_IMAGE_BASE 0x82000000ull
#define REX_IMAGE_SIZE 0x100000ull
#define REX_CODE_BASE 0x82000000ull
#define REX_CODE_SIZE 0x10000ull
#define REX_THUNK_RESERVE_SIZE 0x10000ull
#define REXCRT_HEAP 1
#include <rex/ppc.h>
#include <rex/image_info.h>
#include <rex/logging.h>
#include <rex/chrono/clock.h>
#include <rex/perf/counter.h>
#include <rex/thread/mutex.h>
#include <rex/system/mmio_handler.h>
#include <atomic>
#include <csetjmp>
#include <unordered_map>

REX_FUNC(mcla_public_cpu_probe) {
    // Exercise the actual SIMD and context types used by translated code.
    ctx.r3.u64 = __builtin_rotateleft64(ctx.r4.u64, 11);
    auto value = simde_mm_load_si128(reinterpret_cast<const simde__m128i*>(ctx.v1.u8));
    simde_mm_store_si128(reinterpret_cast<simde__m128i*>(ctx.v2.u8), value);
    ctx.cr6.compare<uint32_t>(ctx.r3.u32, ctx.r4.u32, ctx.xer);
    if (base) {
        uint32_t word;
        __builtin_memcpy(&word, base, sizeof word);
        ctx.r5.u64 = __builtin_bswap32(word);
    }
}
