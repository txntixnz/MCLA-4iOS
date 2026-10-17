# Stage 20: captured shaders and vertex payload bounds

Stage 19 device feedback confirms smooth, enjoyable gameplay. The user resolved
the BSP D10's reduced trigger endpoint with an end deadzone in GameSpace. The
latest exported controller snapshot reaches raw 1.0 and mapped 255 on both
triggers with default MCLA ranges. Keep those defaults unless another controller
actually needs calibration.

The complete captured shader interfaces support twelve missing libraries: nine
vertex and three pixel shaders. The private supplement reconstructs containers
from captured title metadata, uses the existing source translator and ABI
patcher, and compiles Metal 3.0 directly for iOS 16.0. AIR reflection checks the
native buffer ABI, attributes, outputs and all four observed shader pairings.
All 604 existing libraries are preserved byte for byte; the combined corpus has
616 libraries including FSR. Captured bytes and compiled game-derived artifacts
remain private. The partial-corpus option is explicit; ordinary complete-source
builds retain their minimum count requirement. IPA verification checks the
complete compiler manifest, library names and exact hashes.

Five GPU event reports share one command-buffer trace identifier. Four report
invalid GPU memory reads and one reports a firmware lockup. These correlate with
the first of two recovered runtime errors. An encoder's initial shader label is
not proof of which draw faulted. The supplied CPU report records sustained use,
takes no termination action and matches the Stage 19 executable UUID.

The renderer previously checked index payload byte ranges without bounding the
resulting vertex fetches. Stage 20 tracks exact converted vertex payload lengths,
including suballocations of the flight upload ring. Prepared pipelines retain
per-stream strides and the last byte read by their attributes. Persistent index
caches retain minimum/maximum indices; every draw validates its current streams,
offsets and signed base vertex before issuing the Metal draw. Valid negative
base vertices remain supported. Malformed draws are rejected with bounded
resource/range diagnostics. Empty draws and overflowing direct/inline ranges
are handled before submission. Existing completion-owned flights, residency and
GPU recovery behavior remain in place.

Portable sanitizer tests compare bounds against exhaustive small byte-reference
cases and cover negative bases, partial final attributes, ring slices, invalid
large indices and overflow. Existing geometry conversion, quad fetch, cache
reuse and scratch tests also pass. Full native build/package status is recorded
with the private delivery. Physical device testing is still needed to confirm
visual correctness and whether this unchecked path caused the observed faults.
