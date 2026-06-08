


import tkinter as tk
from tkinter import messagebox

from constants import C, PATIENT, PRE_OP_CHECKLIST, POST_OP_METRICS, SURGICAL_ZONES
from data_models import ALERTS, VITALS
from widgets import card, sec_header


# ═══════════════════════════════════════════════════════════════════
#  TAB: PRE-OP WORKFLOW  (full-page 2×2 grid)
# ═══════════════════════════════════════════════════════════════════

def build_preop_workflow(parent, app):
    """Build the full PRE-OP workflow page with 2×2 grid layout:
    Top-Left:  Pre-Operative Checklist
    Top-Right: Pre-Op Imaging & Workspace Analysis
    Bottom-Left:  Surgical Plan
    Bottom-Right: Patient Risk Summary
    """

    # Use a grid-based layout for the 2×2 arrangement
    grid = tk.Frame(parent, bg=C["bg0"])
    grid.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    grid.columnconfigure(0, weight=1)
    grid.columnconfigure(1, weight=2)
    grid.rowconfigure(0, weight=1)
    grid.rowconfigure(1, weight=1)

    # ── TOP-LEFT: Pre-Operative Checklist ─────────────────────────
    tl = tk.Frame(grid, bg=C["bg0"])
    tl.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))

    sec_header(tl, "PRE-OPERATIVE CHECKLIST", C["violet"])
    cklist = card(tl)
    cklist.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

    done  = sum(1 for _, v in PRE_OP_CHECKLIST if v)
    total = len(PRE_OP_CHECKLIST)
    pct   = done / total * 100

    prog_row = tk.Frame(cklist, bg=C["bg2"])
    prog_row.pack(fill=tk.X, padx=10, pady=(8, 4))
    tk.Label(prog_row, text=f"Completion: {done}/{total}",
             font=("Consolas", 9, "bold"), bg=C["bg2"],
             fg=C["green"] if done == total else C["amber"]).pack(side=tk.LEFT)
    tk.Label(prog_row, text=f"{pct:.0f}%",
             font=("Consolas", 9, "bold"), bg=C["bg2"], fg=C["cyan"]).pack(side=tk.RIGHT)

    # Progress bar
    pb_bg = tk.Frame(cklist, bg=C["bg1"], height=8)
    pb_bg.pack(fill=tk.X, padx=10, pady=(0, 8))
    pb_fill = tk.Frame(pb_bg, bg=C["green"] if done == total else C["amber"], height=8)
    pb_fill.place(x=0, y=0, relwidth=pct / 100, relheight=1)

    # Checklist items
    checklist_items = [
        "Patient identity verified",
        "Surgical site marked",
        "Informed consent obtained",
        "Allergies confirmed",
        "NPO status confirmed",
        "Pre-op antibiotics administered",
        "Imaging reviewed",
        "Blood type verified",
        "Robot calibration complete",
        "Sterility confirmed",
    ]

    # Map constants checklist to our display list
    for i, item_text in enumerate(checklist_items):
        # Check if item matches any in PRE_OP_CHECKLIST
        checked = False
        for ck_item, ck_val in PRE_OP_CHECKLIST:
            if item_text.lower()[:15] in ck_item.lower():
                checked = ck_val
                break

        r = tk.Frame(cklist, bg=C["bg2"])
        r.pack(fill=tk.X, padx=10, pady=2)
        icon = "✔" if checked else "○"
        col  = C["green"] if checked else C["amber"]
        tk.Label(r, text=icon, font=("Consolas", 9, "bold"),
                 bg=C["bg2"], fg=col, width=3).pack(side=tk.LEFT)
        tk.Label(r, text=item_text, font=("Consolas", 8),
                 bg=C["bg2"], fg=C["txt0"] if checked else C["amber"],
                 anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Frame(cklist, height=6, bg=C["bg2"]).pack()

    # ── TOP-RIGHT: Pre-Op Imaging & Workspace Analysis ────────────
    tr = tk.Frame(grid, bg=C["bg0"])
    tr.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))

    sec_header(tr, "PRE-OP IMAGING & WORKSPACE ANALYSIS", C["cyan"])

    img_row = tk.Frame(tr, bg=C["bg0"])
    img_row.pack(fill=tk.BOTH, expand=True)

    # CT Scan Preview
    ct_f = card(img_row)
    ct_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))
    tk.Label(ct_f, text="CT SCAN PREVIEW  //  Axial",
             font=("Consolas", 8, "bold"), bg=C["bg2"], fg=C["violet"],
             padx=10).pack(anchor=tk.W, pady=6)
    app._ct_canvas = tk.Canvas(ct_f, bg="#e8f0f8",
                                highlightthickness=0, height=180)
    app._ct_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    app._ct_canvas.bind("<Configure>", lambda e: app._draw_ct())

    # MRI Preview
    mri_f = card(img_row)
    mri_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3, 3))
    tk.Label(mri_f, text="MRI PREVIEW  //  Sagittal",
             font=("Consolas", 8, "bold"), bg=C["bg2"], fg=C["pink"],
             padx=10).pack(anchor=tk.W, pady=6)
    app._mri_canvas = tk.Canvas(mri_f, bg="#eee8f4",
                                highlightthickness=0, height=180)
    app._mri_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    app._mri_canvas.bind("<Configure>", lambda e: app._draw_mri())

    # Workspace / Entry Path
    ws_f = card(img_row)
    ws_f.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3, 0))
    tk.Label(ws_f, text="SURGICAL ENTRY PATH  //  XZ plane",
             font=("Consolas", 8, "bold"), bg=C["bg2"], fg=C["teal"],
             padx=10).pack(anchor=tk.W, pady=6)
    app._ws_canvas = tk.Canvas(ws_f, bg="#eef4fa",
                                highlightthickness=0, height=180)
    app._ws_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    app._ws_canvas.bind("<Configure>", lambda e: app._draw_workspace())

    # Target organ overlay label
    overlay_f = tk.Frame(tr, bg=C["bg0"])
    overlay_f.pack(fill=tk.X, pady=(4, 0))
    for label, color in [("Target: Gallbladder", C["green"]),
                         ("Entry: Umbilical Port", C["cyan"]),
                         ("Approach: Laparoscopic", C["violet"])]:
        badge = tk.Frame(overlay_f, bg=color, padx=8, pady=3)
        badge.pack(side=tk.LEFT, padx=3)
        tk.Label(badge, text=label, font=("Consolas", 7, "bold"),
                 bg=color, fg="white").pack()

    # ── BOTTOM-LEFT: Surgical Plan ────────────────────────────────
    bl = tk.Frame(grid, bg=C["bg0"])
    bl.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))

    sec_header(bl, "SURGICAL PLAN", C["cyan"])
    plan = card(bl)
    plan.pack(fill=tk.BOTH, expand=True)

    plan_data = [
        ("Procedure",        PATIENT["procedure"]),
        ("Surgical Approach", "Minimally Invasive — Laparoscopic"),
        ("Robot Configuration", "3-DOF Laparoscopic Arm"),
        ("Target Organ",     "Gallbladder"),
        ("Estimated Duration", "90 – 120 min"),
        ("Number of Ports",  "4 (umbilical, epigastric, 2× RUQ)"),
        ("Recovery Plan",    "Same-day discharge expected"),
    ]
    for k, v in plan_data:
        r = tk.Frame(plan, bg=C["bg2"])
        r.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(r, text=k, font=("Consolas", 8),
                 bg=C["bg2"], fg=C["txt2"], anchor=tk.W).pack(side=tk.LEFT)
        fg = C["green"] if "same-day" in v.lower() else C["txt0"]
        if "laparoscopic" in v.lower():
            fg = C["cyan"]
        tk.Label(r, text=v, font=("Consolas", 8, "bold"),
                 bg=C["bg2"], fg=fg, anchor=tk.E, wraplength=300).pack(side=tk.RIGHT)
    tk.Frame(plan, height=6, bg=C["bg2"]).pack()

    # ── BOTTOM-RIGHT: Patient Risk Summary ────────────────────────
    br = tk.Frame(grid, bg=C["bg0"])
    br.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

    sec_header(br, "PATIENT RISK SUMMARY", C["amber"])

    risk_grid = tk.Frame(br, bg=C["bg0"])
    risk_grid.pack(fill=tk.BOTH, expand=True)

    risk_items = [
        ("ASA Classification", f"Class {PATIENT['asa']} — Mild systemic disease", C["green"]),
        ("Comorbidities",      ", ".join(PATIENT["comorbidities"]),                C["amber"]),
        ("Allergies",          PATIENT["allergies"],                               C["red"]),
        ("Blood Group",        PATIENT["blood_type"],                              C["cyan"]),
        ("Risk Level",         "LOW",                                              C["green"]),
    ]

    for label, val, color in risk_items:
        r = card(risk_grid)
        r.pack(fill=tk.X, pady=3)
        inner = tk.Frame(r, bg=C["bg2"])
        inner.pack(fill=tk.X, padx=10, pady=8)

        top = tk.Frame(inner, bg=C["bg2"])
        top.pack(fill=tk.X)
        tk.Label(top, text=label, font=("Consolas", 9, "bold"),
                 bg=C["bg2"], fg=C["txt0"], anchor=tk.W).pack(side=tk.LEFT)

        # Color-coded indicator dot
        dot = tk.Canvas(top, width=10, height=10, bg=C["bg2"], highlightthickness=0)
        dot.pack(side=tk.RIGHT, padx=(0, 4))
        dot.create_oval(1, 1, 9, 9, fill=color, outline="")

        tk.Label(inner, text=val, font=("Consolas", 9, "bold"),
                 bg=C["bg2"], fg=color, anchor=tk.W).pack(fill=tk.X, pady=(2, 0))

    # Risk level badge at bottom
    risk_badge_f = tk.Frame(risk_grid, bg=C["bg0"])
    risk_badge_f.pack(fill=tk.X, pady=(6, 0))
    badge_card = card(risk_badge_f)
    badge_card.pack(fill=tk.X)
    badge_inner = tk.Frame(badge_card, bg=C["green_bg"])
    badge_inner.pack(fill=tk.X, padx=1, pady=1)
    tk.Label(badge_inner, text="OVERALL RISK ASSESSMENT: LOW",
             font=("Consolas", 10, "bold"), bg=C["green_bg"], fg=C["green"],
             pady=10).pack()
    tk.Label(badge_inner, text="ASA II  ·  No significant contraindications  ·  Standard anaesthesia protocol",
             font=("Consolas", 7), bg=C["green_bg"], fg=C["txt1"]).pack(pady=(0, 8))


