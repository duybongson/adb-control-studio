"""Unit tests that need NO Android device: scenario round-trip, codegen, report."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adb_studio.codegen import GENERATORS
from adb_studio.recorder import Scenario, Step
from adb_studio.report import render_html
from adb_studio.runner import RunResult, StepResult
from adb_studio.ui_dump import parse_ui_xml


def sample_scenario():
    sc = Scenario(name="Sample", package="com.android.settings")
    sc.add(Step(type="launch_app", package="com.android.settings"))
    sc.add(Step(type="wait", seconds=1))
    sc.add(Step(type="tap", x=100, y=200))
    sc.add(Step(type="text", text="hello world"))
    sc.add(Step(type="assert_text", text="Settings"))
    return sc


def test_scenario_json_roundtrip(tmp_path):
    sc = sample_scenario()
    path = str(tmp_path / "sc.json")
    sc.save(path)
    loaded = Scenario.load(path)
    assert loaded.name == "Sample" and len(loaded.steps) == 5
    assert loaded.steps[2].x == 100 and loaded.steps[3].text == "hello world"


def test_codegen_all_targets_compile_or_look_sane():
    sc = sample_scenario()
    for target, fn in GENERATORS.items():
        code = fn(sc, "") if target in ("python_adb", "pytest") else fn(sc)
        assert code.strip(), target
        if target in ("python_adb", "pytest", "appium"):
            compile(code, f"<{target}>", "exec")  # generated Python must be valid


def test_report_html_contains_summary():
    sc = sample_scenario()
    run = RunResult(scenario=sc, device_serial="emulator-5554")
    run.results.append(StepResult(index=1, step=sc.steps[0], status="passed", message="OK"))
    run.results.append(StepResult(index=2, step=sc.steps[1], status="failed", message="boom"))
    html = render_html(run, log_excerpt="E/AndroidRuntime: FATAL")
    assert "Sample" in html and "FAILED" in html and "FATAL" in html


def test_parse_ui_xml():
    xml = """<?xml version="1.0"?><hierarchy rotation="0">
    <node text="Settings" resource-id="android:id/title" class="android.widget.TextView"
          package="com.android.settings" content-desc="" clickable="true" enabled="true"
          bounds="[0,100][500,200]"/></hierarchy>"""
    els = parse_ui_xml(xml)
    assert len(els) == 1 and els[0].center == (250, 150)
    assert els[0].locator_hint()["value"] == "android:id/title"
