# Stage26 visual frame evidence

Build27 preserves the Stage25 renderer math, shader translator, 633 bundled Metal libraries, recovery, input and saved settings. It adds an explicit diagnostic capture; it does not claim to fix the reported map seam or intermittent textures.

The October18 build26 clip shows a sharply bounded bright patch over the aerial city as the camera zooms toward the car. Its recording creation time is14:57:19UTC (16:57:19 device time); even allowing the7.67second duration, the first rejected shader at16:57:50 is later. The performance captures at17:04:13 and17:04:44 do not cover this transition. The current journal reports build26/PID58020 and contains session/renderer_ready only. Runtime samples through17:05:05 show zero GPU errors; historical errors in earlier log sections are not this session. The cause of the visual patch is unresolved.

## On the iPhone

1. Keep Retail Mode off and enable the FPS graph.
2. While the bright map patch is visible, hold the FPS graph for about0.6seconds. The graph says VISUAL and captures one complete frame after3seconds. Leave the map on screen until VISUAL SAVED appears. A brief pause during this explicit readback is possible.
3. Reopen the launcher and use Export Logs. Send the resulting ZIP. It includes the latest requested visual frame. A later request replaces that diagnostic frame.

For a texture problem elsewhere, capture while the affected surface remains visible. Double-tapping the graph still starts the existing20second performance capture.

## Evidence and limits

A request starts at a submission boundary, captures canonical draw state (including blend/depth/viewport and all26 texture fetch descriptors), guest target format/exposure/topology, deduplicated raw big-endian constant banks and intermediate color-pass images, and reserves room for the final presentation source. It does not alter shader selection, draw ordering, upload caching or resolve behavior. Image blits follow closed encoders; CPU readback and disk writes occur only after successful GPU completion, on a serial utility queue.

Limits:8192 draw records of936bytes,256 constant banks of4096bytes, eight images,16MiB per image and48MiB total image buffers. Intermediates cannot consume the final image's16MiB reserve. Sixty-four constant-bank slots are reserved for small post-processing/UI draws so early world matrices cannot consume the entire budget. A manifest reports truncation, dropped draws, build/profile/PID, frame, GPU, UTC and snapshot draw positions. Snapshot formats are RGBA8 or RGBA16F for2D color targets at least640x360. Higher resolutions may hit limits;720p is preferred for this investigation. This trace attributes passes/states, not a proven faulty shader by itself. GPU faults mark the capture failed rather than publishing its readback as successful.

Normal play performs only an inactive-state check; no visual readbacks or diagnostic disk writes occur until the graph is held. The graph displays capture status. Export only accepts the dedicated manifest/draws/constants/image names, with per-file and aggregate limits; saves and game files remain excluded. `tools/decode_mcla_visual_frame.py` converts exported snapshots to PNG and draws to CSV. HDR previews clamp to0..1 rather than pretending to reproduce the game's tonemapper.

Validation must report native compilation, lifecycle concurrency, ZIP inclusion/exclusion and actual GPU readback separately. The native test returns a clear skip when its Mac has no Metal device; compilation alone is not GPU validation. Phone confirmation is still required.
