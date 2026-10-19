#pragma once
#include "MCLADiagnostics.h"
#if MCLA_GAMEPLAY_ONLY
#undef REXLOG_TRACE
#undef REXLOG_DEBUG
#undef REXLOG_INFO
#undef REXLOG_WARN
#undef REXLOG_ERROR
#undef REXLOG_CRITICAL
#define REXLOG_TRACE(...) ((void)0)
#define REXLOG_DEBUG(...) ((void)0)
#define REXLOG_INFO(...) ((void)0)
#define REXLOG_WARN(...) ((void)0)
#define REXLOG_ERROR(...) ((void)0)
#define REXLOG_CRITICAL(...) ((void)0)
#endif
