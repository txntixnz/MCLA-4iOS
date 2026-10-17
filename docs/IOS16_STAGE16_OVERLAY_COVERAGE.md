# iOS 16 full-screen overlays

The Stage 15 user reports smooth playback without the intro crash. The supplied
81-second iPhone clip proceeds through starter-car selection and into driving.
The new visual issue is a centered black fade/loading rectangle with the 3D
scene visible on either side. On a 960x444 video frame the rectangle spans about
x=86..874: a 16:9 authored frame inside the wider device image, rather than 4:3.
The device log records a 1560x720 native scene and zero GPU command-buffer errors.

The renderer intentionally keeps authored HUD artwork in a centered 16:9 frame
while the scene uses device aspect. Its previous full-screen exception only
accepted Float3 positions, at most six input vertices, and positions very close
to the four clip corners. Other supported position formats, overscanned screen
triangles and backgrounds inside mixed UI batches could therefore retain the
centered frame. The clip does not contain a geometry trace establishing which
of these limitations affected each transition.

Stage 16 changes the coverage decision for the already audited HUD vertex
program F8B6972A1D56B354 on the 1280x720 logical scene target:

- Decode big-endian Float2, Float3 and Float4 positions using the shader's actual
  c8..c11 transform. The original input w is unused by that program.
- Require connected convex triangle coverage of the authored screen, including
  overscan and the half-pixel convention. Screen-sized bounds alone cannot
  qualify a half-screen triangle, disconnected triangles or a crossed quad.
- Recognize independent triangle, quad and rectangle-list backgrounds within
  batches up to 4,096 inputs. Preserve their order, source ranges, indexed base
  vertex and expanded index spans. Small UI pieces keep their authored frame.
- Apply the full attachment viewport and matching scissor to qualified
  backgrounds. A clipped child viewport or scissor does not qualify.
- Preserve the previous driving-HUD experiment's Float3 and independent
  triangle/quad movement policy. The camera and scene-size hooks are unchanged.

Four-vertex strips/fans and a single oversized screen triangle are supported as
whole draws. Larger strips/fans, unsupported formats, invalid inputs and batches
over the limit retain the conservative whole-draw policy. Rectangle-list screen
classification requires an affine (constant-w) projection. The original
FullScreenFades experiment switch still gates the behavior. At most 12 ordinary
non-retail diagnostic lines report the chosen overlay path.

Portable regression coverage includes all three input formats, actual authored
screen projection, input bounds/invalid values, triangle topology and overscan,
crossed/disconnected/partial rejection, mixed-batch ordering, the 4,096-input
limit, expanded index ranges, child scissor rejection, native phone scene extent,
and existing HUD movement and presentation tests. Linux AddressSanitizer and
UBSan pass (leak detection is unavailable in the executor). Apple-host checks
and the full ARM64/iOS 16 application build are required before delivery.

This is a renderer coverage repair, not a device-verified claim that every fade
path is fixed. Replay the intro/loading transitions on the phone and confirm
that black covers the side strips while text and the driving HUD stay aligned.
The Stage 15 shader lifetime repair remains part of the build.
