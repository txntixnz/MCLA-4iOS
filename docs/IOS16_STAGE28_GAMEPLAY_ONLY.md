# Stage28: Gameplay Edition (build29)

The user confirmed build28's map-lighting correction works perfectly and
requested an IPA with all diagnostics disabled, beyond Retail Mode.

Configure the native Release build with `-DMCLA_GAMEPLAY_ONLY=ON`.
`DiagnosticsEnabled()` is then a compile-time false constant; saved preferences
and environment overrides cannot enable it. MCLA log macros erase arguments.
ReX diagnostics remain disabled and its logger is never initialized.

This profile removes Metal encoder execution-status instrumentation, command
buffer debug labels, the persistent GPU fault/recovery journal, detailed
completion telemetry, per-draw hook counters/checksums, frame timing capture,
GPU counters, visual readback requests, shader evidence dumps and the launcher
diagnostic render pipelines. The FPS button and log exporter are hidden, the
diagnostics setting is locked off, and launcher status polling stops once the
first gameplay frames are visible. Controller session diagnostic sampling and
persistence are disabled; saved trigger calibration still applies.

Automatic shader preparation and its functional shader cache remain available.
Missing-program inputs may be decoded for compilation, but their diagnostic
corpus is not submitted to the writer. Completion-owned frame slots, error
recovery, resource validation, application lifecycle handling and frame pacing
remain active because gameplay depends on them.

The confirmed build28 Clear implementation is unchanged. Minimum iOS16,
bundle/container identity, game data, controls and graphical settings remain.
No FPS gain is promised without an on-device comparison.