# ═══════════════════════════════════════════════════════════════════
#  TAB: ALERTS
# ═══════════════════════════════════════════════════════════════════

def build_alerts_tab(parent, app):
    hdr = tk.Frame(parent, bg=C["bg0"])
    hdr.pack(fill=tk.X, pady=(4, 8))
    tk.Label(hdr, text="SYSTEM ALERTS & SAFETY LOG",
             font=("Consolas", 13, "bold"), bg=C["bg0"], fg=C["txt0"]).pack(side=tk.LEFT, padx=4)
    tk.Button(hdr, text="✔ ACK ALL",
              font=("Consolas", 9, "bold"), bg=C["green"], fg="white",
              relief=tk.FLAT, bd=0, padx=10, pady=6, cursor="hand2",
              command=app._ack_all).pack(side=tk.RIGHT, padx=4)

    leg = tk.Frame(parent, bg=C["bg0"])
    leg.pack(fill=tk.X, padx=4, pady=(0, 6))
    for lbl_txt, col in [("CRITICAL", C["red"]), ("WARNING", C["amber"]), ("INFO", C["cyan"])]:
        f = tk.Frame(leg, bg=col, padx=6, pady=2)
        f.pack(side=tk.LEFT, padx=4)
        tk.Label(f, text=lbl_txt, font=("Consolas", 7, "bold"),
                 bg=col, fg="white").pack()

    container = tk.Frame(parent, bg=C["bg0"])
    container.pack(fill=tk.BOTH, expand=True)

    sb = tk.Scrollbar(container, orient=tk.VERTICAL, bg=C["bg1"], troughcolor=C["bg0"])
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    app._alert_canvas = tk.Canvas(container, bg=C["bg0"],
                                  highlightthickness=0,
                                  yscrollcommand=sb.set)
    app._alert_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.configure(command=app._alert_canvas.yview)

    app._alert_frame = tk.Frame(app._alert_canvas, bg=C["bg0"])
    app._alert_canvas.create_window((0, 0), window=app._alert_frame,
                                    anchor=tk.NW, tags="frame")
    app._alert_frame.bind(
        "<Configure>",
        lambda e: app._alert_canvas.configure(scrollregion=app._alert_canvas.bbox("all")))
    app._alert_canvas.bind(
        "<Configure>",
        lambda e: app._alert_canvas.itemconfig("frame", width=e.width))

    app._draw_alerts()


