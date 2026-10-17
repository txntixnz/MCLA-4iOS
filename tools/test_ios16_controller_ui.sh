#!/bin/bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
out=${1:-out/controller-ui}
mkdir -p "$out/ControllerPreview.app"
out=$(CDPATH= cd -- "$out" && pwd)
app="$out/ControllerPreview.app"
cp tools/launcher_preview/Info.plist "$app/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.txntixnz.mcla.controller-uitest' "$app/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :MinimumOSVersion 16.0' "$app/Info.plist"
architecture=$(uname -m)
target="$architecture-apple-ios16.0-simulator"
xcrun --sdk iphonesimulator clang++ -std=c++20 -target "$target" \
    -I MCLAApp/ios -c MCLAApp/ios/MCLAISOReader.cpp -o "$out/iso.o"
xcrun --sdk iphonesimulator clang++ -std=c++20 -target "$target" -fobjc-arc -fblocks \
    -DMCLA_LAUNCHER_INTEGRATION_TEST=1 -I MCLAApp/ios -I MCLAApp/runtime \
    tools/launcher_preview/main.mm tools/launcher_preview/controller_preview.mm \
    tools/launcher_preview/runtime_stubs.mm MCLAApp/ios/MCLAViewController.mm \
    MCLAApp/ios/MCLALauncherView.mm MCLAApp/ios/MCLALauncherSceneView.mm \
    MCLAApp/ios/MCLASaveArchive.mm MCLAApp/ios/MCLALogArchive.mm \
    MCLAApp/ios/MCLAGameInput.mm "$out/iso.o" \
    -framework UIKit -framework SceneKit -framework Foundation -framework QuartzCore \
    -framework CoreGraphics -framework MetalKit -framework Metal -framework CoreMotion \
    -framework GameController -framework UniformTypeIdentifiers -lz -o "$app/LauncherPreview"
codesign --force --sign - "$app"
runtime=$(xcrun simctl list runtimes -j | python3 -c 'import sys,json; r=[r for r in json.load(sys.stdin)["runtimes"] if r.get("isAvailable") and "iOS" in r["name"]]; assert r; print(sorted(r,key=lambda r:tuple(int(x) for x in r["version"].split(".")))[-1]["identifier"])')
device=$(xcrun simctl create MCLA-Controller-UI com.apple.CoreSimulator.SimDeviceType.iPhone-13-Pro-Max "$runtime")
trap 'xcrun simctl shutdown "$device" >/dev/null 2>&1 || true; xcrun simctl delete "$device" >/dev/null 2>&1 || true' EXIT
xcrun simctl boot "$device"
python3 - "$device" "$out" <<'PYTHON'
import subprocess,sys,pathlib
p=pathlib.Path(sys.argv[2])/'simulator-boot.log'
with p.open('w') as f:
    try: subprocess.run(['xcrun','simctl','bootstatus',sys.argv[1],'-b'],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
    except BaseException:
        print(p.read_text()[-12000:]);raise
PYTHON
xcrun simctl install "$device" "$app"
python3 - "$device" "$out" <<'PYTHON'
import subprocess,sys,pathlib,shutil

device,out=sys.argv[1],pathlib.Path(sys.argv[2])
bundle='com.txntixnz.mcla.controller-uitest'
# Cold simulator launch can exceed 30 seconds. Attach until this finite test exits.
run=subprocess.run(['xcrun','simctl','launch','--console',device,bundle],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
(out/'controller-ui.log').write_text(run.stdout)
print(run.stdout[-14000:])
assert run.returncode==0 and 'MCLA_CONTROLLER_UI_TEST PASS:' in run.stdout,'Controller UI regression did not pass'
container=subprocess.check_output(['xcrun','simctl','get_app_container',device,bundle,'data'],text=True).strip()
documents=pathlib.Path(container)/'Documents'
result=documents/'controller-ui-result.txt'
assert result.exists() and 'MCLA_CONTROLLER_UI_TEST PASS' in result.read_text(),'Controller UI regression did not pass'
print(result.read_text())
shutil.copyfile(documents/'xbox-touch-layout.png',out/'xbox-touch-layout.png')
PYTHON
