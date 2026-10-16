# iOS 16.0 / A15 native recompilation experiment

**Status: untested source backport, no playable IPA.**

Goal: port the Xbox 360 Complete Edition static-recompilation build to native ARM64/Metal on iPhone 13 Pro Max running iOS 16.0 and install it through TrollStore. No Xbox 360 emulator is used at runtime, but title-specific compatibility services remain.

## What this branch contains

- Opt-in `ios16-device-release` CMake preset; upstream `ios-device-release` remains iOS 18.
- Xcode deployment target matches the preset instead of being hardcoded to 18.0.
- `MCLA_IOS_MIN=16.0` selects Metal 3.0 and cache stamps isolated from iOS 18 builds. Default remains iOS 18 / Metal 3.1.
- An Apple-hosted CI smoke test compiles a tiny *real* Metal library with deployment target 16.0 and validates its embedded target metadata.
- A preflight tool that reports missing game-derived AOT/shader inputs; it does not pretend a clean checkout builds the game.

## Run initial compiler test

In GitHub Actions, enable Actions if prompted, then run **MCLA iOS 16 - Metal 3.0 smoke test** on branch `ios16-native-backport`. A passing green check demonstrates only the SDK/compiler/deployment-target policy—not game launch or renderer compatibility.

For local testing on macOS with Xcode:

```sh
MCLA_IOS_MIN=16.0 python3 tools/test_mcla_metal_targets.py
python3 tools/ios16_preflight.py
```

## Full title build prerequisites (not bundled)

The upstream source snapshot is **not** a clean disc-to-IPA pipeline. It excludes generated AOT code, title shader sources and offline shader caches. Those must be generated from the user's own compatible Xbox 360 Complete Edition game copy without committing or distributing game data.

Once the inputs exist on a Mac:

```sh
sh tools/apply_dependency_patches.sh
MCLA_IOS_MIN=16.0 python3 tools/build_mcla_metal_shaders.py
MCLA_IOS_MIN=16.0 python3 tools/build_mcla_fsr.py
MCLA_CMAKE="$(command -v cmake)" sh tools/generate_xcode.sh ios16-device YOUR_APPLE_TEAM_ID
cmake --build out/build/ios16-device-release --config Release --target MCLAApp
python3 tools/ios16_preflight.py --app out/build/ios16-device-release/Release-iphoneos/MCLAApp.app
```

Some MSL3.1-only shader constructs, runtime API availability checks or graphics features may require more work. Existing iOS 18 `.metallib` assets cannot be reused unchanged. The pinned tools may also rely on private locally-generated intermediate shader data. Do not simply change Info.plist or re-sign the iOS 18 IPA. No performance claims are made for A15.

Based on upstream [DEVELOPMENT.md](../docs/DEVELOPMENT.md) and [TECHNICAL_NOTES.md](../docs/TECHNICAL_NOTES.md). Preserve GPL-3.0 licensing and credits. Game data remains private.

## Second-stage launcher-only compilation probe

The `ios16-launcher-only` CMake preset sets `MCLA_RUNTIME_ENABLED=OFF`. It deliberately excludes game-derived vertex/shader resources so GitHub-hosted Xcode can compile the **UIKit/Metal shell** without a game dump. This build **cannot launch Midnight Club**. It exists to expose build errors and unsupported iOS APIs before a full port is attempted.

The dedicated Actions workflow `MCLA iOS 16 - launcher compilation` configures Xcode with code signing disabled, attempts the device ARM64 build, and checks the generated app's minimum OS. Any failure is a diagnostic; it is not evidence that the full game is impossible.

## Optional diagnostic IPA

A successful launcher-only workflow uploads `MCLA-iOS16-LAUNCHER-ONLY-NO-GAME.ipa` as an Actions artifact. It is ad-hoc signed for testing on a compatible sideload/TrollStore setup. It has a distinct bundle identifier `com.txntixnz.mcla.ios16.preview`, so it does not overwrite a full-game MCLA installation. The UI may still display the default name MCLA. This is strictly a **non-playable native iOS 16 shell**; do not copy game files into it expecting races to work. The value of a device test is checking whether the launcher and basic Metal presenter start on an A15 phone.

## On-device Metal test report

The iOS 16 preview launcher shows `METAL READY` after the diagnostic shader pipelines compile and depth state initializes, otherwise `METAL CHECK`. A successful report confirms native test-pipeline setup, not the game’s title renderer. Export Logs now includes pipeline readiness, drawable dimensions, submitted/completed frames, and setup errors. Keep exported logs and game files out of the public repository.

## Verify a personal Xbox 360 game copy on-device (Stage 3)

In the native iOS 16 diagnostic launcher, **hold Logs / Verify XEX** to open the Files picker, then choose a user-owned **extracted `default.xex`**. This is a read-only, streamed SHA-256 verification against the two executable profiles in the public `GameDataManifest.json`. The game file is never uploaded to GitHub or added to the IPA. An ISO/ZIP must be extracted first. The result confirms which Complete Edition code version is compatible with the recompilation baseline; it does **not** provide missing AOT code, title shaders, or gameplay. Do not put private game files in the repository.

## Stage 4 — separate visible game-verification button

In the iOS16 diagnostic launcher, the bottom full-width **Verify Game** button is a normal tap target (and selectable using the controller). It opens the Files picker for the user's own extracted `default.xex`; **Export Logs** remains separate. No gesture or hidden button is necessary. This preview still has no game runtime or copyrighted game assets.

## Stage 5 — in-place ISO verification

The iOS 16 preview Verify Game picker now accepts file items, including `.iso`. The read-only XDVDFS reader uses the same disc partition candidates and binary-tree layout as the existing Mac game preparer. It checks five required root files and hashes only the embedded `default.xex` against the release manifest. ISO files do not need to be extracted or uploaded. This only verifies the executable; the preview is not a playable recompilation. Raw Xbox 360 ISO required; PS3 disc images and compressed ZIP/RAR archives are unsupported.

## Stage 6 — iOS 16 Files-picker bypass

The Stage 5 picker was still blocking selection on this device. The iOS 16 launcher creates an app-owned `Documents/MCLA_ISO_Input` folder and **Verify Game** scans that folder and the app's Documents root directly. The user should use Apple's Files app to **MOVE** their Xbox 360 Complete Edition `.iso` into **On My iPhone → MCLA → MCLA_ISO_Input**; return to MCLA and tap **Verify Game**. A single ISO is checked automatically; multiple local ISOs present a selection sheet. This avoids the system import picker and verifies the original ISO in place, with bounded read-only IO and no full-disc extraction. The picker is retained as an optional fallback only. This is still an unplayable diagnostic launcher without AOT game code.

## Stage 7 — existing game-folder auto detection

The read-only **Verify Game** button now scans the actual app-owned `Documents/MCLA_Game_Files` first, then `Documents/MCLA_ISO_Input` and the Documents root. No picker, import, extraction, or move is needed for an ISO already in the normal game-data folder. A single ISO takes priority over any extracted `default.xex`. If no relevant file is found, the UI names the scanned locations instead of sending the user back to an iOS 16 Files picker that cannot select ISO files. This remains a native iOS 16 diagnostic shell, not playable game code.
