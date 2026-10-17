# iOS 16 Stage 18: layout editor and graphics evidence

Stage 17 was reported to run fine, with Start/View obstructing the middle of
the screen and no discoverable touch editor. This update keeps its controller
takeover behavior and existing cyan artwork.

The default Xbox Start and View controls now sit near the bottom, at authored
Y=660 instead of 380. Existing user positions and sizes are preserved.
Driving Controls has a dedicated Touch Layout section with Edit and Reset.
Edit can preview the real controls before starting the title, without changing
the saved touch-enabled preference. It switches to landscape, hides the
launcher, suppresses virtual gameplay input and keeps the Done toolbar visible.
Dragging and resizing use the existing saved-layout implementation. Done saves
and returns to the launcher or game. A physical controller connection or app
interruption still cancels editing and releases virtual input. Disconnect the
controller before opening the touch editor. In game, a three-finger tap opens
the Settings/Edit toolbar.

The production UIKit test exercises the actual settings row, opening before
launch, dragging, saving/reopening, a disabled-touch preview, bottom menu button
positions, and the existing controller takeover/background regressions. Its
runtime and controller inventory are simulated; it is not a device game test.

## Shader gaps

The Stage 16 export's latest session reports seven missing vertex shaders and
one missing pixel shader. All eight exact normalized identities can be recovered
from the existing user-supplied Xenia dump after reversing each little-endian
dword to guest byte order. The same identity normalization matches 509 dump
variants to the 603-library audited title corpus. Filename searches alone miss
these matches because Xenia's filenames use a different hash.

The export contains the capture manifest but excludes its binary shader,
vertex-element, interpolator, declaration and fetch inputs. Bytecode identity
alone does not establish the title's shader interface. Keep the existing 604
validated Metal libraries until those interfaces are available; do not substitute
invented shaders or claim coverage from a name match.

The log exporter now includes only the specifically named binary shader-gap
inputs under native-capture/{shaders,metadata,declarations,fetch}. Each is at
most 64 KiB, with 512 files / 8 MiB total. Full geometry/frame captures and game
or save data are excluded. shader-gap-export.json records limits and counts.
This also exports the already stored gap inputs from earlier sessions, so the
next ordinary diagnostic export can supply the missing interfaces.

## GPU recovery

The latest log records a command buffer discarded during GPU recovery, followed
by continued rendering. It also records serious thermal pressure throughout the
latest session. Neither observation identifies the faulting pass or establishes
that shader gaps caused the recovery.

Diagnostic mode now requests Metal encoder execution status and labels render
and blit passes. Error logs record the frame, domain/code, foreground state at
completion, thermal state and bounded encoder details, with faulted encoders
first. Initial shader IDs in a pass label describe its first binding; they do
not claim to identify a failing draw. Retail mode retains normal command buffers.
Failed command buffers no longer enter successful presentation/GPU timing
averages. This is better attribution and valid telemetry, not a claimed fix for
the underlying device GPU recovery.

Apple API reference: https://developer.apple.com/documentation/metal/mtlcommandbufferencoderinfoerrorkey

The full native build must still audit all 13 strong title graphics hooks and
all 604 unchanged shader libraries before delivery. Stage 18 device testing is
pending.