# ═══════════════════════════════════════════════════════════════════
#  TAB: POST-OP WORKFLOW  (full-page 2×2 grid)
# ═══════════════════════════════════════════════════════════════════

def build_postop_workflow(parent, app):
    """Build the full POST-OP workflow page with 2×2 grid layout:
    Top-Left:    Operative Metrics
    Top-Right:   Intra-Op Vitals Trend
    Bottom-Left: Performance Score
    Bottom-Right: Surgeon Notes
    """

    grid = tk.Frame(parent, bg=C["bg0"])
    grid.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    grid.columnconfigure(0, weight=1)
    grid.columnconfigure(1, weight=2)
    grid.rowconfigure(0, weight=1)
    grid.rowconfigure(1, weight=1)

    # ── TOP-LEFT: Operative Metrics ───────────────────────────────
    tl = tk.Frame(grid, bg=C["bg0"])
    tl.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))

    sec_header(tl, "OPERATIVE METRICS", C["teal"])
    mc = card(tl)
    mc.pack(fill=tk.BOTH, expand=True)

    for k, v in POST_OP_METRICS.items():
        r = tk.Frame(mc, bg=C["bg2"])
        r.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(r, text=k, font=("Consolas", 8),
                 bg=C["bg2"], fg=C["txt2"], anchor=tk.W).pack(side=tk.LEFT)

        # Color-code values
        fg = C["teal"]
        if "Violation" in k and v != "0":
            fg = C["red"]
        elif v == "None":
            fg = C["green"]
        elif "Duration" in k:
            fg = C["cyan"]
        elif "Blood" in k or "EBL" in k:
            fg = C["amber"]

        tk.Label(r, text=v, font=("Consolas", 8, "bold"),
                 bg=C["bg2"], fg=fg).pack(side=tk.RIGHT)
    tk.Frame(mc, height=6, bg=C["bg2"]).pack()

    # ── TOP-RIGHT: Intra-Op Vitals Trend ──────────────────────────
    tr = tk.Frame(grid, bg=C["bg0"])
    tr.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))

    sec_header(tr, "INTRA-OP VITALS TREND", C["cyan"])
    vc = card(tr)
    vc.pack(fill=tk.BOTH, expand=True)

    app._postop_vitals_canvas = tk.Canvas(vc, bg=C["bg2"],
                                          highlightthickness=0)
    app._postop_vitals_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    app._postop_vitals_canvas.bind("<Configure>", lambda e: app._draw_postop_chart())

    # Legend
    legend_f = tk.Frame(vc, bg=C["bg2"])
    legend_f.pack(fill=tk.X, padx=10, pady=(0, 6))
    for label, color in [("HR", C["pink"]), ("SpO₂", C["cyan"]), ("EtCO₂", C["teal"])]:
        lf = tk.Frame(legend_f, bg=C["bg2"])
        lf.pack(side=tk.LEFT, padx=8)
        tk.Frame(lf, bg=color, width=12, height=3).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(lf, text=label, font=("Consolas", 8), bg=C["bg2"], fg=color).pack(side=tk.LEFT)

    # ── BOTTOM-LEFT: Performance Score ────────────────────────────
    bl = tk.Frame(grid, bg=C["bg0"])
    bl.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))

    sec_header(bl, "PERFORMANCE SCORE", C["cyan"])
    sc = card(bl)
    sc.pack(fill=tk.BOTH, expand=True)

    scores = [
        ("Precision",            96),
        ("Safety Compliance",   100),
        ("Tremor Control",       98),
        ("Force Management",     89),
        ("Workspace Efficiency", 82),
    ]
    for metric, score in scores:
        r = tk.Frame(sc, bg=C["bg2"])
        r.pack(fill=tk.X, padx=10, pady=5)

        top = tk.Frame(r, bg=C["bg2"])
        top.pack(fill=tk.X)
        tk.Label(top, text=metric, font=("Consolas", 9, "bold"),
                 bg=C["bg2"], fg=C["txt0"], anchor=tk.W).pack(side=tk.LEFT)

        col = C["green"] if score >= 90 else C["amber"] if score >= 75 else C["red"]
        tk.Label(top, text=f"{score}%", font=("Consolas", 10, "bold"),
                 bg=C["bg2"], fg=col).pack(side=tk.RIGHT)

        bar_bg = tk.Frame(r, bg=C["bg1"], height=8)
        bar_bg.pack(fill=tk.X, pady=(3, 0))
        tk.Frame(bar_bg, bg=col, height=8).place(x=0, y=0, relwidth=score / 100, relheight=1)

    tk.Frame(sc, height=6, bg=C["bg2"]).pack()

    # ── BOTTOM-RIGHT: Surgeon Notes ───────────────────────────────
    br = tk.Frame(grid, bg=C["bg0"])
    br.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

    sec_header(br, "SURGEON NOTES", C["violet"])
    notes_c = card(br)
    notes_c.pack(fill=tk.BOTH, expand=True)

    # Read-only label at top
    notes_hdr = tk.Frame(notes_c, bg=C["bg3"])
    notes_hdr.pack(fill=tk.X, padx=6, pady=(6, 0))
    tk.Label(notes_hdr, text="POST-OPERATIVE REPORT  //  READ-ONLY",
             font=("Consolas", 7, "bold"), bg=C["bg3"], fg=C["txt2"],
             padx=6, pady=4).pack(anchor=tk.W)

    app._notes_txt = tk.Text(notes_c, font=("Consolas", 9),
                             bg=C["bg2"], fg=C["txt0"],
                             insertbackground=C["cyan"],
                             relief=tk.FLAT, bd=0, wrap=tk.WORD,
                             padx=10, pady=8, highlightthickness=0,
                             state=tk.NORMAL)
    app._notes_txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    report_text = (
        "PROCEDURE SUMMARY\n"
        "─────────────────────────────────────────\n"
        f"Procedure: {PATIENT['procedure']}\n"
        f"Surgeon: {PATIENT['surgeon']}\n"
        f"Operating Room: {PATIENT['or']}\n\n"
        "FINDINGS\n"
        "─────────────────────────────────────────\n"
        "Gallbladder removed via standard 4-port laparoscopic technique. "
        "Mild adhesions encountered at the hepatocystic triangle — "
        "dissected sharply with robotic precision. Cystic duct and artery "
        "identified, clipped, and divided. No bile spillage.\n\n"
        "BLOOD LOSS\n"
        "─────────────────────────────────────────\n"
        "Estimated blood loss: 35 mL. Well within acceptable limits "
        "for laparoscopic cholecystectomy.\n\n"
        "INSTRUMENT OBSERVATIONS\n"
        "─────────────────────────────────────────\n"
        "4 instrument changes during procedure. Average applied force "
        "1.8 N (peak 4.2 N). Tremor filtering maintained at 98.6%. "
        "Zero workspace violations recorded.\n\n"
        "COMPLICATIONS\n"
        "─────────────────────────────────────────\n"
        "None. Procedure completed without complications.\n\n"
        "RECOVERY RECOMMENDATION\n"
        "─────────────────────────────────────────\n"
        "Patient tolerated procedure well. Good haemostasis confirmed. "
        "Transferred to PACU in stable condition. Same-day discharge "
        "expected pending standard post-anaesthetic recovery criteria.\n"
    )
    app._notes_txt.insert("1.0", report_text)
    app._notes_txt.configure(state=tk.DISABLED)

    # Export button
    btn_row = tk.Frame(br, bg=C["bg0"])
    btn_row.pack(fill=tk.X, pady=(0, 4))
    tk.Button(btn_row, text="EXPORT REPORT (PDF)",
              font=("Consolas", 9, "bold"), bg=C["teal"], fg="white",
              relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2",
              command=lambda: messagebox.showinfo(
                  "Export", "Post-op report export would save a PDF here.")).pack(side=tk.LEFT)
