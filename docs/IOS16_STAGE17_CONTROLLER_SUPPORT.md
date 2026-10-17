# iOS 16 controller input and Xbox touch layout

The user is testing Stage 16's wide-screen overlay changes. Stage 15 is the
last device-confirmed crash-free baseline. Stage 17 adds controller/touch
handoff and a conventional Xbox arrangement while retaining Stage 16 rendering.

The existing Apple GameController driver is already linked into the native
runtime. It maps the extended profile to Xbox 360 ABXY, D-pad, both sticks and
stick clicks, triggers, shoulders, Start and Back. The title adapter now tracks
the complete physical sample when assigning input packets, so analog-only
steering, camera or trigger changes also advance the packet. Foreground state
gates physical input. User zero can use the next connected platform slot if
its original controller disconnects; capabilities and vibration use the same
fallback policy.

UIKit observes controller connection and disconnection throughout gameplay,
independently of the launcher navigation timer. A connected extended gamepad
hides both touch sticks, pedals, action buttons, the palette and sliding input
router. Taking over clears held touch buttons, triggers, tilt, stick tracking
and queued old press events. Late touch-down events cannot reactivate input.
Disconnecting restores the selected touch layout only if touch controls are
enabled and the app is active. Connecting during layout editing exits editing.
The manual three-finger toolbar still gives access to app settings; its gamepad
buttons, PAD and EDIT remain hidden while a controller is connected.

The new default Xbox touch layout has the conventional A-bottom/B-right/X-left/
Y-top diamond, offset left and right sticks, a left D-pad, LT/RT and LB/RB across
the top, View/Back and Menu/Start in the center, and L3/R3. It uses the existing
cyan double rims, translucent fills, cached pressed/disabled artwork and stick
assets. Glyphs identify the Xbox inputs. A is a separate handbrake input, with
throttle on RT; the older combined driving zones remain in the optional legacy
layout. The Xbox mode has its own saved positions/sizes and deployed-button
list. Existing legacy layouts are preserved. EDIT can customize this mode,
and Driving Controls offers an Xbox layout switch.

Portable checks exercise stable and changing digital/analog packets, neutral
release, reconnect, touch ownership and nonoverlapping authored hit rectangles
at representative phone/tablet sizes. The simulator harness links the shipping
UIKit controller/artwork to explicit runtime/input-recording stubs and overrides
only controller inventory. It tests preconnected and hot-plug behavior, held
input release, late-event rejection, editing/background safety, disabled-touch
preferences, actual constraints/artwork and saved-layout isolation. Its image
shows actual UIKit controls on a blank preview surface, not game playback.

Apple-host checks, simulator execution, the full ARM64/iOS 16 runtime build,
signing and independent IPA audits are required before delivery. Physical
controller, wireless latency and rumble behavior require the user's device test.
