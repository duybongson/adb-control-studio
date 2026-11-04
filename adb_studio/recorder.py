"""Automation recorder + scenario model + replay engine.

A Scenario is an ordered list of Steps saved as human-readable JSON.
The GUI records taps/swipes/keys/text/app actions into a Scenario; the
Runner replays it on a real device; Codegen turns it into source code.
Supported step types:
  tap, swipe, long_press, key, text, launch_app, stop_app, clear_app,
  shell, wait, screenshot, assert_text, assert_package, assert_no_crash
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field


@dataclass
class Step:
    type: str
    x: int = 0
    y: int = 0
    x2: int = 0
    y2: int = 0
    duration_ms: int = 300
    key: str = ""
    text: str = ""
    package: str = ""
    command: str = ""
    seconds: float = 1.0
    name: str = ""

    def describe(self) -> str:
        t = self.type
        if t == "tap": return f"Tap ({self.x}, {self.y})"
        if t == "swipe": return f"Swipe ({self.x},{self.y}) -> ({self.x2},{self.y2}) {self.duration_ms}ms"
        if t == "long_press": return f"Long press ({self.x}, {self.y}) {self.duration_ms}ms"
        if t == "key": return f"Key {self.key}"
        if t == "text": return f"Type '{self.text}'"
        if t in ("launch_app", "stop_app", "clear_app"): return f"{t} {self.package}"
        if t == "shell": return f"Shell: {self.command}"
        if t == "wait": return f"Wait {self.seconds}s"
        if t == "screenshot": return f"Screenshot {self.name or ''}".strip()
        if t.startswith("assert"): return f"{t}: {self.text or self.package}"
        return t


@dataclass
class Scenario:
    name: str = "Untitled scenario"
    package: str = ""
    steps: list[Step] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def add(self, step: Step) -> Step:
        self.steps.append(step)
        return step

    def to_dict(self) -> dict:
        return {"name": self.name, "package": self.package, "created_at": self.created_at,
                "steps": [asdict(s) for s in self.steps]}

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        sc = cls(name=data.get("name", "Untitled scenario"), package=data.get("package", ""),
                 created_at=data.get("created_at", ""))
        known = Step.__dataclass_fields__.keys()
        for raw in data.get("steps", []):
            sc.steps.append(Step(**{k: v for k, v in raw.items() if k in known}))
        return sc

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "Scenario":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
