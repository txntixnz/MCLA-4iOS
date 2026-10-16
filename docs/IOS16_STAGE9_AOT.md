# Private AOT Stage 9 — iOS 16 recompilation readiness

The user-supplied Xbox 360 Complete Edition executable was verified against media ID 5940C9DB and successfully processed by the pinned ReXGlue Linux host generator **outside this public repository**. The resulting 60 translated C++ units and associated generated glue (~123 MB) were packaged privately with a SHA-256 inventory; game-derived code is not committed here.

The generated AOT files have **not** been compiled or linked for iOS ARM64. The 20 \`float16_4\` pack warnings from code generation still need an instruction-level audit and device tests. This is **not** a playable IPA.

To check a local source tree containing your privately staged files:

\`\`\`sh
python3 tools/ios16_aot_readiness.py --root . --aot MCLAApp/generated
\`\`\`

AOT sources should be extracted **locally** to \`MCLAApp/generated/\`, never checked into the public repository. The source-only check also identifies the missing native shader pack, vertex metadata, offline Metal libraries and FSR library. This does not audit Metal AIR deployment triples; run \`tools/verify_mcla_metal_targets.py\` against the final app when those files are available.

The current iOS 16 launcher-only build remains valid. **Full runtime compilation is blocked on private native shader and vertex metadata inputs** in addition to possible SDK/ABI compatibility issues. See \`docs/DEVELOPMENT.md\` for shader capture and rebuild sequence.
