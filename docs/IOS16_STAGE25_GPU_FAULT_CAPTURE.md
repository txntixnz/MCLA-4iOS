# Stage25 / build26 — persistent GPU fault capture

Stage24 touch D-pad behavior is confirmed on the user's iPhone13 Pro Max/iOS16.0. Stage25 retains that implementation and adds GPU evidence. It is not a proven repair of the recurring GPU hang/page fault.

The regular ReX log is disabled in Retail Mode. A separate journal now records renderer sessions, readiness, GPU failures and recovery begin/complete/failure/terminal outcomes, independently of that switch. Every row contains build/profile, session UUID, process ID, UTC and monotonic timestamps. Records are flushed to disk when those rare events occur; healthy frames and individual draws do not write to the journal.

The app retains `logs/gpu-faults.jsonl` and `logs/gpu-faults.previous.jsonl`, each capped at128KiB, with a16KiB cap per record. Rotation keeps recent history across reopening; incomplete trailing records are removed before appending. Export Logs already includes the logs directory and JSONL files. Error storms retain the first16 errors and every120th later error; the error counter exposes that sampling. Encoder details are limited to12 non-completed encoders, faulted first, with bounded labels/signposts and24 automatic-shader names. Omission counts are explicit.

Command buffers request Metal encoder execution status in Retail Mode as well. Apple documents slight possible CPU overhead for this option; this build needs device performance feedback. Pass labels retain initial and final shader pairs and draw counts. Non-guest helper passes no longer inherit stale guest shader identities. Detailed full-frame shader inventories remain in the existing opt-in logger. Presence in a failed pass is not proof of a causal shader or draw.

The portable UBSan regression checks concurrent writes, JSON parsing, interrupted-tail repair, rotation, reopening and errors. The native regression sends a synthetic Metal NSError through the shipping serialization function, reopens the journal and exports it through the actual archive implementation. It validates faulted-encoder priority, bounds, Unicode/escaping and session identity. It does not inject a physical GPU fault or demonstrate an on-device recovery.

Install as an update in TrollStore and keep app data. Play normally with the current controls and export logs after the next graphics problem. Retail Mode can stay on. Match journal events to system IPS timestamps, process IDs and frames. Missing callbacks after abrupt process death can still leave no GPU-error record; session records identify the process but do not prove a particular recovery completed.

No title shader, compiler/cache policy, resource upload, GPU recovery state transition or rendering math is changed. Existing633 bundled libraries and controller/layout data remain the baseline.

Primary API reference: https://developer.apple.com/documentation/metal/mtlcommandbufferdescriptor/erroroptions
