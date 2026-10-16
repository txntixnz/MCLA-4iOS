# Stage 10 — Xenia shader import and isolated CPU compilation

Target: iPhone 13 Pro Max / A15, iOS 16.0, native ARM64 with offline Metal 3.0.

## Verified private inputs

The original Stage 9 package still contains 60 translated game units and two
generated initialization/registration units. All recorded SHA-256 hashes were
verified. None of those files, the executable, or the shader dump is committed
to this repository.

The Xenia capture contains 562 distinct raw programs: 310 vertex and 252 pixel.
Their dwords are **little endian**, while the native renderer expects the raw
**big-endian guest byte stream**. A direct copy gives incorrect identities.
`tools/ios16_import_xenia_shaders.py` corrects word order, applies the pinned
renderer normalization, preserves every patched fetch variant, and emits a
private manifest. The 562 captures reduce to **545 native identities**:
293 vertex and 252 pixel. All 545 were checked against the pinned C++ identity
implementation, with exact agreement.

Optional comparison against the extracted upstream 1.0.4 app found:

- 509 captured variants match its shader library inventory (492 native identities).
- 53 native identities have no matching library: 51 vertex and two pixel.
- Its descriptor-derived vertex map covers 101 of the 293 captured vertex
  identities; every observed active fetch in those covered variants has an entry.

This comparison does **not** make the upstream iOS 18 libraries usable on iOS 16.
No libraries were retargeted or substituted. It also does not establish total
game coverage: the capture is only the paths exercised by its creator.

## Packing warning audit

The 20 Stage 9 `float16_4` diagnostics were **warnings about an unexpected operand
combination**, not 20 missing translations. Every warning is mask=3, shift=0,
with distinct source/destination vectors. The emitted statements exist and use
valid halfword indices. For this combination, the pinned Xenia permute table
preserves the high two guest words and writes the low two words.

`tools/ios16_aot_pack_audit.py` verifies the Stage 9 hashes, locates every warning
site, compiles the actual emitted bodies privately, and compares boundary cases
and deterministic random inputs against an independent integer half-conversion
and lane-placement reference. **327,680 executions passed with UBSan enabled.**
The generated source was not changed. This result does not test other pack
combinations, native ARM64 execution, or gameplay.

All **62 private generated C++ files** also compiled to native Linux x86-64
objects using official LLVM Clang 18.1.8 and the pinned SDK headers. This is a
complete host compilation check, without linking or game execution. It is not
an Apple ARM64 game build.

## Shader compiler

`sh tools/build_mcla_shader_translator.sh` builds the existing ALU-order-aware
source translator with Clang and the pinned fmt headers. Unused dependencies on
DXC, smol-v, xxHash and zstd were removed from its precompiled header. Translation
to text itself requires no GPU. Compiling Metal output still requires Xcode.

The translator built successfully on Linux with official LLVM Clang 18.1.8.
Complete title shader conversion is still blocked on authoritative interpolator
descriptors, the remaining vertex-element tables, and actual loop/integer
constant definitions for any shaders that use loops. No placeholder tables or
fabricated loop values were promoted to production inputs.

## CPU compilation without shader resources

`MCLAApp/tools/aot_compile` configures the real kernel/runtime foundation and an
isolated static CPU target. Shader packs and application resources do not enter
this target, so their absence cannot stop the CPU compilation check.

For a local Mac with the pinned dependencies and private AOT already staged:

```sh
cmake -S MCLAApp/tools/aot_compile -B out/ios16-private-aot -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_SYSROOT=iphoneos -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=16.0 \
  -DMCLA_PRIVATE_GENERATED_DIR=/absolute/private/generated
cmake --build out/ios16-private-aot --target MCLACPUCompilation --parallel 4
```

The public `ios16-cpu-foundation.yml` workflow explicitly sets
`MCLA_AOT_PROBE_ONLY=ON`: it compiles a synthetic fixture against the real
foundation, with actual ARM64/iOS 16 settings. It receives no private game code.
A green result must not be described as compilation of the 60 game units.

The first CPU-foundation run compiled all 349 build actions and produced an
ARM64 static library. Its last verification step used an incorrect `lipo`
argument order; the command was corrected and the gate also inspects the Mach-O
object's iOS platform and minimum deployment version.

For hosted compilation of the actual private inputs, use an access-controlled
private repository or a private local build machine. Public workflow inputs,
logs and artifacts must not be used to distribute the generated game code.
