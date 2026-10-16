// Compatibility for hooks still named by the pinned XEO3 codegen manifest.
#include <rex/ppc/context.h>

// The pinned desktop hooks explicitly removed the fixed half-rate SWF patch:
// it changes playback incorrectly outside an exact 60 FPS presentation rate.
// Returning false keeps the original guest advance block and its epilogue.
bool Hook_IntroHalfRate() { return false; }

// XEO3's remaining invite-gate sites are documented as read-only diagnostics.
// Keep guest gate results/identity pointers unchanged, matching the other
// disabled online probes in the pinned XEO3 implementation.
void Hook_InviteGateProp3(rex::ppc::Register&) {}
void Hook_InviteGateIdentity(rex::ppc::Register&, rex::ppc::Register&) {}
