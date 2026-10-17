# Stage 21: controlled GPU recovery

The Stage20 device run has no missing shaders or vertex-range rejections. Three
firmware lockups occur at frames693,1407,1985. After the third, Metal revokes
GPU access (code4):267 subsequent submissions are ignored, completed FPS falls
to zero, and audio continues. This reproduces the reported graphics-only stop.
The three IPS reports have distinct trace IDs. They report firmware lockups,
not a new explicit page-fault address. The original hang cause remains unknown.

Completion callbacks now request recovery instead of letting the next frame
reuse the failed render/resolve chain. At a render-worker command boundary,
any unsubmitted successor is discarded and every flight is drained with one
shared two-second deadline. Only after all flights finish are mutable render
surfaces, resolved textures, cached bindings and upload-ring resources reset;
a new command queue is created. Guest bindings, immutable geometry/source
textures, pipelines, all616 shader libraries and control settings are retained.
Recovery is never performed from Target/Attach or a completion callback, so it
cannot invalidate resource-map references during a draw. Flight ownership is
released exactly once for either commit completion or an unsubmitted discard.

Access revocation wins over concurrent recovery completion and is terminal for
this process. Further GPU submissions stop, repeated failure logging is bounded,
and a one-time message explains that the app must be closed and reopened. This
is not an attempt to bypass iOS GPU access revocation. Healthy rendering has no
additional GPU waits or shader instrumentation.

Failure diagnostics now include every shader used by the failing command
buffer, plus up to eight distinct pairs and the last pair in each guest pass.
These identify the programs involved more precisely than an initial pass label;
they still do not prove the exact faulting draw. Shader-loop inventory work
found18 cyclic AIR programs, but none is established as the cause and no shader
math is changed speculatively.

A portable sanitizer test covers coalesced failures, drain state, timeout failure
and1000 concurrent access-revocation/recovery races. Full native build status
is recorded in the private delivery. Phone testing must establish recovery
behavior and help isolate any recurring initial hang. Stage21 is a recovery and
attribution improvement; do not describe it as a proven original-hang fix.
