# Stage22: second captured shader supplement

The successful Stage21 phone run exposes17 additional shader identities (9VS,
8PS). The captured microcode passes the pinned runtime identity check, and
its declaration/interpolator/output metadata is available. None of these nine
vertex shaders uses a computed fetch index. Compile only these seventeen
sources directly as Metal3.0 for iOS16, then validate native reflection and all
observed vertex/pixel pair interfaces.

The supplement merge now accepts an explicit expected baseline count while
retaining604 as the default for the original workflow. Stage22 requires616,
checks every input library hash and preserves all616 existing library bytes.
Duplicate baseline/result identities are rejected. The combined corpus should
contain633 libraries, including FSR. Parent supplement provenance is retained.
Captured inputs and compiled game-derived output remain private.

Stage21's renderer, GPU recovery, input and touch artwork remain the working
baseline. Build/package and shader audit results are recorded with the private
delivery. Physical gameplay validation of the added shader effects is still
needed; compilation does not prove every game area is visually correct or that
the original GPU hang cause has been eliminated.
