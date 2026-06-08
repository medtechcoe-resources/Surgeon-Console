# ═══════════════════════════════════════════════════════════════════
#  COLOR SYSTEM  —  Light Cool Clinical Theme
# ═══════════════════════════════════════════════════════════════════
C = {
    "bg0":      "#eef2f7",
    "bg1":      "#f7f9fc",
    "bg2":      "#ffffff",
    "bg3":      "#dde6f0",

    "border":   "#c8d8e8",
    "border2":  "#a0bcd4",

    "cyan":     "#0077b6",
    "green":    "#0a9e6a",
    "amber":    "#d4860a",
    "red":      "#d63031",
    "violet":   "#6c5ce7",
    "teal":     "#00897b",
    "pink":     "#e84393",

    "txt0":     "#0d1b2a",
    "txt1":     "#3a5068",
    "txt2":     "#7a97b0",

    "link1":    "#0077b6",
    "link2":    "#d4860a",
    "link3":    "#6c5ce7",
    "ee":       "#0a9e6a",
    "grid":     "#d0dce8",

    "red_bg":   "#fff0f0",
    "amber_bg": "#fffbf0",
    "green_bg": "#f0faf6",
    "cyan_bg":  "#f0f8ff",
}

# ═══════════════════════════════════════════════════════════════════
#  DEFAULT D-H PARAMETERS
# ═══════════════════════════════════════════════════════════════════
DEFAULT_DH = [
    {"name": "Link 1", "a": 0.0,  "alpha": 90.0, "d": 0.15, "theta": 0.0, "color": C["link1"]},
    {"name": "Link 2", "a": 0.30, "alpha": 0.0,  "d": 0.0,  "theta": 0.0, "color": C["link2"]},
    {"name": "Link 3", "a": 0.25, "alpha": 0.0,  "d": 0.0,  "theta": 0.0, "color": C["link3"]},
]

# ═══════════════════════════════════════════════════════════════════
#  PATIENT DATA
# ═══════════════════════════════════════════════════════════════════
PATIENT = {
    "name":         "J. Morrison",
    "id":           "PT-2024-0847",
    "age":          58,
    "sex":          "M",
    "weight":       82,
    "height":       175,
    "bmi":          26.8,
    "asa":          "II",
    "procedure":    "Laparoscopic Cholecystectomy",
    "surgeon":      "Dr. A. Patel",
    "or":           "OR-3",
    "scheduled":    "08:30",
    "blood_type":   "O+",
    "allergies":    "Penicillin",
    "comorbidities": ["Hypertension", "Type 2 DM"],
}

# ═══════════════════════════════════════════════════════════════════
#  PRE-OP CHECKLIST
# ═══════════════════════════════════════════════════════════════════
PRE_OP_CHECKLIST = [
    ("Patient identity verified",          True),
    ("Surgical site marked",               True),
    ("Informed consent obtained",          True),
    ("Allergies confirmed",                True),
    ("NPO status confirmed (>8h)",         True),
    ("Pre-op antibiotics administered",    True),
    ("Imaging reviewed (CT/MRI)",          True),
    ("Blood type & cross-match ready",     True),
    ("Anaesthesia clearance",              True),
    ("Robot calibration complete",         True),
    ("Instrument sterility verified",      True),
    ("Emergency protocol briefed",         False),
]

# ═══════════════════════════════════════════════════════════════════
#  POST-OP METRICS
# ═══════════════════════════════════════════════════════════════════
POST_OP_METRICS = {
    "Procedure Duration":   "1h 42m",
    "EBL":                  "35 mL",
    "Instrument Changes":   "4",
    "Avg Force Applied":    "1.8 N",
    "Peak Force":           "4.2 N",
    "Tremor Filtered":      "98.6%",
    "Workspace Violations": "0",
    "Tool Path Length":     "847 mm",
    "Repositioning Events": "3",
    "Anaesthesia Time":     "2h 08m",
    "Specimens Collected":  "1",
    "Complications":        "None",
}

# ═══════════════════════════════════════════════════════════════════
#  SURGICAL ZONES
# ═══════════════════════════════════════════════════════════════════
SURGICAL_ZONES = [
    {"label": "Target Zone",  "x":  0.12, "y":  0.08, "z": 0.18, "r": 0.06, "color": C["green"], "safe": True},
    {"label": "No-Go Zone A", "x": -0.1,  "y":  0.05, "z": 0.10, "r": 0.04, "color": C["red"],   "safe": False},
    {"label": "No-Go Zone B", "x":  0.18, "y": -0.05, "z": 0.12, "r": 0.03, "color": C["red"],   "safe": False},
    {"label": "Caution Zone", "x":  0.05, "y":  0.15, "z": 0.20, "r": 0.05, "color": C["amber"], "safe": None},
]
