"""Scenario runner: replays steps on a device, checks assertions,
captures a screenshot per step and returns structured results for reports.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from .adb_client import KEYEVENTS, AdbClient
from .recorder import Scenario, Step
from .ui_dump import find_by_text, parse_ui_xml


@dataclass
class StepResult:
    index: int
    step: Step
    status: str = "passed"          # passed | failed | skipped
    message: str = ""
    duration_s: float = 0.0
    screenshot: str = ""            # local file path (may be "")


@dataclass
class RunResult:
    scenario: Scenario
    device_serial: str = ""
    started_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    results: list[StepResult] = field(default_factory=list)
    log_excerpt: str = ""

    @property
    def passed(self) -> int: return sum(r.status == "passed" for r in self.results)
    @property
    def failed(self) -> int: return sum(r.status == "failed" for r in self.results)
    @property
    def total(self) -> int: return len(self.results)
    @property
    def ok(self) -> bool: return self.failed == 0 and self.total > 0


class Runner:
    def __init__(self, adb: AdbClient, screenshot_dir: str = "output/shots",
                 stop_on_failure: bool = False, step_delay_s: float = 0.4):
        self.adb = adb
        self.screenshot_dir = screenshot_dir
        self.stop_on_failure = stop_on_failure
        self.step_delay_s = step_delay_s
        os.makedirs(screenshot_dir, exist_ok=True)

    def run(self, scenario: Scenario) -> RunResult:
        run = RunResult(scenario=scenario, device_serial=self.adb.serial or "")
        for i, step in enumerate(scenario.steps, 1):
            res = StepResult(index=i, step=step)
            t0 = time.time()
            try:
                res.message = self._execute(step, i)
                if step.type != "screenshot":
                    shot = os.path.join(self.screenshot_dir, f"step_{i:03d}_{step.type}.png")
                    try:
                        self.adb.screenshot(shot)
                        res.screenshot = shot
                    except Exception:
                        pass
            except AssertionError as e:
                res.status, res.message = "failed", str(e)
            except Exception as e:  # adb errors, timeouts...
                res.status, res.message = "failed", f"{type(e).__name__}: {e}"
            res.duration_s = round(time.time() - t0, 3)
            run.results.append(res)
            if res.status == "failed" and self.stop_on_failure:
                for j, rest in enumerate(scenario.steps[i:], i + 1):
                    run.results.append(StepResult(index=j, step=rest, status="skipped",
                                                  message="Skipped after failure"))
                break
            time.sleep(self.step_delay_s)
        return run

    # -- one step -----------------------------------------------------------
    def _execute(self, step: Step, index: int) -> str:
        adb, t = self.adb, step.type
        if t == "tap": adb.tap(step.x, step.y)
        elif t == "swipe": adb.swipe(step.x, step.y, step.x2, step.y2, step.duration_ms)
        elif t == "long_press": adb.long_press(step.x, step.y, step.duration_ms)
        elif t == "key": adb.keyevent(KEYEVENTS.get(step.key.upper(), step.key))
        elif t == "text": adb.text(step.text)
        elif t == "launch_app": return adb.launch_app(step.package) or f"Launched {step.package}"
        elif t == "stop_app": adb.stop_app(step.package)
        elif t == "clear_app": adb.clear_app(step.package)
        elif t == "shell": return adb.shell(step.command, check=False)[:500]
        elif t == "wait": time.sleep(step.seconds)
        elif t == "screenshot":
            path = os.path.join(self.screenshot_dir, step.name or f"shot_{index:03d}.png")
            adb.screenshot(path)
            return f"Saved {path}"
        elif t == "assert_text":
            elements = parse_ui_xml(adb.ui_dump_xml())
            if not find_by_text(elements, step.text):
                raise AssertionError(f"Text not found on screen: '{step.text}'")
            return f"Found text '{step.text}'"
        elif t == "assert_package":
            focus = adb.current_focus()
            if step.package not in focus:
                raise AssertionError(f"Expected package {step.package} in focus, got: {focus[:200]}")
            return f"{step.package} is in focus"
        elif t == "assert_no_crash":
            out = adb.shell(f"logcat -d -t 200 | grep -i 'FATAL EXCEPTION'", check=False)
            if out:
                raise AssertionError(f"Crash found in logcat: {out[:300]}")
            return "No FATAL EXCEPTION in recent logcat"
        else:
            return f"(unknown step type '{t}' - skipped)"
        return "OK"
