import json
import math
import random
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

from constants import C, DEFAULT_DH, PATIENT, SURGICAL_ZONES
from kinematics import Camera3D, fk, joint_pos
from data_models import ALERTS, VITALS
from widgets import card, sec_header, Sparkline, DHPopup
from tab_live_video import LiveVideoTab
from tabs import build_preop_workflow, build_alerts_tab, build_postop_workflow


class SurgicalConsole(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SURGICAL ROBOTIC CONSOLE  //  OR-3  //  Dr. A. Patel")
        self.configure(bg=C["bg0"])
        self.geometry("2560x1080")
        self.minsize(2560, 1080)

        self.dh_params      = [dict(p) for p in DEFAULT_DH]
        self.camera         = Camera3D()
        self._drag_start    = None
        self._anim_running  = False
        self._anim_t        = 0.0
        self._popups        = {}
        self._active_tab    = tk.StringVar(value="LIVE CONTROL")
        self._op_phase      = tk.StringVar(value="INTRA-OP")
        self._elapsed       = 0
        self._timer_running = False

        # Vital events log for the Patient Vitals tab
        self._vital_events = []

        ALERTS.callbacks.append(self._refresh_alert_badge)
        VITALS.start(self._vitals_tick)

        self._build_ui()
        self._update_all()
        self._start_clock()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if hasattr(self, "_live_video"):
            self._live_video.stop_video()
        VITALS.stop()
        self.destroy()

    # ══════════════════════════════════════════════════════════════
    #  TOP-LEVEL LAYOUT
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_topbar()

        body = tk.Frame(self, bg=C["bg0"])
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._left = tk.Frame(body, bg=C["bg0"], width=280)
        self._left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        self._left.pack_propagate(False)
        self._build_sidebar()

        self._right = tk.Frame(body, bg=C["bg0"], width=300)
        self._right.pack(side=tk.RIGHT, fill=tk.Y)
        self._right.pack_propagate(False)

        self._center_frame = tk.Frame(body, bg=C["bg0"])
        self._center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        # Workflow tab bar (PRE-OP / INTRA-OP / POST-OP)
        self._build_workflow_tab_bar(self._center_frame)

        # Sub-tab bar (only visible for INTRA-OP)
        self._build_intraop_sub_bar(self._center_frame)

        self._tab_container = tk.Frame(self._center_frame, bg=C["bg0"])
        self._tab_container.pack(fill=tk.BOTH, expand=True)

        self._build_right_sidebar()   # must come before _build_all_tabs (vitals widgets needed)
        self._build_all_tabs()

        # Default: INTRA-OP workflow → LIVE CONTROL sub-tab
        self._switch_workflow("INTRA-OP")

    # ══════════════════════════════════════════════════════════════
    #  TOP BAR
    # ══════════════════════════════════════════════════════════════

    def _build_topbar(self):
        tb = tk.Frame(self, bg=C["bg2"], height=56)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)

        # Title — no logo, clean left edge
        tk.Label(tb, text="  SURGICAL ROBOTIC CONSOLE",
                 font=("Consolas", 14, "bold"), bg=C["bg2"], fg=C["txt0"]).pack(side=tk.LEFT, padx=(16, 0))
        tk.Label(tb, text="  MEDROBOT OS v4.2",
                 font=("Consolas", 9), bg=C["bg2"], fg=C["txt2"]).pack(side=tk.LEFT)

        right = tk.Frame(tb, bg=C["bg2"])
        right.pack(side=tk.RIGHT, padx=16)

        # Clock
        self._clock_var = tk.StringVar(value="--:--:--")
        clock_f = tk.Frame(right, bg=C["cyan"], padx=10, pady=4)
        clock_f.pack(side=tk.LEFT, padx=6)
        tk.Label(clock_f, textvariable=self._clock_var,
                 font=("Consolas", 13, "bold"), bg=C["cyan"], fg="white").pack()

        # OR Status
        or_f = tk.Frame(right, bg=C["green_bg"],
                        highlightthickness=1, highlightbackground=C["green"])
        or_f.pack(side=tk.LEFT, padx=6, pady=8)
        tk.Label(or_f, text="● OR-3  ACTIVE",
                 font=("Consolas", 9, "bold"), bg=C["green_bg"], fg=C["green"],
                 padx=8, pady=4).pack()

        # Alert badge
        self._alert_badge_var = tk.StringVar(value="")
        self._alert_badge = tk.Label(right, textvariable=self._alert_badge_var,
                                     font=("Consolas", 8, "bold"),
                                     bg=C["red"], fg="white", padx=8, pady=4)

        # OP Timer
        timer_f = tk.Frame(right, bg=C["bg2"])
        timer_f.pack(side=tk.LEFT, padx=10)
        self._timer_var = tk.StringVar(value="00:00:00")
        tk.Label(timer_f, text="OP TIME", font=("Consolas", 7, "bold"),
                 bg=C["bg2"], fg=C["txt2"]).pack()
        tk.Label(timer_f, textvariable=self._timer_var,
                 font=("Consolas", 11, "bold"), bg=C["bg2"], fg=C["amber"]).pack()
        tk.Button(timer_f, text="▶", font=("Consolas", 8), bg=C["amber"],
                  fg="white", relief=tk.FLAT, bd=0, padx=5, cursor="hand2",
                  command=self._toggle_timer).pack(side=tk.LEFT)

        tk.Frame(self, bg=C["cyan"], height=3).pack(fill=tk.X)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

    # ══════════════════════════════════════════════════════════════
    #  LEFT SIDEBAR
    # ══════════════════════════════════════════════════════════════

    def _build_sidebar(self):
        p = PATIENT

        banner = tk.Frame(self._left, bg=C["cyan"])
        banner.pack(fill=tk.X, pady=(8, 0))

        hdr_strip = tk.Frame(banner, bg=C["cyan"])
        hdr_strip.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(hdr_strip, text="PATIENT", font=("Consolas", 7, "bold"),
                 bg=C["cyan"], fg="#a8d8f0").pack(side=tk.LEFT)
        tk.Label(hdr_strip, text=p["id"], font=("Consolas", 7),
                 bg=C["cyan"], fg="#a8d8f0").pack(side=tk.RIGHT)

        tk.Label(banner, text=p["name"],
                 font=("Consolas", 14, "bold"), bg=C["cyan"], fg="white").pack(padx=10)

        info_card = tk.Frame(banner, bg=C["bg2"])
        info_card.pack(fill=tk.X, padx=6, pady=(6, 0))

        for k, v in [("Age/Sex", f"{p['age']} / {p['sex']}"),
                     ("Weight",  f"{p['weight']} kg"),
                     ("BMI",     f"{p['bmi']}"),
                     ("ASA",     f"Class {p['asa']}"),
                     ("Blood",   p["blood_type"])]:
            r = tk.Frame(info_card, bg=C["bg2"])
            r.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(r, text=k, font=("Consolas", 8), bg=C["bg2"],
                     fg=C["txt2"], width=9, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(r, text=str(v), font=("Consolas", 8, "bold"),
                     bg=C["bg2"], fg=C["txt0"]).pack(side=tk.RIGHT)

        tk.Frame(info_card, bg=C["border"], height=1).pack(fill=tk.X, padx=8, pady=4)
        tk.Label(info_card, text=p["procedure"],
                 font=("Consolas", 8, "bold"), bg=C["bg2"],
                 fg=C["violet"], wraplength=200).pack(padx=8, pady=(0, 6))

        allergy_f = tk.Frame(banner, bg=C["red"])
        allergy_f.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Label(allergy_f, text=f"⚠  ALLERGY: {p['allergies']}",
                 font=("Consolas", 8, "bold"), bg=C["red"], fg="white").pack(pady=5)

        sec_header(self._left, "ROBOT STATUS", C["cyan"])
        rs = card(self._left)
        rs.pack(fill=tk.X, pady=(0, 4))

        self._robot_status_items = {}
        for label, val, col in [
            ("Calibration",  "✔ VERIFIED",  C["green"]),
            ("Joint Limits", "✔ NOMINAL",   C["green"]),
            ("Force Sensor", "✔ ACTIVE",    C["green"]),
            ("Sterility",    "✔ CONFIRMED", C["green"]),
            ("Safety Sys.",  "✔ ARMED",     C["green"]),
        ]:
            r = tk.Frame(rs, bg=C["bg2"])
            r.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(r, text=label, font=("Consolas", 8),
                     bg=C["bg2"], fg=C["txt1"], anchor=tk.W).pack(side=tk.LEFT)
            vv = tk.StringVar(value=val)
            tk.Label(r, textvariable=vv, font=("Consolas", 8, "bold"),
                     bg=C["bg2"], fg=col).pack(side=tk.RIGHT)
            self._robot_status_items[label] = vv
        tk.Frame(rs, height=4, bg=C["bg2"]).pack()

        sec_header(self._left, "END EFFECTOR", C["teal"])
        ee_card = card(self._left)
        ee_card.pack(fill=tk.X, pady=(0, 4))
        self.ee_vars = {}
        for ax in ("X", "Y", "Z"):
            r = tk.Frame(ee_card, bg=C["bg2"])
            r.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(r, text=f"{ax} :", font=("Consolas", 9, "bold"),
                     bg=C["bg2"], fg=C["txt2"]).pack(side=tk.LEFT)
            v = tk.StringVar(value="0.0000 m")
            tk.Label(r, textvariable=v, font=("Consolas", 11, "bold"),
                     bg=C["bg2"], fg=C["teal"]).pack(side=tk.RIGHT)
            self.ee_vars[ax] = v

        r2 = tk.Frame(ee_card, bg=C["bg2"])
        r2.pack(fill=tk.X, padx=10, pady=(0, 6))
        tk.Label(r2, text="REACH :", font=("Consolas", 9, "bold"),
                 bg=C["bg2"], fg=C["txt2"]).pack(side=tk.LEFT)
        self._reach_var = tk.StringVar(value="0.0000 m")
        tk.Label(r2, textvariable=self._reach_var,
                 font=("Consolas", 11, "bold"), bg=C["bg2"], fg=C["cyan"]).pack(side=tk.RIGHT)

        self._prox_var = tk.StringVar(value="")
        self._prox_lbl = tk.Label(self._left, textvariable=self._prox_var,
                                  font=("Consolas", 8, "bold"), bg=C["red_bg"],
                                  fg=C["red"], wraplength=210)
        self._prox_lbl.pack(fill=tk.X, pady=2)

    # ══════════════════════════════════════════════════════════════
    #  WORKFLOW TAB BAR  (PRE-OP / INTRA-OP / POST-OP)
    # ══════════════════════════════════════════════════════════════

    def _build_workflow_tab_bar(self, parent):
        """Build the top-level workflow tabs: PRE-OP, INTRA-OP, POST-OP."""
        self._workflow_tabs = ["PRE-OP", "INTRA-OP", "POST-OP"]
        self._workflow_colors = {
            "PRE-OP":   C["violet"],
            "INTRA-OP": C["cyan"],
            "POST-OP":  C["teal"],
        }
        self._active_workflow = tk.StringVar(value="INTRA-OP")

        wf_bar = tk.Frame(parent, bg=C["bg1"], height=44)
        wf_bar.pack(fill=tk.X)
        wf_bar.pack_propagate(False)

        # Left accent bar
        tk.Frame(wf_bar, bg=C["cyan"], width=4).pack(side=tk.LEFT, fill=tk.Y)

        self._wf_btns = {}
        for tab in self._workflow_tabs:
            col = self._workflow_colors[tab]
            b = tk.Button(wf_bar,
                          text=f"  {tab}  ",
                          font=("Consolas", 11, "bold"),
                          bg=C["bg2"], fg=C["txt2"],
                          activebackground=col, activeforeground="white",
                          relief=tk.FLAT, bd=0, padx=18, pady=10,
                          cursor="hand2",
                          command=lambda t=tab: self._switch_workflow(t))
            b.pack(side=tk.LEFT, padx=2)
            self._wf_btns[tab] = b

        # Alert badge (lives in the workflow bar, right side)
        self._tab_alert_var = tk.StringVar(value="")
        self._tab_alert_lbl = tk.Label(wf_bar, textvariable=self._tab_alert_var,
                                       font=("Consolas", 8, "bold"),
                                       bg=C["red"], fg="white", padx=6)

        self._wf_bar = wf_bar

    # ══════════════════════════════════════════════════════════════
    #  INTRA-OP SUB-TAB BAR
    # ══════════════════════════════════════════════════════════════

    def _build_intraop_sub_bar(self, parent):
        """Build the INTRA-OP sub-tabs: LIVE CONTROL, LIVE VIDEO, ALERTS, PATIENT VITALS."""
        self._intraop_subtabs = ["LIVE CONTROL", "LIVE VIDEO", "ALERTS", "PATIENT VITALS"]
        self._active_subtab = tk.StringVar(value="LIVE CONTROL")

        self._sub_bar = tk.Frame(parent, bg=C["bg2"], height=36)
        self._sub_bar.pack_propagate(False)
        # Will be shown/hidden by _switch_workflow

        tk.Frame(self._sub_bar, bg=C["cyan"], width=4).pack(side=tk.LEFT, fill=tk.Y)

        self._sub_btns = {}
        for st in self._intraop_subtabs:
            b = tk.Button(self._sub_bar,
                          text=f"  {st}  ",
                          font=("Consolas", 9, "bold"),
                          bg=C["bg2"], fg=C["txt2"],
                          activebackground=C["cyan_bg"], activeforeground=C["cyan"],
                          relief=tk.FLAT, bd=0, padx=8, pady=6,
                          cursor="hand2",
                          command=lambda t=st: self._switch_subtab(t))
            b.pack(side=tk.LEFT)
            self._sub_btns[st] = b

        self._sub_bar_separator = tk.Frame(parent, bg=C["border"], height=1)
        # Will be shown/hidden by _switch_workflow

    # ══════════════════════════════════════════════════════════════
    #  WORKFLOW TAB SWITCHING
    # ══════════════════════════════════════════════════════════════

    def _switch_workflow(self, workflow):
        """Switch between PRE-OP, INTRA-OP, POST-OP workflow tabs."""
        self._active_workflow.set(workflow)
        self._op_phase.set(workflow)

        # Style workflow buttons
        for tab, btn in self._wf_btns.items():
            active = tab == workflow
            col = self._workflow_colors[tab]
            btn.configure(bg=col if active else C["bg2"],
                          fg="white" if active else C["txt2"])

        # Show/hide INTRA-OP sub-tab bar
        if workflow == "INTRA-OP":
            self._sub_bar.pack(fill=tk.X, after=self._wf_bar)
            self._sub_bar_separator.pack(fill=tk.X, after=self._sub_bar)
            # Restore last active sub-tab
            self._switch_subtab(self._active_subtab.get())
        else:
            self._sub_bar.pack_forget()
            self._sub_bar_separator.pack_forget()
            # Hide all tab content, then show the workflow page
            for t, frame in self._tabs.items():
                frame.pack_forget()
            if workflow == "PRE-OP":
                self._tabs["PRE-OP"].pack(fill=tk.BOTH, expand=True)
                self._left.pack_forget()
                self._right.pack_forget()
            elif workflow == "POST-OP":
                self._tabs["POST-OP"].pack(fill=tk.BOTH, expand=True)
                self._left.pack_forget()
                self._right.pack_forget()

    def _switch_subtab(self, subtab):
        """Switch between INTRA-OP sub-tabs."""
        self._active_subtab.set(subtab)
        self._active_tab.set(subtab)

        # Style sub-buttons
        for st, b in self._sub_btns.items():
            active = st == subtab
            b.configure(bg=C["cyan_bg"] if active else C["bg2"],
                        fg=C["cyan"]    if active else C["txt2"])

        # Show/hide content frames
        for t, frame in self._tabs.items():
            if t == subtab:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()

        # Sidebar visibility
        if subtab == "LIVE VIDEO":
            self._left.pack_forget()
            self._right.pack_forget()
        elif subtab == "PATIENT VITALS":
            self._left.pack_forget()
            self._right.pack_forget()
        else:
            self._left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6),
                            before=self._center_frame)
            self._right.pack(side=tk.RIGHT, fill=tk.Y)

    # Legacy alias
    def _switch_tab(self, tab):
        if tab in self._intraop_subtabs:
            self._switch_workflow("INTRA-OP")
            self._switch_subtab(tab)
        elif tab in ["PRE-OP", "POST-OP"]:
            self._switch_workflow(tab)

    # ══════════════════════════════════════════════════════════════
    #  ALL TABS
    # ══════════════════════════════════════════════════════════════

    def _build_all_tabs(self):
        self._tabs = {}
        # INTRA-OP sub-tabs
        for tab in ["LIVE CONTROL", "LIVE VIDEO", "ALERTS", "PATIENT VITALS"]:
            f = tk.Frame(self._tab_container, bg=C["bg0"])
            self._tabs[tab] = f

        # Workflow pages (PRE-OP and POST-OP)
        for tab in ["PRE-OP", "POST-OP"]:
            f = tk.Frame(self._tab_container, bg=C["bg0"])
            self._tabs[tab] = f

        self._build_live_control(self._tabs["LIVE CONTROL"])

        # Live Video tab — delegated to LiveVideoTab
        self._live_video = LiveVideoTab(self._tabs["LIVE VIDEO"], self)

        build_preop_workflow(self._tabs["PRE-OP"], self)
        build_alerts_tab(self._tabs["ALERTS"], self)
        build_postop_workflow(self._tabs["POST-OP"], self)

        # Patient Vitals full-screen tab
        self._build_patient_vitals_tab(self._tabs["PATIENT VITALS"])

    # ══════════════════════════════════════════════════════════════
    #  PATIENT VITALS TAB — ICU/OR Monitoring Dashboard
    # ══════════════════════════════════════════════════════════════

    def _build_patient_vitals_tab(self, parent):
        """Full-width Patient Vitals panel — ICU/OR style monitoring dashboard."""

        sec_header(parent, "PATIENT VITALS — LIVE MONITORING", C["green"])

        # ── Top Row: 6 monitoring cards ──────────────────────────
        top_grid = tk.Frame(parent, bg=C["bg0"])
        top_grid.pack(fill=tk.X, padx=8, pady=(8, 4))

        vitals_cfg = [
            ("HR",    "bpm",  C["pink"],   50,   100),
            ("SpO₂",  "%",    C["cyan"],   95,   100),
            ("NIBP",  "mmHg", C["violet"], None, None),
            ("EtCO₂", "mmHg", C["teal"],   30,   45),
            ("RR",    "br/m", C["amber"],  12,   20),
            ("Temp",  "°C",   C["green"],  36,   37.5),
        ]

        self._vitals_tab_sparklines = {}
        for col_idx, (key, unit, color, lo, hi) in enumerate(vitals_cfg):
            col_f = tk.Frame(top_grid, bg=C["bg0"])
            col_f.grid(row=0, column=col_idx, sticky="nsew", padx=4)
            top_grid.columnconfigure(col_idx, weight=1)

            vc = card(col_f)
            vc.pack(fill=tk.BOTH, expand=True)
            inner = tk.Frame(vc, bg=C["bg2"])
            inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

            # Label
            tk.Label(inner, text=key, font=("Consolas", 10, "bold"),
                     bg=C["bg2"], fg=C["txt1"], anchor=tk.W).pack(fill=tk.X)
            # Value
            tk.Label(inner, textvariable=self._vitals_widgets[key]["var"],
                     font=("Consolas", 32, "bold"),
                     bg=C["bg2"], fg=color).pack(pady=(4, 0))
            # Unit
            tk.Label(inner, text=unit, font=("Consolas", 9),
                     bg=C["bg2"], fg=C["txt2"]).pack()
            # Status
            tk.Label(inner, textvariable=self._vitals_widgets[key]["status"],
                     font=("Consolas", 9, "bold"),
                     bg=C["bg2"], fg=C["green"]).pack(pady=(4, 0))
            # Sparkline
            if key in ("HR", "SpO₂", "EtCO₂"):
                sp = Sparkline(inner, color=color, width=200, height=36)
                sp.pack(fill=tk.X, pady=(6, 0))
                self._vitals_tab_sparklines[key] = sp

        # ── Middle Row: Vital Trends (left) + Clinical Status (right) ──
        mid_row = tk.Frame(parent, bg=C["bg0"])
        mid_row.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Left: Vital Trends graph
        trends_frame = tk.Frame(mid_row, bg=C["bg0"])
        trends_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        sec_header(trends_frame, "VITAL TRENDS", C["cyan"])
        trends_card = card(trends_frame)
        trends_card.pack(fill=tk.BOTH, expand=True)

        self._vitals_trend_canvas = tk.Canvas(trends_card, bg=C["bg2"],
                                              highlightthickness=0, height=200)
        self._vitals_trend_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._vitals_trend_canvas.bind("<Configure>", lambda e: self._draw_vitals_trend())

        # Legend
        legend_f = tk.Frame(trends_card, bg=C["bg2"])
        legend_f.pack(fill=tk.X, padx=10, pady=(0, 6))
        for label, color in [("HR", C["pink"]), ("SpO₂", C["cyan"]), ("EtCO₂", C["teal"])]:
            lf = tk.Frame(legend_f, bg=C["bg2"])
            lf.pack(side=tk.LEFT, padx=8)
            tk.Frame(lf, bg=color, width=12, height=3).pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(lf, text=label, font=("Consolas", 8), bg=C["bg2"], fg=color).pack(side=tk.LEFT)

        # Right: Clinical Status
        clinical_frame = tk.Frame(mid_row, bg=C["bg0"], width=380)
        clinical_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
        clinical_frame.pack_propagate(False)

        sec_header(clinical_frame, "CLINICAL STATUS", C["green"])

        self._clinical_status_vars = {}
        clinical_items = [
            ("Hemodynamic Status",  "STABLE",    C["green"],  "BP and HR within normal limits"),
            ("Respiratory Status",  "NORMAL",    C["green"],  "RR and EtCO₂ within range"),
            ("Oxygenation Status",  "ADEQUATE",  C["green"],  "SpO₂ > 95%"),
            ("Temperature Status",  "NORMAL",    C["green"],  "Core temp 36.0–37.5°C"),
        ]
        for title, status, color, desc in clinical_items:
            ci = card(clinical_frame)
            ci.pack(fill=tk.X, pady=3)
            inner = tk.Frame(ci, bg=C["bg2"])
            inner.pack(fill=tk.X, padx=10, pady=8)

            top = tk.Frame(inner, bg=C["bg2"])
            top.pack(fill=tk.X)
            tk.Label(top, text=title, font=("Consolas", 9, "bold"),
                     bg=C["bg2"], fg=C["txt0"], anchor=tk.W).pack(side=tk.LEFT)

            sv = tk.StringVar(value=status)
            sc = tk.StringVar(value=color)
            slbl = tk.Label(top, textvariable=sv, font=("Consolas", 9, "bold"),
                            bg=C["bg2"], fg=color)
            slbl.pack(side=tk.RIGHT)

            tk.Label(inner, text=desc, font=("Consolas", 7),
                     bg=C["bg2"], fg=C["txt2"], anchor=tk.W).pack(fill=tk.X, pady=(2, 0))

            self._clinical_status_vars[title] = {"var": sv, "lbl": slbl}

        # ── Bottom: Vital Events Log ─────────────────────────────
        bottom_frame = tk.Frame(parent, bg=C["bg0"])
        bottom_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

        sec_header(bottom_frame, "VITAL EVENTS LOG", C["amber"])

        log_card = card(bottom_frame)
        log_card.pack(fill=tk.X)

        # Header row
        hdr = tk.Frame(log_card, bg=C["bg3"])
        hdr.pack(fill=tk.X, padx=6, pady=(6, 2))
        for col_text, w in [("TIMESTAMP", 14), ("EVENT", 60), ("SEVERITY", 12)]:
            tk.Label(hdr, text=col_text, font=("Consolas", 8, "bold"),
                     bg=C["bg3"], fg=C["cyan"], width=w, anchor=tk.W).pack(side=tk.LEFT)

        # Scrollable log container
        log_container = tk.Frame(log_card, bg=C["bg2"], height=120)
        log_container.pack(fill=tk.X, padx=6, pady=(0, 6))
        log_container.pack_propagate(False)

        log_sb = tk.Scrollbar(log_container, orient=tk.VERTICAL, bg=C["bg1"], troughcolor=C["bg0"])
        log_sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._vital_log_canvas = tk.Canvas(log_container, bg=C["bg2"],
                                           highlightthickness=0,
                                           yscrollcommand=log_sb.set)
        self._vital_log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_sb.configure(command=self._vital_log_canvas.yview)

        self._vital_log_frame = tk.Frame(self._vital_log_canvas, bg=C["bg2"])
        self._vital_log_canvas.create_window((0, 0), window=self._vital_log_frame,
                                              anchor=tk.NW, tags="frame")
        self._vital_log_frame.bind(
            "<Configure>",
            lambda e: self._vital_log_canvas.configure(scrollregion=self._vital_log_canvas.bbox("all")))
        self._vital_log_canvas.bind(
            "<Configure>",
            lambda e: self._vital_log_canvas.itemconfig("frame", width=e.width))

        # Pre-populate with a few events
        self._vital_events = [
            ("08:14", "Vitals monitoring started — all parameters nominal", "INFO"),
            ("08:31", "HR elevated briefly to 88 bpm — returned to baseline", "WARNING"),
            ("08:33", "SpO₂ stable at 98%", "INFO"),
            ("08:47", "EtCO₂ transient rise to 42 mmHg", "WARNING"),
        ]
        self._draw_vital_log()

    def _draw_vitals_trend(self):
        """Draw multi-line vital signs trend graph on the Patient Vitals tab."""
        c = self._vitals_trend_canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10 or not VITALS.history["hr"]:
            return

        datasets = [
            ("HR",    VITALS.history["hr"],    50, 120, C["pink"]),
            ("SpO₂",  VITALS.history["spo2"],  92, 100, C["cyan"]),
            ("EtCO₂", VITALS.history["etco2"], 28, 50,  C["teal"]),
        ]
        margin_l, margin_r, margin_t, margin_b = 40, 10, 10, 25
        cw = W - margin_l - margin_r
        ch = H - margin_t - margin_b

        # Grid lines
        for i in range(5):
            y = margin_t + i * ch // 4
            c.create_line(margin_l, y, W - margin_r, y, fill=C["bg3"], dash=(2, 4))

        # Time axis labels
        data_len = max(len(d) for _, d, _, _, _ in datasets)
        if data_len > 1:
            for i in range(0, data_len, max(1, data_len // 6)):
                x = margin_l + i / max(data_len - 1, 1) * cw
                c.create_text(x, H - 6, text=f"-{data_len - i}s",
                              fill=C["txt2"], font=("Consolas", 6))

        for label, data, lo, hi, color in datasets:
            if len(data) < 2:
                continue
            rng = hi - lo or 1
            pts = []
            for i, v in enumerate(data):
                x = margin_l + i / max(len(data) - 1, 1) * cw
                y = margin_t + (1 - (v - lo) / rng) * ch
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(*pts, fill=color, width=2, smooth=True)
            c.create_text(W - margin_r - 4, pts[-1], text=label,
                          fill=color, font=("Consolas", 7), anchor=tk.E)

        # Axes
        c.create_line(margin_l, margin_t, margin_l, H - margin_b, fill=C["border2"], width=1)
        c.create_line(margin_l, H - margin_b, W - margin_r, H - margin_b, fill=C["border2"], width=1)

    def _draw_vital_log(self):
        """Redraw the vital events log table."""
        for w in self._vital_log_frame.winfo_children():
            w.destroy()

        sev_colors = {"INFO": C["cyan"], "WARNING": C["amber"], "CRITICAL": C["red"]}
        for timestamp, event, severity in self._vital_events:
            r = tk.Frame(self._vital_log_frame, bg=C["bg2"])
            r.pack(fill=tk.X, pady=1)

            col = sev_colors.get(severity, C["cyan"])
            tk.Frame(r, bg=col, width=3).pack(side=tk.LEFT, fill=tk.Y)
            tk.Label(r, text=timestamp, font=("Consolas", 8),
                     bg=C["bg2"], fg=C["txt2"], width=14, anchor=tk.W).pack(side=tk.LEFT, padx=(4, 0))
            tk.Label(r, text=event, font=("Consolas", 8),
                     bg=C["bg2"], fg=C["txt0"], anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(r, text=severity, font=("Consolas", 8, "bold"),
                     bg=C["bg2"], fg=col, width=12, anchor=tk.W).pack(side=tk.RIGHT)

    def _add_vital_event(self, event, severity="INFO"):
        """Add a vital event to the log."""
        t = datetime.now().strftime("%H:%M:%S")
        self._vital_events.insert(0, (t, event, severity))
        if len(self._vital_events) > 50:
            self._vital_events.pop()
        try:
            self._draw_vital_log()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════
    #  LIVE CONTROL TAB
    # ══════════════════════════════════════════════════════════════

    def _build_live_control(self, parent):
        row = tk.Frame(parent, bg=C["bg0"])
        row.pack(fill=tk.BOTH, expand=True)

        view_col = tk.Frame(row, bg=C["bg0"])
        view_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        vhdr = tk.Frame(view_col, bg=C["bg2"],
                        highlightthickness=1, highlightbackground=C["border"], height=38)
        vhdr.pack(fill=tk.X)
        vhdr.pack_propagate(False)
        tk.Frame(vhdr, bg=C["teal"], width=4).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(vhdr, text="  3D SURGICAL WORKSPACE  //  Drag · Scroll to navigate",
                 font=("Consolas", 9), bg=C["bg2"], fg=C["txt1"]).pack(side=tk.LEFT, pady=6)

        self._anim_btn = tk.Button(vhdr, text="▶  SIMULATE",
                                   font=("Consolas", 8, "bold"),
                                   bg=C["amber"], fg="white",
                                   activebackground=C["teal"], activeforeground="white",
                                   relief=tk.FLAT, bd=0, padx=10, pady=5,
                                   cursor="hand2", command=self._toggle_anim)
        self._anim_btn.pack(side=tk.RIGHT, padx=8, pady=4)

        self._zone_var = tk.BooleanVar(value=True)
        tk.Checkbutton(vhdr, text="Surgical Zones",
                       variable=self._zone_var,
                       font=("Consolas", 8), bg=C["bg2"], fg=C["txt1"],
                       selectcolor=C["bg3"], activebackground=C["bg2"],
                       command=self._draw_3d).pack(side=tk.RIGHT, padx=4)

        self.canvas = tk.Canvas(view_col, bg=C["bg3"],
                                highlightthickness=1, highlightbackground=C["border"],
                                cursor="fleur")
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.canvas.bind("<ButtonPress-1>",   self._ds)
        self.canvas.bind("<B1-Motion>",       self._dm)
        self.canvas.bind("<ButtonRelease-1>", self._de)
        self.canvas.bind("<MouseWheel>",      self._sc)
        self.canvas.bind("<Button-4>",        self._sc)
        self.canvas.bind("<Button-5>",        self._sc)
        self.canvas.bind("<Configure>",       lambda e: self._update_all())

        ctrl = tk.Frame(row, bg=C["bg0"], width=240)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)
        ctrl.pack_propagate(False)
        self._build_joint_controls(ctrl)

    def _build_joint_controls(self, parent):
        sec_header(parent, "KINEMATIC CHAIN", C["cyan"])
        tk.Label(parent, text="Click link to edit D-H parameters",
                 font=("Consolas", 7), bg=C["bg0"], fg=C["txt2"]).pack(anchor=tk.W, padx=4)

        lf = card(parent)
        lf.pack(fill=tk.X, pady=(4, 8))
        self.link_btns = []
        for i, p in enumerate(self.dh_params):
            row = tk.Frame(lf, bg=C["bg2"])
            row.pack(fill=tk.X)
            tk.Frame(row, bg=p["color"], width=4).pack(side=tk.LEFT, fill=tk.Y)
            b = tk.Button(row, text=f"  {p['name'].upper()}",
                          font=("Consolas", 9, "bold"),
                          bg=C["bg2"], fg=C["txt0"],
                          activebackground=C["cyan_bg"], activeforeground=p["color"],
                          relief=tk.FLAT, bd=0, anchor=tk.W,
                          padx=8, pady=11, cursor="hand2",
                          command=lambda idx=i: self._open_popup(idx))
            b.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(row, text="✎", font=("Consolas", 9),
                     bg=C["bg2"], fg=C["txt2"], padx=8).pack(side=tk.RIGHT)
            tk.Frame(lf, bg=C["border"], height=1).pack(fill=tk.X)
            self.link_btns.append(b)

        sec_header(parent, "JOINT ANGLES", C["amber"])
        self.sliders = []
        for i, p in enumerate(self.dh_params):
            color = p["color"]
            f = card(parent)
            f.pack(fill=tk.X, pady=3)
            hr = tk.Frame(f, bg=C["bg2"])
            hr.pack(fill=tk.X, padx=8, pady=(6, 2))
            dot = tk.Canvas(hr, width=8, height=8, bg=C["bg2"], highlightthickness=0)
            dot.pack(side=tk.LEFT)
            dot.create_oval(1, 1, 7, 7, fill=color, outline="")
            tk.Label(hr, text=f" {p['name']}",
                     font=("Consolas", 8, "bold"), bg=C["bg2"], fg=C["txt0"]).pack(side=tk.LEFT)
            vv = tk.StringVar(value="0.0°")
            tk.Label(hr, textvariable=vv, font=("Consolas", 9, "bold"),
                     bg=C["bg2"], fg=color).pack(side=tk.RIGHT)
            s = tk.Scale(f, from_=-180, to=180, orient=tk.HORIZONTAL,
                         bg=C["bg2"], fg=C["txt0"], troughcolor=C["bg3"],
                         activebackground=color, highlightthickness=0,
                         bd=0, sliderrelief=tk.FLAT, font=("Consolas", 7),
                         command=lambda v, idx=i, vvar=vv: self._on_slider(idx, v, vvar))
            s.pack(fill=tk.X, padx=8, pady=(0, 6))
            s.set(p["theta"])
            self.sliders.append((s, vv))

        sec_header(parent, "CONFIGURATION", C["violet"])

        # D-H table
        tc = card(parent)
        tc.pack(fill=tk.X, pady=(0, 4))
        cols   = ["Link", "a (m)", "α (°)", "d (m)", "θ (°)"]
        widths = [6, 7, 6, 7, 6]
        hr = tk.Frame(tc, bg=C["bg3"])
        hr.pack(fill=tk.X, padx=4, pady=(4, 2))
        for col_text, w in zip(cols, widths):
            tk.Label(hr, text=col_text, font=("Consolas", 7, "bold"),
                     bg=C["bg3"], fg=C["cyan"], width=w).pack(side=tk.LEFT)

        self._dh_table_rows = []
        for _ in range(3):
            r = tk.Frame(tc, bg=C["bg2"])
            r.pack(fill=tk.X, padx=4, pady=1)
            cells = []
            for w in widths:
                var = tk.StringVar()
                tk.Label(r, textvariable=var, font=("Consolas", 7),
                         bg=C["bg2"], fg=C["txt1"], width=w).pack(side=tk.LEFT)
                cells.append(var)
            self._dh_table_rows.append(cells)
        tk.Frame(tc, height=4, bg=C["bg2"]).pack()

        tk.Button(parent, text="LOAD JSON CONFIG",
                  font=("Consolas", 8, "bold"), bg=C["violet"], fg="white",
                  activebackground=C["cyan"], activeforeground="white",
                  relief=tk.FLAT, bd=0, padx=10, pady=9, cursor="hand2",
                  command=self._load_json).pack(fill=tk.X, pady=2)
        tk.Button(parent, text="EXPORT JSON",
                  font=("Consolas", 8, "bold"), bg=C["bg3"], fg=C["txt0"],
                  activebackground=C["border"], relief=tk.FLAT, bd=0,
                  padx=10, pady=9, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=self._export_json).pack(fill=tk.X, pady=2)
        tk.Button(parent, text="RESET",
                  font=("Consolas", 8, "bold"), bg=C["bg3"], fg=C["amber"],
                  activebackground=C["amber_bg"], relief=tk.FLAT, bd=0,
                  padx=10, pady=9, cursor="hand2",
                  highlightthickness=1, highlightbackground=C["border"],
                  command=self._reset).pack(fill=tk.X, pady=2)

    # ══════════════════════════════════════════════════════════════
    #  RIGHT SIDEBAR — VITALS + LIVE ALERTS
    # ══════════════════════════════════════════════════════════════

    def _build_right_sidebar(self):
        sec_header(self._right, "PATIENT VITALS", C["green"])

        self._vitals_widgets = {}
        vitals_cfg = [
            ("HR",    "bpm",  C["pink"],   50,   100),
            ("SpO₂",  "%",    C["cyan"],   95,   100),
            ("NIBP",  "mmHg", C["violet"], None, None),
            ("EtCO₂", "mmHg", C["teal"],   30,   45),
            ("RR",    "br/m", C["amber"],  12,   20),
            ("Temp",  "°C",   C["green"],  36,   37.5),
        ]
        for key, unit, color, lo, hi in vitals_cfg:
            vc = card(self._right)
            vc.pack(fill=tk.X, pady=2)
            inner = tk.Frame(vc, bg=C["bg2"])
            inner.pack(fill=tk.X, padx=8, pady=5)

            top = tk.Frame(inner, bg=C["bg2"])
            top.pack(fill=tk.X)
            tk.Label(top, text=key, font=("Consolas", 8, "bold"),
                     bg=C["bg2"], fg=C["txt1"], width=6, anchor=tk.W).pack(side=tk.LEFT)
            vv = tk.StringVar(value="---")
            tk.Label(top, textvariable=vv, font=("Consolas", 13, "bold"),
                     bg=C["bg2"], fg=color).pack(side=tk.LEFT)
            tk.Label(top, text=f" {unit}", font=("Consolas", 8),
                     bg=C["bg2"], fg=C["txt2"]).pack(side=tk.LEFT)

            status_v   = tk.StringVar(value="")
            status_lbl = tk.Label(top, textvariable=status_v,
                                  font=("Consolas", 7, "bold"),
                                  bg=C["bg2"], fg=C["green"])
            status_lbl.pack(side=tk.RIGHT)

            sp = None
            if key in ("HR", "SpO₂", "EtCO₂"):
                sp = Sparkline(inner, color=color, width=180, height=24)
                sp.pack(fill=tk.X, pady=(3, 0))

            self._vitals_widgets[key] = {
                "var":        vv,
                "status":     status_v,
                "status_lbl": status_lbl,
                "spark":      sp,
                "lo":         lo,
                "hi":         hi,
                "color":      color,
            }

        sec_header(self._right, "LIVE ALERTS", C["red"])
        self._live_alert_frame = tk.Frame(self._right, bg=C["bg0"])
        self._live_alert_frame.pack(fill=tk.X)
        self._draw_live_alerts()

        sec_header(self._right, "QUICK ACTIONS", C["amber"])
        for txt, col, cmd in [
            ("🛑  EMERGENCY STOP",  C["red"],    self._estop),
            ("⚠  TRIGGER ALERT",   C["amber"],  self._manual_alert),
            ("✔  ACK ALL ALERTS",  C["green"],  self._ack_all),
        ]:
            tk.Button(self._right, text=txt,
                      font=("Consolas", 9, "bold"), bg=col, fg="white",
                      activebackground=C["border2"], activeforeground=C["txt0"],
                      relief=tk.FLAT, bd=0, padx=10, pady=8, cursor="hand2",
                      command=cmd).pack(fill=tk.X, pady=2)

    # ══════════════════════════════════════════════════════════════
    #  VITALS DISPLAY
    # ══════════════════════════════════════════════════════════════

    def _vitals_tick(self):
        self.after(0, self._update_vitals_display)

    def _update_vitals_display(self):
        v = VITALS
        mapping = {
            "HR":    (f"{v.hr:.0f}",   v.hr,    50,  100),
            "SpO₂":  (f"{v.spo2:.1f}", v.spo2,  95,  100),
            "NIBP":  (f"{v.nibp_s:.0f}/{v.nibp_d:.0f}", None, None, None),
            "EtCO₂": (f"{v.etco2:.1f}",v.etco2, 30,  45),
            "RR":    (f"{v.rr:.0f}",   v.rr,    12,  20),
            "Temp":  (f"{v.temp:.1f}", v.temp,  36,  37.5),
        }
        spark_data = {"HR": v.history["hr"], "SpO₂": v.history["spo2"], "EtCO₂": v.history["etco2"]}

        for key, (disp, val, lo, hi) in mapping.items():
            w = self._vitals_widgets.get(key)
            if not w:
                continue
            w["var"].set(disp)
            if val is not None and lo is not None:
                oor = val < lo or val > hi
                w["status"].set("⚠ OOR" if oor else "✔ OK")
                w["status_lbl"].configure(fg=C["red"] if oor else C["green"])

                # Log OOR events
                if oor and random.random() < 0.02:
                    self._add_vital_event(
                        f"{key} out of range: {disp}", "WARNING")

            if key in spark_data and w["spark"]:
                w["spark"].update_data(spark_data[key])

        # Update Patient Vitals tab sparklines
        for key in ("HR", "SpO₂", "EtCO₂"):
            sp = self._vitals_tab_sparklines.get(key)
            if sp and key in spark_data:
                sp.update_data(spark_data[key])

        # Update clinical status indicators
        self._update_clinical_status(v)

        # Update vitals trend graph
        try:
            self._draw_vitals_trend()
        except Exception:
            pass

        # Update post-op chart
        try:
            self._draw_postop_chart()
        except Exception:
            pass

    def _update_clinical_status(self, v):
        """Update the clinical status cards on the Patient Vitals tab."""
        try:
            cs = self._clinical_status_vars
        except AttributeError:
            return

        # Hemodynamic
        hemo = cs.get("Hemodynamic Status")
        if hemo:
            if v.hr < 50 or v.hr > 100 or v.nibp_s > 160 or v.nibp_s < 90:
                hemo["var"].set("⚠ ABNORMAL")
                hemo["lbl"].configure(fg=C["amber"])
            else:
                hemo["var"].set("STABLE")
                hemo["lbl"].configure(fg=C["green"])

        # Respiratory
        resp = cs.get("Respiratory Status")
        if resp:
            if v.rr < 10 or v.rr > 22 or v.etco2 > 50 or v.etco2 < 28:
                resp["var"].set("⚠ ABNORMAL")
                resp["lbl"].configure(fg=C["amber"])
            else:
                resp["var"].set("NORMAL")
                resp["lbl"].configure(fg=C["green"])

        # Oxygenation
        oxy = cs.get("Oxygenation Status")
        if oxy:
            if v.spo2 < 95:
                oxy["var"].set("⚠ LOW")
                oxy["lbl"].configure(fg=C["red"])
            else:
                oxy["var"].set("ADEQUATE")
                oxy["lbl"].configure(fg=C["green"])

        # Temperature
        temp = cs.get("Temperature Status")
        if temp:
            if v.temp < 36 or v.temp > 37.5:
                temp["var"].set("⚠ ABNORMAL")
                temp["lbl"].configure(fg=C["amber"])
            else:
                temp["var"].set("NORMAL")
                temp["lbl"].configure(fg=C["green"])

    # ══════════════════════════════════════════════════════════════
    #  SYNTHETIC DRAWINGS (CT, Workspace, Post-op chart)
    # ══════════════════════════════════════════════════════════════

    def _draw_ct(self):
        c = self._ct_canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        cx, cy = W // 2, H // 2
        c.create_oval(cx - 80, cy - 95, cx + 80, cy + 95, fill="#ddeef8", outline="#a0bcd4", width=2)
        c.create_oval(cx - 60, cy - 45, cx + 20, cy + 20, fill="#c8e8c0", outline="#7ab870", width=1)
        c.create_text(cx - 25, cy - 15, text="LIVER", fill="#3a7a30", font=("Consolas", 7, "bold"))
        c.create_oval(cx + 5, cy - 10, cx + 30, cy + 10, fill="#d0f0d8", outline=C["green"], width=2)
        c.create_text(cx + 18, cy, text="GB", fill=C["green"], font=("Consolas", 6, "bold"))
        c.create_oval(cx + 8, cy - 7, cx + 27, cy + 7, outline=C["cyan"], width=1, dash=(3, 2))
        c.create_oval(cx - 12, cy + 50, cx + 12, cy + 75, fill="#d8d8f0", outline="#8888c0", width=2)
        c.create_text(cx, cy + 62, text="SP", fill="#6060a0", font=("Consolas", 6))
        c.create_line(W - 10, 10, cx + 18, cy, fill=C["cyan"], width=1, dash=(4, 2))
        c.create_oval(W - 14, 6, W - 6, 14, fill=C["cyan"], outline="")
        c.create_text(W - 20, 20, text="TOOL", fill=C["cyan"], font=("Consolas", 6), anchor=tk.E)
        c.create_line(cx + 18, cy - 18, cx + 18, cy + 18, fill=C["green"], dash=(2, 2))
        c.create_line(cx + 4, cy, cx + 32, cy, fill=C["green"], dash=(2, 2))
        c.create_line(10, H - 12, 60, H - 12, fill=C["txt2"], width=2)
        c.create_text(35, H - 20, text="5 cm", fill=C["txt2"], font=("Consolas", 6))
        c.create_text(cx, 10, text="AXIAL  //  L3 LEVEL  //  PRE-OP",
                      fill=C["txt2"], font=("Consolas", 7))

    def _draw_mri(self):
        """Draw a simplified MRI sagittal view."""
        c = self._mri_canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        cx, cy = W // 2, H // 2

        # Body outline (sagittal)
        c.create_oval(cx - 70, cy - 100, cx + 70, cy + 100, fill="#e0e8f4", outline="#a0b8d0", width=2)

        # Spine
        for i in range(8):
            y = cy - 60 + i * 18
            c.create_rectangle(cx + 30, y, cx + 42, y + 12, fill="#d8d0c8", outline="#b0a898", width=1)

        # Organs
        c.create_oval(cx - 50, cy - 40, cx + 10, cy + 10, fill="#c8e8c0", outline="#7ab870", width=1)
        c.create_text(cx - 20, cy - 15, text="LIVER", fill="#3a7a30", font=("Consolas", 6, "bold"))

        c.create_oval(cx - 15, cy + 5, cx + 15, cy + 30, fill="#d0f0d8", outline=C["green"], width=2)
        c.create_text(cx, cy + 18, text="GB", fill=C["green"], font=("Consolas", 6, "bold"))

        # Entry path
        c.create_line(cx - 60, cy - 80, cx, cy + 18, fill=C["cyan"], width=1, dash=(4, 2))
        c.create_oval(cx - 64, cy - 84, cx - 56, cy - 76, fill=C["cyan"], outline="")
        c.create_text(cx - 50, cy - 90, text="ENTRY", fill=C["cyan"], font=("Consolas", 6))

        c.create_text(cx, 10, text="SAGITTAL  //  MRI PREVIEW",
                      fill=C["txt2"], font=("Consolas", 7))
        c.create_line(10, H - 12, 60, H - 12, fill=C["txt2"], width=2)
        c.create_text(35, H - 20, text="5 cm", fill=C["txt2"], font=("Consolas", 6))

    def _draw_workspace(self):
        c = self._ws_canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        max_reach = sum(p["a"] for p in self.dh_params) + 0.1
        scale     = min(W, H) * 0.38 / (max_reach or 0.5)
        ox, oy    = W // 2, H - 20

        for r, col in [(sum(p["a"] for p in self.dh_params) * scale, C["cyan"]),
                       ((self.dh_params[0]["a"] + self.dh_params[1]["a"]) * scale, C["violet"])]:
            if r > 4:
                c.create_arc(ox - r, oy - r, ox + r, oy + r,
                             start=0, extent=180, outline=col,
                             style=tk.ARC, width=1, dash=(4, 4))

        for zone in SURGICAL_ZONES:
            zx = ox + zone["x"] * scale
            zy = oy - zone["z"] * scale
            zr = zone["r"] * scale
            c.create_oval(zx - zr, zy - zr, zx + zr, zy + zr,
                          outline=zone["color"], fill="", width=2, dash=(3, 2))
            c.create_text(zx, zy - zr - 6, text=zone["label"],
                          fill=zone["color"], font=("Consolas", 6))

        transforms = fk(self.dh_params)
        positions  = joint_pos(transforms)
        prev_x, prev_y = ox, oy
        link_colors = [C["link1"], C["link2"], C["link3"]]
        for i in range(1, len(positions)):
            pos = positions[i]
            nx  = ox + pos[0] * scale
            ny  = oy - pos[2] * scale
            c.create_line(prev_x, prev_y, nx, ny, fill=link_colors[min(i - 1, 2)], width=3)
            c.create_oval(nx - 5, ny - 5, nx + 5, ny + 5, fill=link_colors[min(i - 1, 2)], outline="")
            prev_x, prev_y = nx, ny

        c.create_oval(prev_x - 7, prev_y - 7, prev_x + 7, prev_y + 7, fill=C["ee"], outline="white")
        c.create_text(ox, 10, text="REACHABILITY  //  XZ PLANE", fill=C["txt2"], font=("Consolas", 7))
        for i, (lab, col) in enumerate([("Link 1", C["link1"]), ("Link 2", C["link2"]),
                                        ("Link 3", C["link3"]), ("EE", C["ee"])]):
            c.create_rectangle(8, H - 14 - i * 14, 18, H - 4 - i * 14, fill=col, outline="")
            c.create_text(22, H - 9 - i * 14, text=lab, fill=col, font=("Consolas", 6), anchor=tk.W)

    def _draw_postop_chart(self):
        c = self._postop_vitals_canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10 or not VITALS.history["hr"]:
            return
        datasets = [
            ("HR",    VITALS.history["hr"],    50, 120, C["pink"]),
            ("SpO₂",  VITALS.history["spo2"],  92, 100, C["cyan"]),
            ("EtCO₂", VITALS.history["etco2"], 28, 50,  C["teal"]),
        ]
        margin = 30
        cw = W - 2 * margin
        ch = H - margin - 8
        for label, data, lo, hi, color in datasets:
            if len(data) < 2:
                continue
            rng = hi - lo or 1
            pts = []
            for i, v in enumerate(data):
                x = margin + i / max(len(data) - 1, 1) * cw
                y = margin + (1 - (v - lo) / rng) * ch
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(*pts, fill=color, width=1.5, smooth=True)
            c.create_text(W - 4, pts[-1], text=label, fill=color, font=("Consolas", 7), anchor=tk.E)
        c.create_line(margin, 8, margin, H - margin, fill=C["border2"], width=1)
        c.create_line(margin, H - margin, W - 4, H - margin, fill=C["border2"], width=1)
        c.create_text(4, H // 2, text="VITALS", fill=C["txt2"], font=("Consolas", 6), angle=90, anchor=tk.CENTER)

    # ══════════════════════════════════════════════════════════════
    #  3D VIEWPORT
    # ══════════════════════════════════════════════════════════════

    def _draw_3d(self, transforms=None, positions=None):
        c = self.canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        self.camera.cx = W / 2
        self.camera.cy = H / 2 + 50

        if transforms is None:
            transforms = fk(self.dh_params)
        if positions is None:
            positions = joint_pos(transforms)

        # Grid
        gs, steps = 0.65, 10
        step = gs / steps
        for i in range(-steps, steps + 1):
            v = i * step
            x1, y1, _ = self.camera.project(-gs, v, 0)
            x2, y2, _ = self.camera.project( gs, v, 0)
            c.create_line(x1, y1, x2, y2, fill=C["grid"])
            x1, y1, _ = self.camera.project(v, -gs, 0)
            x2, y2, _ = self.camera.project(v,  gs, 0)
            c.create_line(x1, y1, x2, y2, fill=C["grid"])

        # Axes
        for axis, color, lbl_txt in [((0.2, 0, 0), "#ff4040", "X"),
                                      ((0, 0.2, 0), "#40ff40", "Y"),
                                      ((0, 0, 0.2), "#4080ff", "Z")]:
            ox, oy, _ = self.camera.project(0, 0, 0)
            ax, ay, _ = self.camera.project(*axis)
            c.create_line(ox, oy, ax, ay, fill=color, width=2, arrow=tk.LAST)
            c.create_text(ax, ay - 8, text=lbl_txt, fill=color, font=("Consolas", 7, "bold"))

        # Surgical zones
        if self._zone_var.get():
            for zone in SURGICAL_ZONES:
                zx, zy, _ = self.camera.project(zone["x"], zone["y"], zone["z"])
                zr = zone["r"] * self.camera.scale * 0.5
                c.create_oval(zx - zr, zy - zr, zx + zr, zy + zr,
                              outline=zone["color"], fill="", width=1, dash=(4, 3))
                c.create_text(zx, zy - zr - 8, text=zone["label"],
                              fill=zone["color"], font=("Consolas", 7))

        # Links
        for i in range(len(positions) - 1):
            x0, y0, _ = self.camera.project(*positions[i])
            x1, y1, _ = self.camera.project(*positions[i + 1])
            color = self.dh_params[i]["color"]
            c.create_line(x0, y0, x1, y1, fill=color, width=10, capstyle=tk.ROUND, stipple="gray50")
            c.create_line(x0, y0, x1, y1, fill=color, width=5, capstyle=tk.ROUND)
            c.create_text((x0 + x1) / 2 + 12, (y0 + y1) / 2 - 10,
                          text=f"L{i + 1}", fill=color, font=("Consolas", 8, "bold"))

        # Joints
        for i, pos in enumerate(positions):
            px, py, _ = self.camera.project(*pos)
            if i == 0:
                c.create_rectangle(px - 18, py + 4, px + 18, py + 12, fill=C["border2"], outline=C["txt1"])
                c.create_rectangle(px - 11, py - 3, px + 11, py + 4,  fill=C["border"], outline=C["txt1"])
                c.create_oval(px - 8, py - 8, px + 8, py + 8, fill=C["cyan"], outline="white", width=2)
            elif i == len(positions) - 1:
                r = 12
                c.create_oval(px - r, py - r, px + r, py + r, fill=C["ee"], outline="white", width=2)
                c.create_oval(px - 3, py - 3, px + 3, py + 3, fill="white", outline="")
                c.create_line(px - 20, py, px + 20, py, fill=C["ee"], dash=(3, 3))
                c.create_line(px, py - 20, px, py + 20, fill=C["ee"], dash=(3, 3))
                c.create_text(px + 26, py - 16, text="END EFFECTOR", fill=C["ee"], font=("Consolas", 7, "bold"))
            else:
                col = self.dh_params[i - 1]["color"]
                c.create_oval(px - 9, py - 9, px + 9, py + 9, fill="white", outline=col, width=2)
                c.create_oval(px - 4, py - 4, px + 4, py + 4, fill=col, outline="")

        ee = positions[-1]
        ex, ey, _ = self.camera.project(*ee)
        c.create_text(ex + 34, ey + 22,
                      text=f"({ee[0]:.3f}, {ee[1]:.3f}, {ee[2]:.3f}) m",
                      fill=C["ee"], font=("Consolas", 8), anchor=tk.W)
        c.create_text(10, H - 10,
                      text=f"Az:{self.camera.az:.0f}°  El:{self.camera.el:.0f}°  Zoom:{self.camera.scale:.0f}",
                      fill=C["txt2"], font=("Consolas", 7), anchor=tk.SW)
        for i, p in enumerate(self.dh_params):
            cx2, cy2 = W - 14, 14 + i * 16
            c.create_oval(cx2 - 5, cy2 - 5, cx2 + 5, cy2 + 5, fill=p["color"], outline="")
            c.create_text(cx2 - 10, cy2, text=p["name"], fill=p["color"], font=("Consolas", 7), anchor=tk.E)

        self._check_proximity(ee)

    def _check_proximity(self, ee):
        warnings = []
        for zone in SURGICAL_ZONES:
            if not zone["safe"]:
                dist      = math.sqrt((ee[0] - zone["x"]) ** 2 + (ee[1] - zone["y"]) ** 2 + (ee[2] - zone["z"]) ** 2)
                clearance = dist - zone["r"]
                if clearance < 0.05:
                    warnings.append(f"⚠ {clearance * 1000:.0f} mm from {zone['label']}")
                    if clearance < 0.02:
                        ALERTS.add("CRITICAL", f"Proximity breach — {zone['label']} clearance {clearance * 1000:.0f}mm")
        self._prox_var.set("\n".join(warnings) if warnings else "")

    # ══════════════════════════════════════════════════════════════
    #  MOUSE / SCROLL
    # ══════════════════════════════════════════════════════════════

    def _ds(self, e): self._drag_start = (e.x, e.y)
    def _de(self, e): self._drag_start = None

    def _dm(self, e):
        if self._drag_start:
            dx, dy = e.x - self._drag_start[0], e.y - self._drag_start[1]
            self.camera.az += dx * 0.5
            self.camera.el  = max(-89, min(89, self.camera.el + dy * 0.3))
            self._drag_start = (e.x, e.y)
            self._draw_3d()

    def _sc(self, e):
        f = 1.1 if (e.num == 4 or e.delta > 0) else 1 / 1.1
        self.camera.scale = max(100, min(1400, self.camera.scale * f))
        self._draw_3d()

    # ══════════════════════════════════════════════════════════════
    #  ANIMATION
    # ══════════════════════════════════════════════════════════════

    def _toggle_anim(self):
        self._anim_running = not self._anim_running
        self._anim_btn.configure(
            text="⏹ STOP SIM" if self._anim_running else "▶ SIMULATE",
            bg=C["green"]    if self._anim_running else C["amber"])
        if self._anim_running:
            self._run_anim()

    def _run_anim(self):
        if not self._anim_running:
            return
        self._anim_t += 0.035
        angles = [
            45 * math.sin(self._anim_t),
            55 * math.sin(self._anim_t * 0.8 + 1.2),
            35 * math.sin(self._anim_t * 1.4 + 2.1),
        ]
        for i, (s, vv) in enumerate(self.sliders):
            s.set(angles[i])
            self.dh_params[i]["theta"] = angles[i]
            vv.set(f"{angles[i]:.1f}°")
        self._update_all()
        self.after(40, self._run_anim)

    # ══════════════════════════════════════════════════════════════
    #  SLIDER / POPUP
    # ══════════════════════════════════════════════════════════════

    def _on_slider(self, idx, value, vv):
        self.dh_params[idx]["theta"] = float(value)
        vv.set(f"{float(value):.1f}°")
        popup = self._popups.get(idx)
        if popup and popup.winfo_exists():
            popup.evars["theta"].set(f"{float(value):.4f}")
        self._update_all()

    def _open_popup(self, idx):
        ex = self._popups.get(idx)
        if ex and ex.winfo_exists():
            ex.lift()
            ex.focus_force()
            return
        popup = DHPopup(self, idx, self.dh_params, self._popup_apply, self._popup_close)
        self._popups[idx] = popup
        self.link_btns[idx].configure(fg=self.dh_params[idx]["color"])

    def _popup_apply(self, idx, p):
        self.dh_params[idx].update(p)
        s, vv = self.sliders[idx]
        s.set(p["theta"])
        vv.set(f"{p['theta']:.1f}°")
        self._update_all()

    def _popup_close(self, idx):
        self._popups.pop(idx, None)
        if idx < len(self.link_btns):
            self.link_btns[idx].configure(fg=C["txt1"])

    # ══════════════════════════════════════════════════════════════
    #  JSON CONFIG
    # ══════════════════════════════════════════════════════════════

    def _load_json(self):
        path = filedialog.askopenfilename(
            title="Load D-H Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
            links  = data.get("links", data) if isinstance(data, dict) else data
            if not isinstance(links, list) or not links:
                raise ValueError("JSON must have a 'links' list")
            colors = [C["link1"], C["link2"], C["link3"]]
            new    = []
            for i, lnk in enumerate(links[:3]):
                new.append({
                    "name":  lnk.get("name", f"Link {i + 1}"),
                    "a":     float(lnk.get("a", 0)),
                    "alpha": float(lnk.get("alpha", 0)),
                    "d":     float(lnk.get("d", 0)),
                    "theta": float(lnk.get("theta", 0)),
                    "color": lnk.get("color", colors[i % 3]),
                })
            while len(new) < 3:
                j = len(new)
                new.append({"name": f"Link {j + 1}", "a": 0, "alpha": 0,
                            "d": 0, "theta": 0, "color": colors[j]})
            self.dh_params = new
            for i, (s, vv) in enumerate(self.sliders):
                s.set(self.dh_params[i]["theta"])
                vv.set(f"{self.dh_params[i]['theta']:.1f}°")
            for idx, popup in self._popups.items():
                if popup and popup.winfo_exists():
                    popup.dh_params = self.dh_params
                    popup.refresh()
            self._update_all()
            ALERTS.add("INFO", f"Config loaded: {path.split('/')[-1]}")
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))

    def _export_json(self):
        path = filedialog.asksaveasfilename(
            title="Export Config", defaultextension=".json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w") as f:
            json.dump({
                "robot_name": "Surgical 3-DOF Arm",
                "dof": 3,
                "links": [{k: v for k, v in p.items() if k != "color"}
                          for p in self.dh_params],
            }, f, indent=2)
        messagebox.showinfo("Exported", f"Saved:\n{path}")

    def _reset(self):
        self.dh_params = [dict(p) for p in DEFAULT_DH]
        for i, (s, vv) in enumerate(self.sliders):
            s.set(self.dh_params[i]["theta"])
            vv.set("0.0°")
        for idx, popup in list(self._popups.items()):
            if popup and popup.winfo_exists():
                popup.dh_params = self.dh_params
                popup.refresh()
        self._update_all()

    # ══════════════════════════════════════════════════════════════
    #  QUICK ACTIONS
    # ══════════════════════════════════════════════════════════════

    def _estop(self):
        self._anim_running = False
        self._anim_btn.configure(text="▶ SIMULATE", bg=C["amber"])
        ALERTS.add("CRITICAL", "EMERGENCY STOP triggered — all motion halted")
        messagebox.showwarning("EMERGENCY STOP",
                               "All robotic motion halted.\nCheck system before resuming.")

    def _manual_alert(self):
        ALERTS.add("WARNING", "Manual alert triggered by operator")
        self._draw_live_alerts()

    def _set_phase(self, phase, color):
        self._op_phase.set(phase)
        ALERTS.add("INFO", f"Operative phase changed to: {phase}")
        if phase == "INTRA-OP" and not self._timer_running:
            self._toggle_timer()
        self._draw_live_alerts()

    def _toggle_timer(self):
        self._timer_running = not self._timer_running

    # ══════════════════════════════════════════════════════════════
    #  ALERTS (shared drawing helpers)
    # ══════════════════════════════════════════════════════════════

    def _draw_alerts(self):
        for w in self._alert_frame.winfo_children():
            w.destroy()
        level_colors = {"CRITICAL": C["red"],      "WARNING": C["amber"],     "INFO": C["cyan"]}
        level_bg     = {"CRITICAL": C["red_bg"],   "WARNING": C["amber_bg"],  "INFO": C["cyan_bg"]}
        for a in ALERTS.alerts:
            col    = level_colors.get(a["level"], C["cyan"])
            bg_col = level_bg.get(a["level"],     C["cyan_bg"])
            acked  = a["ack"]
            row    = tk.Frame(self._alert_frame,
                              bg=bg_col if not acked else C["bg2"],
                              highlightthickness=1,
                              highlightbackground=col if not acked else C["border"])
            row.pack(fill=tk.X, pady=3, padx=4)
            badge = tk.Frame(row, bg=col, width=80)
            badge.pack(side=tk.LEFT, fill=tk.Y)
            badge.pack_propagate(False)
            tk.Label(badge, text=a["level"], font=("Consolas", 8, "bold"),
                     bg=col, fg="white").pack(expand=True)
            inner = tk.Frame(row, bg=bg_col if not acked else C["bg2"])
            inner.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=8)
            tk.Label(inner, text=a["msg"], font=("Consolas", 9),
                     bg=bg_col if not acked else C["bg2"],
                     fg=C["txt0"] if not acked else C["txt2"],
                     anchor=tk.W, wraplength=500).pack(fill=tk.X, anchor=tk.W)
            meta = tk.Frame(inner, bg=bg_col if not acked else C["bg2"])
            meta.pack(fill=tk.X, pady=(3, 0))
            tk.Label(meta, text=a["time"], font=("Consolas", 7),
                     bg=meta.cget("bg"), fg=C["txt2"]).pack(side=tk.LEFT)
            tk.Label(meta, text="✔ ACKNOWLEDGED" if acked else "PENDING",
                     font=("Consolas", 7, "bold"),
                     bg=meta.cget("bg"),
                     fg=C["green"] if acked else C["amber"]).pack(side=tk.RIGHT)

    def _draw_live_alerts(self):
        for w in self._live_alert_frame.winfo_children():
            w.destroy()
        level_colors = {"CRITICAL": C["red"], "WARNING": C["amber"], "INFO": C["cyan"]}
        shown = [a for a in ALERTS.alerts if not a["ack"]][:4]
        for a in shown:
            col = level_colors.get(a["level"], C["cyan"])
            r   = tk.Frame(self._live_alert_frame, bg=C["bg2"],
                           highlightthickness=1, highlightbackground=col)
            r.pack(fill=tk.X, pady=2)
            tk.Frame(r, bg=col, width=3).pack(side=tk.LEFT, fill=tk.Y)
            inner = tk.Frame(r, bg=C["bg2"])
            inner.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, pady=5)
            tk.Label(inner, text=a["level"], font=("Consolas", 7, "bold"),
                     bg=C["bg2"], fg=col).pack(anchor=tk.W)
            tk.Label(inner, text=a["msg"], font=("Consolas", 7),
                     bg=C["bg2"], fg=C["txt0"], wraplength=185,
                     anchor=tk.W, justify=tk.LEFT).pack(fill=tk.X, anchor=tk.W)
        if not shown:
            tk.Label(self._live_alert_frame, text="✔  No active alerts",
                     font=("Consolas", 8), bg=C["bg0"], fg=C["green"]).pack(pady=6)

    def _ack_all(self):
        ALERTS.ack_all()
        self._draw_alerts()

    def _refresh_alert_badge(self):
        unacked = sum(1 for a in ALERTS.alerts if not a["ack"])
        if unacked:
            self._tab_alert_var.set(f" {unacked} ")
            self._tab_alert_lbl.pack(side=tk.LEFT, padx=4, pady=6)
        else:
            self._tab_alert_lbl.pack_forget()
        self._draw_live_alerts()
        if self._active_tab.get() == "ALERTS":
            self._draw_alerts()

    # ══════════════════════════════════════════════════════════════
    #  UPDATE ALL
    # ══════════════════════════════════════════════════════════════

    def _update_all(self):
        transforms = fk(self.dh_params)
        positions  = joint_pos(transforms)
        ee = positions[-1]

        self.ee_vars["X"].set(f"{ee[0]:.4f} m")
        self.ee_vars["Y"].set(f"{ee[1]:.4f} m")
        self.ee_vars["Z"].set(f"{ee[2]:.4f} m")
        self._reach_var.set(f"{math.sqrt(sum(v ** 2 for v in ee)):.4f} m")

        for i, (p, cells) in enumerate(zip(self.dh_params, self._dh_table_rows)):
            for var, v in zip(cells, [f"L{i + 1}", f"{p['a']:.3f}",
                                       f"{p['alpha']:.1f}", f"{p['d']:.3f}",
                                       f"{p['theta']:.1f}"]):
                var.set(v)

        self._draw_3d(transforms, positions)
        self._draw_workspace()

    # ══════════════════════════════════════════════════════════════
    #  CLOCK + TIMER
    # ══════════════════════════════════════════════════════════════

    def _start_clock(self):
        def _tick():
            self._clock_var.set(datetime.now().strftime("%H:%M:%S"))
            if self._timer_running:
                self._elapsed += 1
                h, r = divmod(self._elapsed, 3600)
                m, s = divmod(r, 60)
                self._timer_var.set(f"{h:02d}:{m:02d}:{s:02d}")
            self.after(1000, _tick)
        _tick()
