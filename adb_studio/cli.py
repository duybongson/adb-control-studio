"""Headless CLI - same engine as the GUI, for CI / scheduled automation.

Examples:
  python -m adb_studio devices
  python -m adb_studio screenshot out.png
  python -m adb_studio logcat --seconds 10 --out output/logs/run.log
  python -m adb_studio run scenarios/example_smoke.json --report output/reports
  python -m adb_studio gen scenarios/example_smoke.json --target appium --out test_appium.py
"""
from __future__ import annotations

import argparse
import sys
import time

from .adb_client import AdbClient
from .codegen import GENERATORS
from .recorder import Scenario
from .report import write_report
from .runner import Runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="adb-studio", description="ADB Control Studio CLI")
    p.add_argument("--serial", default="", help="device serial (default: first device)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("devices")
    sp = sub.add_parser("screenshot"); sp.add_argument("out")
    lp = sub.add_parser("logcat"); lp.add_argument("--seconds", type=float, default=10)
    lp.add_argument("--out", default="")
    rp = sub.add_parser("run"); rp.add_argument("scenario")
    rp.add_argument("--report", default="output/reports"); rp.add_argument("--stop-on-failure", action="store_true")
    gp = sub.add_parser("gen"); gp.add_argument("scenario")
    gp.add_argument("--target", choices=list(GENERATORS), default="python_adb"); gp.add_argument("--out", default="")

    args = p.parse_args(argv)
    adb = AdbClient(serial=args.serial or None)
    if not args.serial and args.cmd in ("screenshot", "logcat", "run"):
        try:
            devs = [d for d in adb.devices() if d.state == "device"]
            if devs: adb.serial = devs[0].serial
        except Exception:
            pass  # the command itself will surface a clear adb error

    if args.cmd == "devices":
        for d in adb.devices(): print(d.label, d.state)
        return 0
    if args.cmd == "screenshot":
        print(adb.screenshot(args.out)); return 0
    if args.cmd == "logcat":
        proc = adb.logcat_popen()
        lines = []
        try:
            t0 = time.time()
            for line in proc.stdout:
                lines.append(line.rstrip("\n"))
                if time.time() - t0 > args.seconds: break
        finally:
            proc.terminate()
        text = "\n".join(lines)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f: f.write(text)
            print(f"Wrote {len(lines)} lines to {args.out}")
        else:
            print(text)
        return 0
    if args.cmd == "run":
        sc = Scenario.load(args.scenario)
        run = Runner(adb, stop_on_failure=args.stop_on_failure).run(sc)
        try: run.log_excerpt = adb.shell("logcat -d -t 300", check=False)
        except Exception: pass
        path = write_report(run, out_dir=args.report)
        print(f"{run.passed}/{run.total} passed, {run.failed} failed -> {path}")
        return 0 if run.ok else 1
    if args.cmd == "gen":
        sc = Scenario.load(args.scenario)
        fn = GENERATORS[args.target]
        code = fn(sc, adb.serial or "") if args.target in ("python_adb", "pytest") else fn(sc)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f: f.write(code)
            print(f"Wrote {args.out}")
        else:
            print(code)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
