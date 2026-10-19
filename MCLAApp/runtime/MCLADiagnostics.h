#pragma once
#include <atomic>

#ifndef MCLA_GAMEPLAY_ONLY
#define MCLA_GAMEPLAY_ONLY 0
#endif

// Selected by the launcher before runtime startup; immutable during gameplay.
namespace mcla {
inline constexpr bool kGameplayOnly = MCLA_GAMEPLAY_ONLY != 0;
#if MCLA_GAMEPLAY_ONLY
inline constexpr bool DiagnosticsEnabled() noexcept { return false; }
inline void SetDiagnosticsEnabled(bool) noexcept {}
#else
inline std::atomic<bool> diagnosticsEnabled{false};
inline bool DiagnosticsEnabled() noexcept {
    return diagnosticsEnabled.load(std::memory_order_relaxed);
}
inline void SetDiagnosticsEnabled(bool enabled) noexcept {
    diagnosticsEnabled.store(enabled, std::memory_order_relaxed);
}
#endif
}
