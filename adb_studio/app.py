"""ADB Control Studio - desktop GUI (Tkinter, stdlib + optional Pillow).

Layout:
  Left   : device list, connection (USB / Wi-Fi), live screen mirror
           (click = tap, drag = swipe, right-click = long press)
  Right  : tabs - Control | Apps | Inspector | Logcat | Record & Auto |
           Screen Record | Files | Shell | Report
Everything the GUI does is also a Step: with Record ON, your clicks and
actions are captured into a Scenario you can replay, export as code
(Python-ADB / Appium / pytest / shell) and run as a test with an
HTML report.
"""
from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:  # pragma: no cover
    HAS_PIL = False

from .adb_client import KEYEVENTS, AdbClient, AdbError
from .codegen import GENERATORS
from .guide import ABOUT_TEXT, GUIDE_SECTIONS
from .recorder import Scenario, Step
from .report import write_report
from .runner import Runner
from .ui_dump import parse_ui_xml

# -- professional dark-sidebar palette -------------------------------------
COLORS = {
    "sidebar_bg": "#0f172a", "sidebar_fg": "#e2e8f0", "sidebar_muted": "#94a3b8",
    "accent": "#2563eb", "accent_hover": "#1d4ed8", "danger": "#dc2626",
    "bg": "#f1f5f9", "panel": "#ffffff", "text": "#0f172a",
    "status_bg": "#1e293b", "status_fg": "#bfdbfe",
}
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_SECTION = ("Segoe UI", 10, "bold")

OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(os.path.join(OUTPUT_DIR, "shots"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "reports"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "videos"), exist_ok=True)


class StudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ADB Control Studio 1.1 - Appium-style control, without Appium")
        self.geometry("1420x880")
        self.minsize(1150, 720)
        self.configure(bg=COLORS["bg"])
        self._apply_theme()
        self._build_menu()
        self._bind_shortcuts()
        self.adb = AdbClient()
        self.scenario = Scenario(name="New scenario")
        self.recording = False
        self.log_process: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.log_paused = False
        self.log_lines: list[str] = []
        self.record_process: subprocess.Popen | None = None
        self.device_size = (1080, 2400)
        self._mirror_img = None
        self._drag_start = None
        self._build_ui()
        self.refresh_devices()
        self._poll_log_queue()
        self.after(300, self.refresh_mirror)

    # ------------------------------------------------------------ theming --
    def _apply_theme(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")  # flat, modern base that accepts custom colors
        except tk.TclError:
            pass
        c = COLORS
        style.configure(".", font=FONT, background=c["bg"], foreground=c["text"])
        style.configure("TFrame", background=c["bg"])
        style.configure("Panel.TFrame", background=c["panel"])
        style.configure("TLabel", background=c["bg"])
        style.configure("Panel.TLabel", background=c["panel"])
        style.configure("Title.TLabel", font=FONT_TITLE, background=c["bg"], foreground=c["text"])
        style.configure("Sub.TLabel", font=FONT_SMALL, background=c["bg"], foreground="#475569")
        style.configure("Section.TLabel", font=FONT_SECTION, background=c["bg"])
        # sidebar (dark)
        style.configure("Side.TFrame", background=c["sidebar_bg"])
        style.configure("Side.TLabel", background=c["sidebar_bg"], foreground=c["sidebar_fg"], font=FONT_SMALL)
        style.configure("SideTitle.TLabel", background=c["sidebar_bg"], foreground="#ffffff",
                        font=("Segoe UI", 13, "bold"))
        style.configure("SideMuted.TLabel", background=c["sidebar_bg"], foreground=c["sidebar_muted"], font=("Segoe UI", 8))
        style.configure("SideSection.TLabel", background=c["sidebar_bg"], foreground="#7dd3fc", font=("Segoe UI", 9, "bold"))
        style.configure("Side.TCheckbutton", background=c["sidebar_bg"], foreground=c["sidebar_fg"], font=FONT_SMALL)
        style.map("Side.TCheckbutton", background=[("active", c["sidebar_bg"])])
        style.configure("Side.TLabelframe", background=c["sidebar_bg"], foreground=c["sidebar_fg"])
        style.configure("Side.TLabelframe.Label", background=c["sidebar_bg"], foreground="#7dd3fc", font=("Segoe UI", 9, "bold"))
        # buttons
        style.configure("TButton", padding=(10, 5), font=FONT_SMALL)
        style.configure("Accent.TButton", background=c["accent"], foreground="#ffffff",
                        padding=(12, 6), font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", c["accent_hover"]), ("disabled", "#93c5fd")])
        style.configure("Danger.TButton", background=c["danger"], foreground="#ffffff",
                        padding=(12, 6), font=("Segoe UI", 9, "bold"))
        style.map("Danger.TButton", background=[("active", "#b91c1c")])
        style.configure("Side.TButton", padding=(8, 4), font=FONT_SMALL)
        # notebook tabs
        style.configure("TNotebook", background=c["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 7), font=("Segoe UI", 9, "bold"),
                        background="#e2e8f0", foreground="#334155")
        style.map("TNotebook.Tab", background=[("selected", c["panel"])], foreground=[("selected", c["accent"])])
        # inputs & trees
        style.configure("TEntry", padding=4)
        style.configure("TCombobox", padding=4)
        style.configure("Treeview", rowheight=24, font=FONT_SMALL, background=c["panel"], fieldbackground=c["panel"])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#e2e8f0")
        style.configure("TLabelframe", background=c["bg"])
        style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"), foreground=c["accent"], background=c["bg"])
        style.configure("TCheckbutton", background=c["bg"], font=FONT_SMALL)
        style.map("TCheckbutton", background=[("active", c["bg"])])

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load scenario JSON...", command=self.load_scenario)
        file_menu.add_command(label="Save scenario JSON...", command=self.save_scenario)
        file_menu.add_separator()
        file_menu.add_command(label="Take screenshot", command=self.take_screenshot)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Refresh devices (F5)", command=self.refresh_devices)
        tools_menu.add_command(label="Refresh screen (F6)", command=self.refresh_mirror)
        tools_menu.add_command(label="Dump UI (Inspector)", command=self.dump_ui)
        tools_menu.add_command(label="Start logcat", command=self.start_logcat)
        tools_menu.add_command(label="Stop logcat", command=self.stop_logcat)
        tools_menu.add_separator()
        tools_menu.add_command(label="Record / stop recording (F9)", command=self.toggle_recording)
        tools_menu.add_command(label="Run scenario + HTML report", command=self.run_with_report)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide (Hướng dẫn)", command=self._open_guide_tab)
        help_menu.add_command(label="About ADB Control Studio", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)

    def _bind_shortcuts(self):
        self.bind_all("<F5>", lambda _e: self.refresh_devices())
        self.bind_all("<F6>", lambda _e: self.refresh_mirror())
        self.bind_all("<F9>", lambda _e: self.toggle_recording())

    def _show_about(self):
        messagebox.showinfo("About ADB Control Studio", ABOUT_TEXT)

    def _open_guide_tab(self):
        for i in range(self.tabs.index("end")):
            if "Guide" in self.tabs.tab(i, "text"):
                self.tabs.select(i)
                return

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        # status bar first so it always owns the bottom strip of the window
        self.status = tk.StringVar(value="Ready. Connect a device (USB debugging ON) or start your emulator, then Refresh (F5).")
        tk.Label(self, textvariable=self.status, bg=COLORS["status_bg"], fg=COLORS["status_fg"],
                 font=FONT_SMALL, anchor="w", padx=10, pady=5).pack(side="bottom", fill="x")

        # ---- left: dark sidebar -------------------------------------------
        left = ttk.Frame(self, width=384, style="Side.TFrame")
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        inner = ttk.Frame(left, style="Side.TFrame")
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        ttk.Label(inner, text="ADB CONTROL STUDIO", style="SideTitle.TLabel").pack(anchor="w")
        ttk.Label(inner, text="Appium-style control - logcat - recorder - codegen - reports",
                  style="SideMuted.TLabel", wraplength=350).pack(anchor="w", pady=(0, 10))

        ttk.Label(inner, text="DEVICES", style="SideSection.TLabel").pack(anchor="w")
        self.device_combo = ttk.Combobox(inner, state="readonly", width=44)
        self.device_combo.pack(fill="x", pady=3)
        self.device_combo.bind("<<ComboboxSelected>>", lambda _e: self._select_device())
        row = ttk.Frame(inner, style="Side.TFrame"); row.pack(fill="x", pady=2)
        ttk.Button(row, text="Refresh (F5)", style="Side.TButton", command=self.refresh_devices).pack(side="left", padx=2)
        ttk.Button(row, text="Device info", style="Side.TButton", command=self.show_device_info).pack(side="left", padx=2)
        ttk.Button(row, text="Reconnect", style="Side.TButton", command=lambda: self._bg(lambda: (self.adb.run(["reconnect"], check=False), self.refresh_devices()))).pack(side="left", padx=2)

        wifi = ttk.LabelFrame(inner, text="Wi-Fi connect (adb tcpip)", style="Side.TLabelframe")
        wifi.pack(fill="x", pady=8)
        self.wifi_entry = ttk.Entry(wifi, width=26)
        self.wifi_entry.insert(0, "192.168.1.100:5555")
        self.wifi_entry.pack(side="left", padx=4, pady=5)
        ttk.Button(wifi, text="Connect", style="Side.TButton", command=self.wifi_connect).pack(side="left", padx=2)
        ttk.Button(wifi, text="tcpip 5555", style="Side.TButton", command=lambda: self._bg(lambda: self.adb.run(["tcpip", "5555"]))).pack(side="left", padx=2)

        ttk.Label(inner, text="LIVE SCREEN", style="SideSection.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(inner, text="Click = tap - Drag = swipe - Right-click = long press",
                  style="SideMuted.TLabel").pack(anchor="w", pady=(0, 4))
        self.mirror = tk.Canvas(inner, width=344, height=540, bg="#020617",
                                highlightthickness=2, highlightbackground="#334155", highlightcolor=COLORS["accent"])
        self.mirror.pack(fill="both", expand=True)
        self.mirror.bind("<ButtonPress-1>", self._mirror_press)
        self.mirror.bind("<ButtonRelease-1>", self._mirror_release)
        self.mirror.bind("<Button-3>", self._mirror_long_press)
        mrow = ttk.Frame(inner, style="Side.TFrame"); mrow.pack(fill="x", pady=6)
        ttk.Button(mrow, text="Screenshot", style="Side.TButton", command=self.take_screenshot).pack(side="left", padx=2)
        ttk.Button(mrow, text="Refresh (F6)", style="Side.TButton", command=self.refresh_mirror).pack(side="left", padx=2)
        self.mirror_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(mrow, text="Auto 2s", style="Side.TCheckbutton", variable=self.mirror_auto).pack(side="left", padx=4)

        # ---- right: header + tabs + status bar ------------------------------
        right = ttk.Frame(self)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=(8, 0))
        header = ttk.Frame(right); header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="Control Center", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  |  Drive the device on the left, automate & report on the right. "
                               "New here? Menu Help > User Guide.",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self._tab_control(); self._tab_apps(); self._tab_inspector(); self._tab_logcat()
        self._tab_record(); self._tab_screenrecord(); self._tab_files(); self._tab_shell(); self._tab_report()
        self._tab_guide()

    # -- tabs ---------------------------------------------------------------
    def _tab_control(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Control")
        nav = ttk.LabelFrame(f, text="Navigation & system keys"); nav.pack(fill="x", padx=8, pady=6)
        for i, key in enumerate(["HOME", "BACK", "APP_SWITCH", "POWER", "WAKEUP", "MENU", "ENTER", "ESCAPE"]):
            ttk.Button(nav, text=key.title(), width=12,
                       command=lambda k=key: self.do_key(k)).grid(row=i // 4, column=i % 4, padx=4, pady=4)
        vol = ttk.LabelFrame(f, text="Volume / media / d-pad"); vol.pack(fill="x", padx=8, pady=6)
        for i, key in enumerate(["VOLUME_UP", "VOLUME_DOWN", "MUTE", "MEDIA_PLAY_PAUSE", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "DPAD_CENTER"]):
            ttk.Button(vol, text=key.replace("_", " ").title(), width=14,
                       command=lambda k=key: self.do_key(k)).grid(row=i // 3, column=i % 3, padx=4, pady=4)

        tapf = ttk.LabelFrame(f, text="Tap / swipe by coordinates"); tapf.pack(fill="x", padx=8, pady=6)
        self.tap_x, self.tap_y = ttk.Entry(tapf, width=8), ttk.Entry(tapf, width=8)
        self.tap_x.grid(row=0, column=0, padx=3, pady=4); self.tap_y.grid(row=0, column=1, padx=3, pady=4)
        ttk.Button(tapf, text="Tap", command=lambda: self.do_tap(int(self.tap_x.get() or 0), int(self.tap_y.get() or 0))).grid(row=0, column=2, padx=3)
        self.sw = [ttk.Entry(tapf, width=8) for _ in range(4)]
        for i, e in enumerate(self.sw): e.grid(row=1, column=i, padx=3, pady=4)
        ttk.Button(tapf, text="Swipe", command=self._do_swipe_form).grid(row=1, column=4, padx=3)

        txtf = ttk.LabelFrame(f, text="Type text into focused field"); txtf.pack(fill="x", padx=8, pady=6)
        self.text_entry = ttk.Entry(txtf, width=60); self.text_entry.pack(side="left", padx=4, pady=4)
        ttk.Button(txtf, text="Send text", command=self.do_text).pack(side="left", padx=2)
        ttk.Button(txtf, text="Paste from clipboard", command=lambda: (self.text_entry.delete(0, "end"), self.text_entry.insert(0, self.clipboard_get()))).pack(side="left", padx=2)

        misc = ttk.LabelFrame(f, text="Quick actions"); misc.pack(fill="x", padx=8, pady=6)
        ttk.Button(misc, text="Wake + unlock swipe", command=lambda: self._bg(lambda: (self.adb.keyevent(224), self.adb.swipe(540, 1800, 540, 800, 300)))).pack(side="left", padx=3, pady=4)
        ttk.Button(misc, text="Open URL / activity...", command=self._open_activity).pack(side="left", padx=3, pady=4)
        ttk.Button(misc, text="Reboot", command=lambda: self._confirm_bg("Reboot device?", lambda: self.adb.run(["reboot"]))).pack(side="left", padx=3, pady=4)
        ttk.Button(misc, text="Battery info", command=lambda: self._bg(lambda: self._set_status(self.adb.battery()))).pack(side="left", padx=3, pady=4)

    def _tab_apps(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Apps")
        top = ttk.Frame(f); top.pack(fill="x", padx=8, pady=6)
        self.app_query = ttk.Entry(top, width=34); self.app_query.pack(side="left", padx=2)
        self.app_3p = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Third-party only", variable=self.app_3p).pack(side="left", padx=4)
        ttk.Button(top, text="List apps", command=self.list_apps).pack(side="left", padx=2)
        ttk.Button(top, text="Current focus", command=lambda: self._bg(lambda: self._set_status(self.adb.current_focus()))).pack(side="left", padx=2)
        self.app_list = tk.Listbox(f, height=18)
        self.app_list.pack(fill="both", expand=True, padx=8, pady=4)
        row = ttk.Frame(f); row.pack(fill="x", padx=8, pady=4)
        for label, fn in [("Launch", self._app_launch), ("Force stop", self._app_stop),
                          ("Clear data", self._app_clear), ("Uninstall", self._app_uninstall),
                          ("App info screen", self._app_info)]:
            ttk.Button(row, text=label, command=fn).pack(side="left", padx=2)
        ttk.Button(f, text="Install APK...", command=self.install_apk).pack(anchor="w", padx=8, pady=4)

    def _tab_inspector(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Inspector (UI dump)")
        ttk.Label(f, text="Like Appium Inspector: dump the UI tree, click an element to see locators, tap it on the device.").pack(anchor="w", padx=8, pady=6)
        ttk.Button(f, text="Dump UI now", command=self.dump_ui).pack(anchor="w", padx=8)
        self.ui_tree = ttk.Treeview(f, columns=("locator",), height=20)
        self.ui_tree.heading("#0", text="Element"); self.ui_tree.heading("locator", text="Locator hint")
        self.ui_tree.column("locator", width=380)
        self.ui_tree.pack(fill="both", expand=True, padx=8, pady=6)
        self.ui_tree.bind("<<TreeviewSelect>>", self._ui_selected)
        row = ttk.Frame(f); row.pack(fill="x", padx=8, pady=4)
        ttk.Button(row, text="Tap selected element", command=self._ui_tap_selected).pack(side="left", padx=2)
        ttk.Button(row, text="Add assert_text step", command=self._ui_add_assert).pack(side="left", padx=2)
        self._ui_elements = []

    def _tab_logcat(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Logcat")
        top = ttk.Frame(f); top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Start", command=self.start_logcat).pack(side="left", padx=2)
        ttk.Button(top, text="Stop", command=self.stop_logcat).pack(side="left", padx=2)
        ttk.Button(top, text="Clear buffer", command=lambda: self._bg(self.adb.clear_logcat)).pack(side="left", padx=2)
        ttk.Button(top, text="Clear view", command=lambda: (self.log_text.delete("1.0", "end"), self.log_lines.clear())).pack(side="left", padx=2)
        ttk.Button(top, text="Save log...", command=self.save_log).pack(side="left", padx=2)
        ttk.Button(top, text="Crash snapshot", command=self.crash_snapshot).pack(side="left", padx=2)
        filt = ttk.Frame(f); filt.pack(fill="x", padx=8, pady=2)
        ttk.Label(filt, text="Filter (text / package / tag):").pack(side="left")
        self.log_filter = ttk.Entry(filt, width=30); self.log_filter.pack(side="left", padx=4)
        ttk.Label(filt, text="Level:").pack(side="left")
        self.log_level = ttk.Combobox(filt, values=["All", "V", "D", "I", "W", "E", "F"], width=5, state="readonly")
        self.log_level.set("All"); self.log_level.pack(side="left", padx=4)
        self.log_count = tk.StringVar(value="0 lines")
        ttk.Label(filt, textvariable=self.log_count).pack(side="left", padx=6)
        self.log_text = tk.Text(f, wrap="none", bg="#0b1220", fg="#d1d5db", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=8, pady=6)
        for tag, color in [("E", "#f87171"), ("W", "#facc15"), ("F", "#ef4444"), ("I", "#93c5fd")]:
            self.log_text.tag_config(f"lvl{tag}", foreground=color)

    def _tab_record(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Record & Automation")
        top = ttk.Frame(f); top.pack(fill="x", padx=8, pady=6)
        self.rec_btn = ttk.Button(top, text="● Start recording actions", style="Accent.TButton", command=self.toggle_recording)
        self.rec_btn.pack(side="left", padx=2)
        ttk.Button(top, text="Replay scenario", command=self.replay_scenario).pack(side="left", padx=2)
        ttk.Button(top, text="Save scenario JSON...", command=self.save_scenario).pack(side="left", padx=2)
        ttk.Button(top, text="Load scenario JSON...", command=self.load_scenario).pack(side="left", padx=2)
        ttk.Button(top, text="Clear steps", command=lambda: (self.scenario.steps.clear(), self._refresh_steps())).pack(side="left", padx=2)
        add = ttk.LabelFrame(f, text="Add step manually"); add.pack(fill="x", padx=8, pady=4)
        self.step_type = ttk.Combobox(add, values=["wait", "assert_text", "assert_package", "assert_no_crash", "shell", "screenshot", "key"],
                                      width=16, state="readonly")
        self.step_type.set("wait"); self.step_type.pack(side="left", padx=3, pady=4)
        self.step_value = ttk.Entry(add, width=44); self.step_value.insert(0, "1")
        self.step_value.pack(side="left", padx=3, pady=4)
        ttk.Button(add, text="Add", command=self.add_manual_step).pack(side="left", padx=2)
        ttk.Label(add, text="wait=seconds - assert_text=text - shell=command - key=HOME/BACK...").pack(side="left", padx=6)
        self.step_list = tk.Listbox(f, height=13)
        self.step_list.pack(fill="both", expand=True, padx=8, pady=4)
        row = ttk.Frame(f); row.pack(fill="x", padx=8, pady=2)
        ttk.Button(row, text="Delete selected step", command=self.delete_step).pack(side="left", padx=2)
        ttk.Button(row, text="Move up", command=lambda: self.move_step(-1)).pack(side="left", padx=2)
        ttk.Button(row, text="Move down", command=lambda: self.move_step(1)).pack(side="left", padx=2)
        gen = ttk.LabelFrame(f, text="Auto-generate code from this scenario"); gen.pack(fill="x", padx=8, pady=6)
        self.gen_target = ttk.Combobox(gen, values=list(GENERATORS.keys()), width=14, state="readonly")
        self.gen_target.set("python_adb"); self.gen_target.pack(side="left", padx=3, pady=4)
        ttk.Button(gen, text="Generate + save...", command=self.generate_code).pack(side="left", padx=2)
        ttk.Button(gen, text="Preview", command=self.preview_code).pack(side="left", padx=2)

    def _tab_screenrecord(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Screen Record")
        ttk.Label(f, text="Records the device screen to MP4 with adb screenrecord (max 180s per clip).").pack(anchor="w", padx=8, pady=6)
        row = ttk.Frame(f); row.pack(anchor="w", padx=8, pady=2)
        ttk.Button(row, text="Start recording", command=self.start_record).pack(side="left", padx=2)
        ttk.Button(row, text="Stop + pull MP4", command=self.stop_record).pack(side="left", padx=2)
        ttk.Button(row, text="Open output/videos folder", command=lambda: os.startfile(os.path.join(OUTPUT_DIR, "videos")) if os.name == "nt" else None).pack(side="left", padx=2)
        ttk.Label(f, text="Tip: screenshots from the mirror / Control tab land in output/shots.").pack(anchor="w", padx=8, pady=4)

    def _tab_files(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Files")
        row = ttk.Frame(f); row.pack(fill="x", padx=8, pady=6)
        self.remote_path = ttk.Entry(row, width=50); self.remote_path.insert(0, "/sdcard/")
        self.remote_path.pack(side="left", padx=2)
        ttk.Button(row, text="List", command=self.list_files).pack(side="left", padx=2)
        ttk.Button(row, text="Push file...", command=self.push_file).pack(side="left", padx=2)
        ttk.Button(row, text="Pull selected...", command=self.pull_file).pack(side="left", padx=2)
        self.file_text = tk.Text(f, wrap="none", font=("Consolas", 9))
        self.file_text.pack(fill="both", expand=True, padx=8, pady=4)

    def _tab_shell(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Shell")
        row = ttk.Frame(f); row.pack(fill="x", padx=8, pady=6)
        self.shell_entry = ttk.Entry(row, width=80); self.shell_entry.pack(side="left", padx=2, fill="x", expand=True)
        self.shell_entry.bind("<Return>", lambda _e: self.run_shell())
        ttk.Button(row, text="Run", command=self.run_shell).pack(side="left", padx=2)
        self.shell_text = tk.Text(f, wrap="word", font=("Consolas", 9), bg="#0b1220", fg="#d1d5db")
        self.shell_text.pack(fill="both", expand=True, padx=8, pady=4)

    def _tab_report(self):
        f = ttk.Frame(self.tabs); self.tabs.add(f, text="Test Run & Report")
        ttk.Label(f, text="Run the current scenario as a test: every step gets a screenshot, "
                          "assertions are checked, then a self-contained HTML report is generated.").pack(anchor="w", padx=8, pady=6)
        row = ttk.Frame(f); row.pack(anchor="w", padx=8, pady=2)
        self.stop_on_fail = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Stop on first failure", variable=self.stop_on_fail).pack(side="left", padx=4)
        ttk.Button(row, text="Run scenario + build HTML report", style="Accent.TButton", command=self.run_with_report).pack(side="left", padx=4)
        ttk.Button(row, text="Open output/reports folder", command=lambda: os.startfile(os.path.join(OUTPUT_DIR, "reports")) if os.name == "nt" else None).pack(side="left", padx=4)
        self.report_text = tk.Text(f, wrap="word", font=("Consolas", 9))
        self.report_text.pack(fill="both", expand=True, padx=8, pady=6)

    def _tab_guide(self):
        f = ttk.Frame(self.tabs, style="Panel.TFrame"); self.tabs.add(f, text="Guide (Hướng dẫn)")
        top = ttk.Frame(f, style="Panel.TFrame"); top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Hướng dẫn sử dụng - ADB Control Studio", style="Panel.TLabel",
                  font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Button(top, text="About", command=self._show_about).pack(side="right", padx=2)
        wrap = ttk.Frame(f, style="Panel.TFrame"); wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        txt = tk.Text(wrap, wrap="word", font=("Segoe UI", 10), bg="#ffffff", fg=COLORS["text"],
                      relief="flat", padx=14, pady=10)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.tag_config("h", font=("Segoe UI", 12, "bold"), foreground=COLORS["accent"], spacing1=14, spacing3=4)
        txt.tag_config("body", font=("Segoe UI", 10), spacing3=8, lmargin1=4, lmargin2=4)
        for title, body in GUIDE_SECTIONS:
            txt.insert("end", title + "\n", "h")
            txt.insert("end", body.strip() + "\n", "body")
        txt.configure(state="disabled")
        self.guide_text = txt

    # ------------------------------------------------------------- helpers --
    def _set_status(self, msg: str):
        self.after(0, lambda: self.status.set(str(msg)[:400]))

    def _bg(self, fn, on_done=None):
        def worker():
            try:
                result = fn()
                if on_done: self.after(0, lambda: on_done(result))
                elif isinstance(result, str) and result: self._set_status(result)
            except Exception as e:
                self._set_status(f"Error: {e}")
                self.after(0, lambda: messagebox.showerror("ADB Control Studio", str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _confirm_bg(self, question, fn):
        if messagebox.askyesno("Confirm", question):
            self._bg(fn)

    def _record(self, step: Step):
        if self.recording:
            self.scenario.add(step)
            self._refresh_steps()

    # ------------------------------------------------------------- devices --
    def refresh_devices(self):
        def work():
            try:
                devices = self.adb.devices()
            except Exception as e:
                self._set_status(f"adb error: {e}"); return
            labels = [d.label for d in devices if d.state == "device"] or ["(no device - check USB debugging)"]
            self.after(0, lambda: (self.device_combo.config(values=labels), self.device_combo.set(labels[0])))
            if devices:
                self.adb.serial = devices[0].serial
                self._bg(lambda: setattr(self, "device_size", self.adb.screen_size()))
        threading.Thread(target=work, daemon=True).start()

    def _select_device(self):
        label = self.device_combo.get()
        if "(" in label:
            self.adb.serial = label.rsplit("(", 1)[1].rstrip(")")
            self._bg(lambda: setattr(self, "device_size", self.adb.screen_size()))
            self.refresh_mirror()

    def show_device_info(self):
        def work():
            p = self.adb.device_props()
            keys = ["ro.product.manufacturer", "ro.product.model", "ro.build.version.release",
                    "ro.build.version.sdk", "ro.product.cpu.abi"]
            info = "\n".join(f"{k}: {p.get(k, '-')}" for k in keys)
            info += f"\nSerial: {self.adb.serial}\nScreen: {self.adb.screen_size()}\n{self.adb.battery()}"
            self.after(0, lambda: messagebox.showinfo("Device info", info))
        self._bg(work)

    def wifi_connect(self):
        target = self.wifi_entry.get().strip()
        ip, _, port = target.partition(":")
        self._bg(lambda: self.adb.connect_wifi(ip, int(port or 5555)), on_done=lambda _r: self.refresh_devices())

    # -------------------------------------------------------------- mirror --
    def refresh_mirror(self):
        if not self.mirror_auto.get() and hasattr(self, "_mirror_done"):
            return
        self._mirror_done = True
        def work():
            try:
                data = self.adb.screenshot_bytes()
                path = os.path.join(OUTPUT_DIR, "shots", "_mirror.png")
                with open(path, "wb") as fh: fh.write(data)
                self.after(0, lambda: self._draw_mirror(path))
            except Exception:
                pass
            if self.mirror_auto.get():
                self.after(2000, self.refresh_mirror)
        threading.Thread(target=work, daemon=True).start()

    def _draw_mirror(self, path):
        try:
            w_canvas = max(self.mirror.winfo_width(), 340)
            if HAS_PIL:
                img = Image.open(path)
                self.device_size = img.size
                scale = min(w_canvas / img.width, 560 / img.height)
                img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
                self._mirror_img = ImageTk.PhotoImage(img)
                self._mirror_scale = (self.device_size[0] / img.width, self.device_size[1] / img.height)
            else:
                self._mirror_img = tk.PhotoImage(file=path)
                self._mirror_scale = (self.device_size[0] / self._mirror_img.width(),
                                      self.device_size[1] / self._mirror_img.height())
            self.mirror.delete("all")
            self.mirror.create_image(0, 0, anchor="nw", image=self._mirror_img)
        except Exception:
            pass

    def _to_device(self, event):
        sx, sy = getattr(self, "_mirror_scale", (3.0, 3.0))
        return int(event.x * sx), int(event.y * sy)

    def _mirror_press(self, event):
        self._drag_start = self._to_device(event)

    def _mirror_release(self, event):
        if not self._drag_start: return
        x2, y2 = self._to_device(event)
        x1, y1 = self._drag_start; self._drag_start = None
        if abs(x2 - x1) < 12 and abs(y2 - y1) < 12:
            self.do_tap(x1, y1)
        else:
            self._bg(lambda: self.adb.swipe(x1, y1, x2, y2, 300))
            self._record(Step(type="swipe", x=x1, y=y1, x2=x2, y2=y2, duration_ms=300))
        self.after(600, self.refresh_mirror)

    def _mirror_long_press(self, event):
        x, y = self._to_device(event)
        self._bg(lambda: self.adb.long_press(x, y, 800))
        self._record(Step(type="long_press", x=x, y=y, duration_ms=800))

    # ------------------------------------------------------------- control --
    def do_tap(self, x, y):
        self._bg(lambda: self.adb.tap(x, y))
        self._record(Step(type="tap", x=int(x), y=int(y)))

    def do_key(self, key):
        self._bg(lambda: self.adb.keyevent(KEYEVENTS[key]))
        self._record(Step(type="key", key=key))

    def do_text(self):
        value = self.text_entry.get()
        self._bg(lambda: self.adb.text(value))
        self._record(Step(type="text", text=value))

    def _do_swipe_form(self):
        vals = [int(e.get() or 0) for e in self.sw]
        self._bg(lambda: self.adb.swipe(*vals, 300))
        self._record(Step(type="swipe", x=vals[0], y=vals[1], x2=vals[2], y2=vals[3], duration_ms=300))

    def _open_activity(self):
        comp = simpledialog.askstring("Open activity", "Component (pkg/.Activity) or action intent:")
        if comp:
            self._bg(lambda: self.adb.start_activity(comp))

    def take_screenshot(self):
        path = os.path.join(OUTPUT_DIR, "shots", f"shot_{AdbClient.now_stamp()}.png")
        self._bg(lambda: self.adb.screenshot(path), on_done=lambda _r: self._set_status(f"Screenshot saved: {path}"))
        self._record(Step(type="screenshot", name=os.path.basename(path)))

    # ---------------------------------------------------------------- apps --
    def _selected_pkg(self) -> str:
        sel = self.app_list.curselection()
        return self.app_list.get(sel[0]) if sel else ""

    def list_apps(self):
        def work():
            pkgs = self.adb.list_packages(self.app_3p.get(), self.app_query.get().strip())
            self.after(0, lambda: (self.app_list.delete(0, "end"),
                                   [self.app_list.insert("end", p) for p in pkgs],
                                   self._set_status(f"{len(pkgs)} packages")))
        self._bg(work)

    def _app_launch(self):
        pkg = self._selected_pkg()
        if pkg: self._bg(lambda: self.adb.launch_app(pkg)); self._record(Step(type="launch_app", package=pkg))
    def _app_stop(self):
        pkg = self._selected_pkg()
        if pkg: self._bg(lambda: self.adb.stop_app(pkg)); self._record(Step(type="stop_app", package=pkg))
    def _app_clear(self):
        pkg = self._selected_pkg()
        if pkg: self._confirm_bg(f"Clear all data of {pkg}?", lambda: self.adb.clear_app(pkg)); self._record(Step(type="clear_app", package=pkg))
    def _app_uninstall(self):
        pkg = self._selected_pkg()
        if pkg: self._confirm_bg(f"Uninstall {pkg}?", lambda: self.adb.uninstall(pkg))
    def _app_info(self):
        pkg = self._selected_pkg()
        if pkg: self._bg(lambda: self.adb.shell(f"am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{pkg}", check=False))
    def install_apk(self):
        path = filedialog.askopenfilename(filetypes=[("APK", "*.apk")])
        if path: self._bg(lambda: self.adb.install(path))

    # ------------------------------------------------------------ inspector --
    def dump_ui(self):
        def work():
            elements = parse_ui_xml(self.adb.ui_dump_xml())
            self._ui_elements = elements
            def fill():
                self.ui_tree.delete(*self.ui_tree.get_children())
                for i, el in enumerate(elements):
                    loc = el.locator_hint()
                    self.ui_tree.insert("", "end", iid=str(i), text=el.label,
                                        values=(f"{loc['strategy']} = {loc['value']}",))
            self.after(0, fill)
        self._bg(work)

    def _ui_selected_el(self):
        sel = self.ui_tree.selection()
        return self._ui_elements[int(sel[0])] if sel and self._ui_elements else None

    def _ui_selected(self, _e=None):
        el = self._ui_selected_el()
        if el: self._set_status(f"{el.class_name} text='{el.text}' id='{el.resource_id}' desc='{el.content_desc}' center={el.center}")

    def _ui_tap_selected(self):
        el = self._ui_selected_el()
        if el:
            x, y = el.center; self.do_tap(x, y)

    def _ui_add_assert(self):
        el = self._ui_selected_el()
        if el and (el.text or el.content_desc):
            self.scenario.add(Step(type="assert_text", text=el.text or el.content_desc))
            self._refresh_steps(); self._set_status("Added assert_text step")

    # -------------------------------------------------------------- logcat --
    def start_logcat(self):
        self.stop_logcat()
        self.adb.clear_logcat()
        extra = []
        level = self.log_level.get()
        if level != "All": extra = ["*:S", f"*:{level}"]
        self.log_process = self.adb.logcat_popen(extra)
        def reader():
            for line in self.log_process.stdout:
                self.log_queue.put(line.rstrip("\n"))
        threading.Thread(target=reader, daemon=True).start()
        self._set_status("Logcat running...")

    def stop_logcat(self):
        if self.log_process:
            self.log_process.terminate(); self.log_process = None

    def _poll_log_queue(self):
        filt = self.log_filter.get().strip().lower()
        batch = []
        try:
            while True: batch.append(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        if batch and not self.log_paused:
            for line in batch:
                if filt and filt not in line.lower(): continue
                self.log_lines.append(line)
                start = self.log_text.index("end-1c")
                self.log_text.insert("end", line + "\n")
                for tag in ("E", "W", "F", "I"):
                    if f" {tag} " in line or f"/{tag}(" in line:
                        self.log_text.tag_add(f"lvl{tag}", start, f"{start} lineend"); break
            self.log_text.see("end")
            self.log_count.set(f"{len(self.log_lines)} lines")
            if len(self.log_lines) > 20000:  # keep the widget responsive
                self.log_text.delete("1.0", "5000.0"); self.log_lines = self.log_lines[-15000:]
        self.after(250, self._poll_log_queue)

    def save_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".log",
                                            initialfile=f"logcat_{AdbClient.now_stamp()}.log",
                                            initialdir=os.path.join(OUTPUT_DIR, "logs"))
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write("\n".join(self.log_lines))
            self._set_status(f"Log saved: {path}")

    def crash_snapshot(self):
        def work():
            out = self.adb.shell("logcat -d | grep -A 30 -E 'FATAL EXCEPTION|AndroidRuntime' | tail -n 200", check=False)
            self.after(0, lambda: messagebox.showinfo("Crash snapshot", out or "No crash lines found in buffer."))
        self._bg(work)

    # -------------------------------------------------------------- record --
    def toggle_recording(self):
        self.recording = not self.recording
        self.rec_btn.config(text="■ Stop recording" if self.recording else "● Start recording actions",
                            style="Danger.TButton" if self.recording else "Accent.TButton")
        self._set_status("Recording ON - every tap/swipe/key/text/app action becomes a step." if self.recording else "Recording OFF")

    def _refresh_steps(self):
        self.step_list.delete(0, "end")
        for i, s in enumerate(self.scenario.steps, 1):
            self.step_list.insert("end", f"{i:02d}. {s.describe()}")

    def add_manual_step(self):
        t, v = self.step_type.get(), self.step_value.get().strip()
        step = Step(type=t)
        if t == "wait": step.seconds = float(v or 1)
        elif t == "assert_text": step.text = v
        elif t == "assert_package": step.package = v
        elif t == "shell": step.command = v
        elif t == "key": step.key = v.upper() or "HOME"
        elif t == "screenshot": step.name = v
        self.scenario.add(step); self._refresh_steps()

    def delete_step(self):
        sel = self.step_list.curselection()
        if sel: del self.scenario.steps[sel[0]]; self._refresh_steps()

    def move_step(self, delta):
        sel = self.step_list.curselection()
        if not sel: return
        i, j = sel[0], sel[0] + delta
        if 0 <= j < len(self.scenario.steps):
            self.scenario.steps[i], self.scenario.steps[j] = self.scenario.steps[j], self.scenario.steps[i]
            self._refresh_steps(); self.step_list.selection_set(j)

    def save_scenario(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Scenario JSON", "*.json")],
                                            initialfile=f"{self.scenario.name.replace(' ', '_')}.json")
        if path:
            self.scenario.name = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
            self.scenario.save(path); self._set_status(f"Scenario saved: {path}")

    def load_scenario(self):
        path = filedialog.askopenfilename(filetypes=[("Scenario JSON", "*.json")])
        if path:
            self.scenario = Scenario.load(path); self._refresh_steps()
            self._set_status(f"Loaded {len(self.scenario.steps)} steps from {path}")

    def replay_scenario(self):
        def work():
            run = Runner(self.adb, screenshot_dir=os.path.join(OUTPUT_DIR, "shots")).run(self.scenario)
            self._set_status(f"Replay done: {run.passed}/{run.total} passed, {run.failed} failed")
        self._bg(work)

    def generate_code(self):
        target = self.gen_target.get()
        ext = ".py" if target != "shell" else ".sh"
        path = filedialog.asksaveasfilename(defaultextension=ext, initialfile=f"generated_{target}{ext}")
        if path:
            code = GENERATORS[target](self.scenario, self.adb.serial or "") if target in ("python_adb", "pytest") else GENERATORS[target](self.scenario)
            with open(path, "w", encoding="utf-8") as f: f.write(code)
            self._set_status(f"Code generated: {path}")

    def preview_code(self):
        target = self.gen_target.get()
        code = GENERATORS[target](self.scenario, self.adb.serial or "") if target in ("python_adb", "pytest") else GENERATORS[target](self.scenario)
        win = tk.Toplevel(self); win.title(f"Preview - {target}"); win.geometry("760x560")
        txt = tk.Text(win, font=("Consolas", 9)); txt.pack(fill="both", expand=True)
        txt.insert("1.0", code)

    # --------------------------------------------------------- screen rec. --
    def start_record(self):
        if self.record_process: return
        self.record_process = self.adb.start_screenrecord()
        self._set_status("Screen recording... (device-side, max 180s)")

    def stop_record(self):
        if not self.record_process: return
        self.adb.shell("pkill -2 screenrecord", check=False)
        time.sleep(1)
        local = os.path.join(OUTPUT_DIR, "videos", f"rec_{AdbClient.now_stamp()}.mp4")
        proc, self.record_process = self.record_process, None
        self._bg(lambda: self.adb.pull("/sdcard/_adb_studio_rec.mp4", local),
                 on_done=lambda _r: self._set_status(f"Video saved: {local}"))
        try: proc.terminate()
        except Exception: pass

    # --------------------------------------------------------------- files --
    def list_files(self):
        def work():
            out = self.adb.ls(self.remote_path.get().strip())
            self.after(0, lambda: (self.file_text.delete("1.0", "end"), self.file_text.insert("1.0", out)))
        self._bg(work)

    def push_file(self):
        path = filedialog.askopenfilename()
        if path:
            remote = self.remote_path.get().strip().rstrip("/") + "/" + os.path.basename(path)
            self._bg(lambda: self.adb.push(path, remote))

    def pull_file(self):
        name = simpledialog.askstring("Pull file", "Remote file name (inside current folder):")
        if name:
            local = filedialog.asksaveasfilename(initialfile=name)
            if local:
                remote = self.remote_path.get().strip().rstrip("/") + "/" + name
                self._bg(lambda: self.adb.pull(remote, local))

    # --------------------------------------------------------------- shell --
    def run_shell(self):
        cmd = self.shell_entry.get().strip()
        if not cmd: return
        def work():
            out = self.adb.shell(cmd, check=False, timeout=60)
            self.after(0, lambda: self.shell_text.insert("end", f"$ {cmd}\n{out}\n\n"))
            self.after(0, lambda: self.shell_text.see("end"))
        self._bg(work)

    # -------------------------------------------------------------- report --
    def run_with_report(self):
        def work():
            runner = Runner(self.adb, screenshot_dir=os.path.join(OUTPUT_DIR, "shots", f"run_{AdbClient.now_stamp()}"),
                            stop_on_failure=self.stop_on_fail.get())
            run = runner.run(self.scenario)
            try:
                run.log_excerpt = self.adb.shell("logcat -d -t 300", check=False)
            except Exception:
                run.log_excerpt = ""
            path = write_report(run, out_dir=os.path.join(OUTPUT_DIR, "reports"))
            summary = (f"Run finished: {run.passed}/{run.total} passed, {run.failed} failed\n"
                       f"Report: {path}\n\n" +
                       "\n".join(f"{'PASS' if r.status=='passed' else r.status.upper():7} step {r.index}: {r.step.describe()} - {r.message}" for r in run.results))
            self.after(0, lambda: (self.report_text.delete("1.0", "end"), self.report_text.insert("1.0", summary)))
            if os.name == "nt":
                os.startfile(path)
        self._bg(work)

    def on_close(self):
        self.stop_logcat()
        self.destroy()


def main():
    app = StudioApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
