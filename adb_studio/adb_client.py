"""Thin, reliable wrapper around the `adb` binary (stdlib only).

Every method returns plain Python data and raises AdbError with the raw
adb output on failure, so the GUI / runner / codegen can report it cleanly.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field


class AdbError(RuntimeError):
    pass


def find_adb(explicit: str | None = None) -> str:
    """Locate adb: explicit path > $ADB_PATH > PATH > Android SDK defaults."""
    candidates = [explicit, os.environ.get("ADB_PATH"), shutil.which("adb")]
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or os.path.join(
            home, "AppData", "Local", "Android", "Sdk")
        candidates += [os.path.join(sdk, "platform-tools", "adb.exe"),
                       r"C:\platform-tools\adb.exe", r"D:\platform-tools\adb.exe"]
    else:
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or os.path.join(home, "Android", "Sdk")
        candidates += [os.path.join(sdk, "platform-tools", "adb")]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    if shutil.which("adb"):
        return "adb"
    return "adb"  # let subprocess raise a clear error later


@dataclass
class Device:
    serial: str
    state: str = "device"
    props: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        model = self.props.get("model") or self.props.get("ro.product.model", "")
        return f"{model} ({self.serial})".strip() if model else self.serial


KEYEVENTS = {
    "HOME": 3, "BACK": 4, "CALL": 5, "ENDCALL": 6, "DPAD_UP": 19, "DPAD_DOWN": 20,
    "DPAD_LEFT": 21, "DPAD_RIGHT": 22, "DPAD_CENTER": 23, "POWER": 26, "CAMERA": 27,
    "VOLUME_UP": 24, "VOLUME_DOWN": 25, "MUTE": 164, "ENTER": 66, "TAB": 61,
    "ESCAPE": 111, "DELETE": 67, "MENU": 82, "APP_SWITCH": 187, "MEDIA_PLAY_PAUSE": 85,
    "BRIGHTNESS_UP": 221, "BRIGHTNESS_DOWN": 220, "WAKEUP": 224, "SLEEP": 223,
}


class AdbClient:
    def __init__(self, adb_path: str | None = None, serial: str | None = None):
        self.adb = find_adb(adb_path)
        self.serial = serial

    # -- core -------------------------------------------------------------
    def run(self, args: list[str], timeout: float = 30, check: bool = True) -> str:
        cmd = [self.adb]
        if self.serial and args[:1] not in (["connect"], ["disconnect"]):
            cmd += ["-s", self.serial]
        cmd += args
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
        except FileNotFoundError as e:
            raise AdbError(f"adb not found at '{self.adb}'. Install Android platform-tools "
                           f"or set ADB_PATH.") from e
        except subprocess.TimeoutExpired as e:
            raise AdbError(f"adb timed out after {timeout}s: {' '.join(cmd)}") from e
        out = (p.stdout or "") + (p.stderr or "")
        if check and p.returncode != 0:
            raise AdbError(out.strip() or f"adb exited {p.returncode}: {' '.join(cmd)}")
        return out.strip()

    def shell(self, command: str, timeout: float = 30, check: bool = True) -> str:
        return self.run(["shell", command], timeout=timeout, check=check)

    def popen(self, args: list[str]) -> subprocess.Popen:
        cmd = [self.adb]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += args
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")

    # -- devices ----------------------------------------------------------
    def devices(self) -> list[Device]:
        out = self.run(["devices", "-l"], check=False)
        result = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            props = {}
            for token in parts[2:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    props[k] = v
            result.append(Device(serial=parts[0], state=parts[1], props=props))
        return result

    def connect_wifi(self, ip: str, port: int = 5555) -> str:
        return self.run(["connect", f"{ip}:{port}"], check=False)

    def disconnect(self, target: str = "") -> str:
        return self.run(["disconnect"] + ([target] if target else []), check=False)

    def device_props(self) -> dict:
        raw = self.shell("getprop", check=False)
        props = {}
        for m in re.finditer(r"\[(.+?)\]: \[(.*)\]", raw):
            props[m.group(1)] = m.group(2)
        return props

    def screen_size(self) -> tuple[int, int]:
        out = self.shell("wm size", check=False)
        m = re.search(r"(\d+)x(\d+)", out)
        return (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)

    def battery(self) -> str:
        return self.shell("dumpsys battery | grep -E 'level|status|temperature'", check=False)

    def current_focus(self) -> str:
        out = self.shell("dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'", check=False)
        return out.strip()

    # -- control ----------------------------------------------------------
    def tap(self, x: int, y: int): self.shell(f"input tap {int(x)} {int(y)}")
    def swipe(self, x1, y1, x2, y2, duration_ms: int = 300):
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}")
    def long_press(self, x, y, duration_ms: int = 800): self.swipe(x, y, x, y, duration_ms)
    def keyevent(self, code): self.shell(f"input keyevent {code}")
    def text(self, value: str):
        # adb input text: spaces -> %s, escape shell-sensitive characters
        safe = value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
        self.shell(f'input text "{safe}"')
    def start_activity(self, component_or_action: str):
        if "/" in component_or_action:
            return self.shell(f"am start -n {component_or_action}", check=False)
        return self.shell(f"am start -a {component_or_action}", check=False)

    # -- apps ---------------------------------------------------------------
    def list_packages(self, third_party_only: bool = False, query: str = "") -> list[str]:
        args = "pm list packages" + (" -3" if third_party_only else "")
        out = self.shell(args, check=False)
        pkgs = [ln.replace("package:", "").strip() for ln in out.splitlines() if ln.startswith("package:")]
        if query:
            pkgs = [p for p in pkgs if query.lower() in p.lower()]
        return sorted(pkgs)

    def install(self, apk_path: str, replace: bool = True, grant: bool = True) -> str:
        args = ["install"] + (["-r"] if replace else []) + (["-g"] if grant else []) + [apk_path]
        return self.run(args, timeout=180)
    def uninstall(self, package: str) -> str: return self.run(["uninstall", package], timeout=120)
    def launch_app(self, package: str) -> str:
        return self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1", check=False)
    def stop_app(self, package: str): self.shell(f"am force-stop {package}", check=False)
    def clear_app(self, package: str): self.shell(f"pm clear {package}", check=False)
    def app_pid(self, package: str) -> str: return self.shell(f"pidof {package}", check=False).strip()

    # -- capture ------------------------------------------------------------
    def screenshot(self, local_path: str) -> str:
        remote = "/sdcard/_adb_studio_shot.png"
        self.shell(f"screencap -p {remote}")
        self.run(["pull", remote, local_path])
        self.shell(f"rm {remote}", check=False)
        return local_path

    def screenshot_bytes(self) -> bytes:
        p = subprocess.run([self.adb] + (["-s", self.serial] if self.serial else []) +
                           ["exec-out", "screencap", "-p"], capture_output=True, timeout=30)
        if p.returncode != 0 or not p.stdout:
            raise AdbError("screencap failed")
        return p.stdout

    def start_screenrecord(self, remote: str = "/sdcard/_adb_studio_rec.mp4", time_limit: int = 180):
        return self.popen(["shell", f"screenrecord --time-limit {time_limit} {remote}"])

    def ui_dump_xml(self) -> str:
        self.shell("uiautomator dump /sdcard/_adb_studio_ui.xml", check=False, timeout=30)
        return self.shell("cat /sdcard/_adb_studio_ui.xml", check=False, timeout=30)

    # -- files ---------------------------------------------------------------
    def push(self, local: str, remote: str) -> str: return self.run(["push", local, remote], timeout=180)
    def pull(self, remote: str, local: str) -> str: return self.run(["pull", remote, local], timeout=180)
    def ls(self, remote: str = "/sdcard/") -> str: return self.shell(f"ls -la {remote}", check=False)

    # -- logcat ---------------------------------------------------------------
    def clear_logcat(self): self.run(["logcat", "-c"], check=False)
    def logcat_popen(self, extra_args: list[str] | None = None) -> subprocess.Popen:
        return self.popen(["logcat", "-v", "threadtime"] + (extra_args or []))

    def wait_for_device(self, timeout: float = 30) -> bool:
        try:
            self.run(["wait-for-device"], timeout=timeout)
            return True
        except AdbError:
            return False

    @staticmethod
    def now_stamp() -> str:
        return time.strftime("%Y%m%d_%H%M%S")
