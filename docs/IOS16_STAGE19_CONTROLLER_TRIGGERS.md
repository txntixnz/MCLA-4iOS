# Stage 19: analog controller trigger calibration

Device feedback reports reduced RT throttle with face-button throttle working.
The pinned iOS driver already maps Apple's documented 0..1 pressure to unsigned
0..255; the guest state uses one byte per trigger and the adapter merges by max.
No observed raw trigger samples establish the cause yet. Do not call a fixed
multiplier or signed-byte conversion a proven root-cause repair.

Driving Controls > Physical Controller > Test and calibrate triggers shows live
iOS pressure and the mapped Xbox value. Explicit calibration records released
positions and the largest full squeeze of each trigger independently. Validated
endpoints remap linearly, preserving the entire analog range. Both triggers must
show at least 0.05 travel before Save. No peak learning happens during gameplay,
and defaults remain 0..1. Profiles persist by vendor, product category and profile
class; identical controller types share the profile. Reset restores defaults.

The dependency patch calls the app converter with the actual native controller
slot object, before complete-sample packet tracking and touch merging. Setup
holds physical pedals at zero, cancels unfinished calibration on disconnect or
backgrounding, and requires release after leaving before pedals can drive again.
The input hot path caches profile data under a mutex and performs no file writes.
Log export includes current-process raw min/max, mapped maxima and saved ranges.
Resigning active saves a bounded snapshot so this evidence survives reopening
the app to export logs. The snapshot has its own date and build identifier.

Validation covers all 256 levels for normal, half and offset ranges, bad endpoints
and nonfinite samples. The production UIKit test uses real GameController
snapshots and the production converter to cover independently reduced LT/RT,
rejected partial saves, persistence on a new controller instance, neutral setup,
release rearming, cancellation and reset. These are synthetic input tests;
physical-controller behavior still needs the user's test.

The supplied diagnostic ZIP identifies build 17, not build 18. Its latest session
contains two GPU hangs followed by continued rendering, and eight missing shader
identities. It has no binary shader interfaces or Stage 18 encoder attribution.
The Stage 18 bounded shader export and Metal attribution remain in this build;
this change does not claim to resolve shader gaps or GPU recovery.

Apple pressure-value contract:
https://developer.apple.com/documentation/gamecontroller/gccontrollerbuttoninput/value
