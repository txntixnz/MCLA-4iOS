# iOS 16 private native runtime integration

The actual Stage 9 title code passed ARM64/iOS 16 compilation. Its 62 Mach-O
objects were independently inspected for CPU type, device platform and minimum
iOS version. This is distinct from the public synthetic CPU foundation probe.
The verified archive SHA-256 is
`5d872c7ab9c68ebe3c46dc0e3dc70f9abad2e03e9cf67c393c3ff8045d483b40`.

## Restricted shader compatibility experiment

All **604 existing libraries**, containing **605 AIR modules**, were rebuilt
through Apple's iPhoneOS Metal compiler/linker with iOS 16 deployment flags:
603 title libraries (308 vertex, 295 pixel) and the two-function FSR library.
The compiler accepted every module, the resulting libraries all advertise iOS
16.0, and the expanded stage/reflection/function-constant metadata matched
before and after rebuilding. No existing metallib container was relabeled.

The source comparison compiles one public synthetic program directly as
Metal 3.1/iOS 18 and Metal 3.0/iOS 16. Applying the restricted IR adaptation
produces text identical to the direct iOS 16 baseline, excluding the ModuleID
comment. Differences are the target triple, AIR/language metadata, and
removable `noundef` optimization assertions. This is evidence for that program,
**not a general proof of AIR backward compatibility**.

`ios16_air_compat.py` refuses unexpected data layouts, targets, AIR/language
versions, shader stages, named AIR metadata and external intrinsics. It
requires the direct synthetic comparison proof and explicit experimental opt-in.
It never modifies instructions, numerical values, floating-point flags,
resource bindings or reflected interfaces. Apple compiles and links new files;
output targets and reflection are checked again.

Device pipeline creation, rendering, gameplay and performance remain untested.
The resource-recovery tool emits deliberately conservative masks (26 texture
slots and 256 constant registers per shader), which can reduce performance.
Vertex semantics, locations, components, numeric types and color output slots
come from the original compiler reflection; unknown interfaces are rejected.

This path does not recover original Xenos interpolator descriptors or loop
constants. The user's captured corpus still has **53 identities** absent from
the reference title library inventory. Full shader coverage is not claimed.
The required older SPIR-V fallback pack retains its original provisional flags;
it is not promoted into the direct Metal execution path.

## Full private build

`tools/templates/ios16-private-shaders.yml` rebuilds and retains shader inputs
only in a private repository. `tools/templates/ios16-private-runtime.yml` then
reuses the previously verified CPU and shader artifacts, checks their hashes,
restores the renderer interface header, and builds the real runtime, native
Metal renderer, XMA audio and input path. The optional imported AOT archive is
independently checked again by CMake; normal source compilation is retained.

The candidate reuses the isolated iOS 16 preview bundle identifier to retain
access to the ISO already placed in that app's Documents folder. Local input
identity verification is shared by the launcher and runtime. A verified ISO is
passed to the foundation's existing **read-only** DiscImageDevice, preserving
the same guest mount order and `game:`, `d:` and `t:` links. Extracted game
folders remain supported. Executable hashing is cached during UI refresh and
repeated immediately before launch; no ISO copying or extraction is required.

Every artifact containing generated game code, shader code or compiled game
binaries must stay private. Public workflows use synthetic source only.

The first complete native compile reached the final linker, which identified
three stale XEO3 hook names still present in its generated code. Compatibility
functions preserve the original guest path: the retired half-rate intro patch
returns false, and the two documented read-only invite probes leave registers
unchanged. No generated game body or CPU archive is modified.

The private test profile enables diagnostics once for its first launch; later
user settings persist. This allows the existing bounded missing-shader capture
path to collect real descriptor metadata if the unrepresented cases are hit.
