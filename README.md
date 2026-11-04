# ADB Control Studio

**Full ADB device control like Appium Inspector + Android Studio, but simpler:
no Appium server, no WebDriver, no Node. One pure-Python desktop app.**

Built for QA / automation work: control a real device, grab logs, record a
flow once, replay it, auto-generate code from it, and ship an HTML test
report — all from one window.

## Features

| Area | What you get |
|---|---|
| **Devices** | USB + Wi-Fi (`adb tcpip` / `connect`), device info, battery, reconnect, multi-device picker |
| **Live control** | Live screen mirror — **click = tap, drag = swipe, right-click = long press**; nav/volume/d-pad keys, tap/swipe by coordinates, type text, open activities, reboot |
| **Apps** | List/filter packages (3rd-party or all), launch, force-stop, clear data, uninstall, install APK, current-focus detector |
| **Inspector** | `uiautomator` UI dump like Appium Inspector: element tree, resource-id / content-desc / text, bounds, locator hints, tap element, turn an element into an `assert_text` step |
| **Logcat** | Live streaming logcat with text/package filter + level filter, color-coded E/W/F/I, pause-safe buffer, save `.log`, crash snapshot (`FATAL EXCEPTION` / AndroidRuntime) |
| **Record & Automation** | Record every GUI action (tap/swipe/long-press/key/text/app) into a scenario; edit/reorder steps; add manual steps (`wait`, `assert_text`, `assert_package`, `assert_no_crash`, `shell`, `screenshot`, `key`); save/load scenario JSON; 1-click replay |
| **Auto code generation** | From any scenario: **Python (pure adb, zero deps)**, **Appium Python**, **pytest**, and **bash shell script** — preview before saving |
| **Screen record** | `adb screenrecord` start/stop, auto-pull MP4; screenshots to `output/shots/` |
| **Files** | Browse `/sdcard/`, push/pull files |
| **Shell** | Built-in adb-shell console |
| **Test run & Report** | Run a scenario as a test: screenshot per step, assertions, optional stop-on-failure, logcat excerpt, and a **single self-contained HTML report** (screenshots embedded) in `output/reports/` |
| **CLI (headless/CI)** | `devices`, `screenshot`, `logcat`, `run <scenario> --report`, `gen <scenario> --target appium` — exit code 0/1 for CI |

## Requirements

- Python 3.10+ (Tkinter is in the standard library)
- Android `platform-tools` (`adb`) in PATH, or set `ADB_PATH`
- A device/emulator with **USB debugging** enabled
- Optional: `pip install Pillow` for smoother mirror scaling

## Interface (v1.1)

- Dark device sidebar (device picker, Wi-Fi connect, live mirror) + light control center.
- Menu bar (File / Tools / Help), keyboard shortcuts: **F5** refresh devices, **F6** refresh
  screen, **F9** start/stop recording.
- Accent primary actions; the Record button turns red while recording.
- Built-in **Guide tab** with the full user guide in Vietnamese (also in
  [docs/GUIDE.md](docs/GUIDE.md), or menu **Help > User Guide**).

## Quick start (Windows)

```bat
run.bat
```

or anywhere:

```bash
python main.py            # GUI
python main.py devices    # CLI
python -m adb_studio run scenarios/example_smoke.json
python -m adb_studio gen scenarios/example_smoke.json --target pytest --out test_smoke.py
```

## Typical QA flow

1. Plug in the phone → **Refresh** → pick the device.
2. Open your app, hit **● Start recording**, drive the flow on the live mirror.
3. Add `assert_text` steps from the **Inspector** tab.
4. **Save scenario JSON**, then either **Replay**, **Generate code**, or
   **Run + build HTML report**.

## Project layout

```
main.py                 entry point (GUI if no args, CLI otherwise)
adb_studio/
  adb_client.py         all adb operations (devices, control, apps, logcat, files)
  ui_dump.py            uiautomator XML parsing + locator hints
  recorder.py           Scenario / Step model (JSON)
  runner.py             replay engine + assertions + per-step screenshots
  codegen.py            scenario -> Python-ADB / Appium / pytest / shell
  report.py             self-contained HTML report generator
  app.py                Tkinter GUI (9 tabs)
  cli.py                headless CLI for CI
scenarios/              example scenarios
tests/                  device-free unit tests (pytest tests/)
output/                 shots / videos / logs / reports (git-ignored)
```

## Notes & limits

- Pinch/zoom is not supported by `adb input` (single pointer only) — swipe twice
  or use the app's +/- controls instead.
- `screenrecord` is capped at 180s per clip by Android itself.
- Text input uses `adb input text` (spaces work; some IME/Unicode cases are
  better typed via clipboard on the device).
