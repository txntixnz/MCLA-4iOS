# Stage23: on-device shader generation

The app keeps the entire audited Stage22 corpus (633 Metal libraries) as its
first choice. Newly encountered programs are copied with their live descriptor
metadata, translated by the existing XenosRecomp branch, and compiled by Metal
on a single utility-priority queue. Draw submission never waits for compilation.
Programs become available on subsequent draws after successful entry-point and
stage validation. The shader info objects and library ownership remain stable.

The source generator shares the container builder, constant/vertex-ID patches,
common source and gamma helpers with the offline pipeline. Private replay checks
compare all17 Stage22 additions byte for byte against their audited MSL. Native
cache tests withhold these17 from the test corpus and exercise real Metal cold
compilation, duplicate coalescing, warm cache reuse, corruption recovery and
persistent GPU-error suspension. App builds retain all633 bundled libraries.

Versioned, checksummed source/interface caches live under Library/Caches/MCLA/
AutomaticShaders. Metal manages its compiled GPU cache. Persistent custom entries
are limited to128 per compiler revision and512KiB of source per shader. Cache
corruption regenerates from the captured program; failed compilation cannot
publish an entry. The app needs no shader server, automatic upload, or network.

Automatic Shaders defaults on in Graphics > Experimental and applies after
reopening the app. A transient Preparing shaders indicator shows queued work.
New effects can be absent until compilation finishes. Existing controls, layouts,
resolution/settings, bundle identity, three-flight GPU ownership and Stage21
recovery logic are retained.

New loops, calls/jumps, predicate CF, computed vertex-fetch programs, invalid
descriptors, out-of-range texture slots and malformed microcode are rejected for
offline review; the on-device path does not guess their ABI. Missing captures
remain bounded to64 pairs. All new programs in a faulted GPU frame are suspended
for that compiler revision, conservatively, without asserting they caused the
fault. Existing bundled programs are never suspended by this mechanism.

Compilation is not physical gameplay validation. Device behavior, first-encounter
latency and visuals still need the user's phone test. This feature does not prove
the original GPU fault cause is fixed or that every future shader is supported.
