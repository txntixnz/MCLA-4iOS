# iOS 16 graphics hook binding repair

The first Stage 13 device test on an A15 / iOS 16.0 reached the actual game
entry and produced audio, but stayed on the launcher. Its GPU telemetry showed
33,289 clear calls, zero draw calls, zero resolves and zero swaps. Metal device
and helper setup succeeded. These observations locate this failure before
native title frame submission, rather than proving a shader or drawable error.

The private Stage 9 AOT was generated with the XEO3 manifest. That manifest
spells graphics functions `rex_sub_ADDRESS`; the desktop manifest gives the
same CE addresses names such as `D3DDevice_DrawIndexedVertices`. The native
hooks used the desktop names. Inspection of the delivered Stage 13 Mach-O
confirmed that 11 of 13 graphics entry points retained weak generated wrappers.
Only clear and resource unlock, already spelled by address, had strong native
overrides. Direct AOT calls and both dispatch tables therefore bypassed the
named overrides.

The build now reads the generated declarations and both function tables,
checks all 13 known CE addresses, and creates a private binding header for
the convention actually present. It maps native overrides and their calls to
the original generated bodies together. Both naming conventions are supported;
missing, inconsistent, duplicate and mixed mappings stop configuration.
The private AOT source and compiled archive are unchanged.

Before guest execution, the app checks that all 13 dispatcher entries point
to the linked native overrides. Packaging also inspects the ARM64 Mach-O
symbol table and requires strong definitions for all 13 actual AOT symbols.
The launcher still waits for a completed, presented title frame before hiding.

Validation:

- Synthetic host linker tests pass for direct and table calls in both naming
  conventions, including forwarding to the matching original bodies.
- Negative tests reject missing, inconsistent, duplicate and mixed tables.
- The new binary audit rejects the delivered Stage 13 executable and identifies
  its weak overrides, independently corroborating the device telemetry.
- Full native ARM64/iOS 16 compilation, Apple signing verification and packaging
  passed in private run `38985733583` using source
  `83eaf51c040d76d1f6cb2d7960589e10b5db66d2`. Public launcher and linker tests
  passed in run `38985712519`.
- Independent downloaded-byte inspection confirms 13 strong native hooks, the
  same preview bundle identity, and all 604 previously compiled shader hashes.
  IPA SHA-256:
  `05062040419d9901974d3e925c4ce4ef0bb28006c5dd3df8b1f7dc46eb0299ab`.
- Real device rendering needs a new test; connectivity checks do not establish
  GPU execution, correct imagery, gameplay or frame rate.
