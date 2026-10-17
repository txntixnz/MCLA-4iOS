# Stage24: prompt touch D-pad release

The layout editor attached an enabled two-tap removal gesture to every movable
control during normal gameplay. Its default delayed-ended behavior could hold
a button down after the finger lifted, allowing menu key repeat to look like
two presses. The handler's editing check did not prevent UIKit from analyzing
the gesture or delaying release.

Removal gestures now start disabled, enable only while editing, and disable
again on Done or a controller/background interruption. Their ended events do
not wait for another tap. The three-finger toolbar gesture also leaves ended
events undelayed. Normal held D-pad input and rapid intentional taps retain
their original game-side handling; no debounce timer or repeat suppression is
added. The gamepad state/keystroke bridge is unchanged.

The UIKit integration regression checks all four directional button actions,
held state, cancellation, distinct rapid taps, non-delaying ancestor gestures,
and editor/Done/controller-takeover gesture lifecycle. It runs the shipping
view controller with synthetic input recording in the iOS simulator. It does
not replay physical touchscreen events or prove the user's perceived issue
resolved; that requires phone feedback.

The renderer, automatic shader compiler/cache revision, GPU recovery, control
artwork, saved positions and physical-controller calibration are unchanged.
All633 bundled Metal libraries remain the build24 baseline. No prewarming or
additional shader control-flow support is part of this change.
