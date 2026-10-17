# iOS 16 intro crash: shader input lifetime

Stage 14 renders correctly on the user's A15 / iOS 16.0 device. The user
reported good image quality and smooth playback, followed by a crash before
starter-car selection. Logs record 2,137 native presents, millions of draws,
no missing shader identities, and zero GPU command-buffer errors before this
failure. Normal display samples were approximately 30 FPS.

At the crash, new vertex and pixel library loads report `Too many open files`.
The symbolicated crash is SIGABRT in Metal's render-pipeline descriptor
validation, called by `MetalRenderer::Draw`. The separate wakeup report says
`Action taken: none`; it is not the terminating event.

The renderer loaded and retained one file-backed Metal library per shader.
The failure path also treated an entry with shader metadata, but no successfully
loaded library, as ready. A later draw reused that entry, failed to obtain the
required function, and passed a nil function to Metal validation.

The repair reads each offline library into owned bytes and closes its input
descriptor before invoking `newLibraryWithData:error:`. Dispatch owns a copy
for any deferred Metal use. The same loader covers title, FSR and optional
SMAA libraries, with no change to compiled shader bytes. Failed loads remain
retryable, nil functions are not cached, and a missing required shader function
stops the draw before Metal validates a pipeline. Diagnostics are bounded.
No process-wide file limit is increased.

Validation so far:

- The actual byte reader passes 640 retained inputs with a 64-descriptor soft
  limit, verifies every payload, and leaves the descriptor count unchanged.
- Empty, missing, directory and oversized inputs clean up correctly. Forced
  EMFILE is recoverable after releasing one descriptor.
- Apple-host tests pass for the actual Objective-C++ loader with retained
  dispatch data, descriptor closure before Metal, intact bytes after input
  destruction, and recovery from a failed library creation.
- Public validation run `38988119407` passes. Full native ARM64/iOS 16 build,
  signing and packaging pass in private run `38988177873`, source
  `beaa57a8c1c04a48fd430da4219e92959e996718`.
- The downloaded IPA independently passes target, signature structure, all
  604 unchanged shader hashes and all 13 strong native hook checks.
- Real device playback past the previous crash needs a new test.
