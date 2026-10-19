# Gameplay Edition fix1 (build30)

Build29 was rejected by the user: audio runs, but no picture. Disabling the
vertex-binding skip counter inserted an unbraced `if constexpr` beneath the
binding-cache `if`. Its `else` bound to the inner condition, so the first and
changed vertex buffers were never bound. The earlier clear-only GPU tests did
not exercise vertex submission and missed this regression.

Add explicit braces around the cache-hit branch. The Metal buffer binding and
cache update now run on every cache miss, independently of diagnostics. Treat
`-Wdangling-else` as a build error to prevent the same mistake.

`tools/test_mcla_vertex_binding.py` extracts the actual production branch. It
checks first binding, identical-binding reuse, changed offsets and changed
buffers with gameplay-only both disabled and enabled. On macOS the unmodified
Objective-C++ branch also submits a triangle to Metal and verifies its pixels.
The shipped build29 branch must fail this regression before the corrected one
passes. Existing gameplay-policy, clear and depth/stencil checks remain.

All diagnostics remain disabled. The confirmed build28 lighting fix, shaders,
controls, graphics settings and container identity remain unchanged. Build and
GPU validation do not substitute for the next phone test.
