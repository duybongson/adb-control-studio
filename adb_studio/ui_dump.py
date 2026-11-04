"""Parse `uiautomator dump` XML: element tree, tap targets and locator hints.

This is what makes the tool feel like Appium Inspector: click an element in
the tree, get its bounds, resource-id / content-desc / text and a ready-made
locator suggestion for generated code.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class UiElement:
    text: str = ""
    resource_id: str = ""
    class_name: str = ""
    package: str = ""
    content_desc: str = ""
    clickable: bool = False
    enabled: bool = True
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)
    children: list["UiElement"] = field(default_factory=list)

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bounds
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def label(self) -> str:
        name = self.text or self.content_desc or self.resource_id.split("/")[-1] or self.class_name.split(".")[-1]
        return f"{name}  [{self.class_name.split('.')[-1]}] {self.bounds}"

    def locator_hint(self) -> dict:
        """Best Appium-style locator for this element, most stable first."""
        if self.resource_id:
            return {"strategy": "id", "value": self.resource_id}
        if self.content_desc:
            return {"strategy": "accessibility id", "value": self.content_desc}
        if self.text:
            return {"strategy": "xpath", "value": f"//*[@text='{self.text}']"}
        return {"strategy": "xpath", "value": f"//{self.class_name}"}


_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _parse_bounds(raw: str) -> tuple[int, int, int, int]:
    m = _BOUNDS.match(raw or "")
    return tuple(int(v) for v in m.groups()) if m else (0, 0, 0, 0)


def parse_ui_xml(xml_text: str) -> list[UiElement]:
    """Return a flat list of all elements (tree is reachable via children)."""
    if not xml_text or "<hierarchy" not in xml_text:
        return []
    # uiautomator output can contain a leading 'UI hierchary dumped to: ...' line
    start = xml_text.find("<?xml")
    if start > 0:
        xml_text = xml_text[start:]
    root = ET.fromstring(xml_text)
    flat: list[UiElement] = []

    def walk(node) -> UiElement:
        el = UiElement(
            text=node.get("text", ""), resource_id=node.get("resource-id", ""),
            class_name=node.get("class", ""), package=node.get("package", ""),
            content_desc=node.get("content-desc", ""),
            clickable=node.get("clickable") == "true",
            enabled=node.get("enabled", "true") == "true",
            bounds=_parse_bounds(node.get("bounds", "")))
        flat.append(el)
        for child in node:
            el.children.append(walk(child))
        return el

    for child in root:
        walk(child)
    return flat


def find_by_text(elements: list[UiElement], needle: str, exact: bool = False) -> UiElement | None:
    for el in elements:
        hay = [el.text, el.content_desc]
        if any((h == needle if exact else needle.lower() in h.lower()) for h in hay if h):
            return el
    return None
