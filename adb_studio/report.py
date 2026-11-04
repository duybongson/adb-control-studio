"""HTML test report: summary, per-step status, embedded screenshots, log excerpt.
Single self-contained .html file (screenshots base64-inlined) - send it to
anyone, no server needed.
"""
from __future__ import annotations

import base64
import html
import os
import time

from .runner import RunResult


def _img_tag(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="screenshot" loading="lazy">'


_CSS = """
body{font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}
h1{font-size:22px;margin:0 0 4px}.meta{color:#94a3b8;font-size:13px;margin-bottom:16px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.card{background:#1e293b;border-radius:12px;padding:14px 18px;min-width:110px}
.card b{font-size:26px;display:block}.pass{color:#4ade80}.fail{color:#f87171}.skip{color:#facc15}
table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;vertical-align:top;font-size:13px;border-bottom:1px solid #334155}
th{background:#334155}.badge{padding:2px 8px;border-radius:999px;font-weight:600;font-size:12px}
.b-passed{background:#14532d;color:#4ade80}.b-failed{background:#7f1d1d;color:#fca5a5}.b-skipped{background:#713f12;color:#fde68a}
img{max-width:180px;border-radius:8px}pre{background:#020617;padding:14px;border-radius:12px;overflow:auto;font-size:12px}
code{color:#93c5fd}
"""


def render_html(run: RunResult, log_excerpt: str = "") -> str:
    rows = []
    for r in run.results:
        rows.append(
            f"<tr><td>{r.index}</td><td><code>{html.escape(r.step.type)}</code><br>{html.escape(r.step.describe())}</td>"
            f"<td><span class='badge b-{r.status}'>{r.status.upper()}</span></td>"
            f"<td>{html.escape(r.message)}</td><td>{r.duration_s:.2f}s</td><td>{_img_tag(r.screenshot)}</td></tr>")
    verdict = "PASSED" if run.ok else "FAILED"
    vclass = "pass" if run.ok else "fail"
    log_block = f"<h2>Logcat excerpt</h2><pre>{html.escape(log_excerpt or run.log_excerpt)}</pre>" if (log_excerpt or run.log_excerpt) else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>ADB Studio Report - {html.escape(run.scenario.name)}</title><style>{_CSS}</style></head><body>
<h1>{html.escape(run.scenario.name)} - <span class="{vclass}">{verdict}</span></h1>
<div class="meta">Device: {html.escape(run.device_serial or '-')} &middot; Started: {html.escape(run.started_at)} &middot;
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} &middot; App under test: {html.escape(run.scenario.package or '-')}</div>
<div class="cards">
 <div class="card"><b>{run.total}</b>Total steps</div>
 <div class="card"><b class="pass">{run.passed}</b>Passed</div>
 <div class="card"><b class="fail">{run.failed}</b>Failed</div>
 <div class="card"><b>{(100*run.passed//run.total) if run.total else 0}%</b>Pass rate</div>
</div>
<table><tr><th>#</th><th>Step</th><th>Status</th><th>Message</th><th>Time</th><th>Screenshot</th></tr>
{''.join(rows)}</table>
{log_block}
</body></html>"""


def write_report(run: RunResult, out_dir: str = "output/reports", log_excerpt: str = "") -> str:
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run.scenario.name)
    path = os.path.join(out_dir, f"report_{safe}_{stamp}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(run, log_excerpt))
    return path
