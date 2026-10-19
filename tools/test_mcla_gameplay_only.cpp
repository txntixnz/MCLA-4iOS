#include "../MCLAApp/runtime/MCLADiagnostics.h"
#include <cassert>
// The quiet header must erase argument evaluation, not just discard output.
#define REXLOG_INFO(...) (++evaluated)
#define REXLOG_ERROR(...) (++evaluated)
#include "../MCLAApp/runtime/MCLAQuietLogging.h"

static_assert(mcla::kGameplayOnly);
static_assert(!mcla::DiagnosticsEnabled());
int main() {
  mcla::SetDiagnosticsEnabled(true);
  assert(!mcla::DiagnosticsEnabled());
  int evaluated = 0;
  REXLOG_INFO("{}", ++evaluated);
  REXLOG_ERROR("{}", ++evaluated);
  assert(evaluated == 0);
}
