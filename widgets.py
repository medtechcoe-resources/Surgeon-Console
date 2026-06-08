import tkinter as tk
from constants import C


# ═══════════════════════════════════════════════════════════════════
#  FACTORY HELPERS
# ═══════════════════════════════════════════════════════════════════

def lbl(parent, text, font=None, fg=None, bg=None, **kw):
    """Create a standard label with clinical theme defaults."""
    return tk.Label(
        parent, text=text,
        font=font or ("Consolas", 9),
        fg=fg or C["txt1"],
        bg=bg or C["bg1"],
        **kw,
    )


def sep(parent, bg=None, height=1):
    """Pack a thin horizontal separator line."""
    tk.Frame(parent, bg=bg or C["border"], height=height).pack(fill=tk.X)


def card(parent, **kw):
    """Return a white bordered card frame (not yet packed)."""
    return tk.Frame(
        parent, bg=C["bg2"],
        highlightthickness=1,
        highlightbackground=C["border"],
        **kw,
    )


def sec_header(parent, text, color=None):
    """Pack a coloured section-header row into *parent*."""
    f = tk.Frame(parent, bg=C["bg0"])
    f.pack(fill=tk.X, pady=(10, 4))
    tk.Frame(f, bg=color or C["cyan"], width=3).pack(side=tk.LEFT, fill=tk.Y)
    tk.Label(
        f, text=f"  {text}",
        font=("Consolas", 8, "bold"),
        bg=C["bg0"],
        fg=color or C["cyan"],
    ).pack(side=tk.LEFT)


def status_badge(parent, text, color):
    """Return a coloured badge frame (not yet packed)."""
    f = tk.Frame(parent, bg=color, padx=6, pady=2)
    tk.Label(f, text=text, font=("Consolas", 8, "bold"),
             bg=color, fg="white").pack()
    return f


# ═══════════════════════════════════════════════════════════════════
#  SPARKLINE WIDGET
# ═══════════════════════════════════════════════════════════════════

class Sparkline(tk.Canvas):
    """Mini scrolling line chart for live vitals data."""

    def __init__(self, parent, color, width=120, height=30, **kw):
        super().__init__(
            parent, width=width, height=height,
            bg=C["bg3"], highlightthickness=0,
            **kw,
        )
        self.color = color
        self._data = []

    def update_data(self, data):
        self._data = list(data[-50:])
        self.draw()

    def draw(self):
        self.delete("all")
        W, H = self.winfo_width(), self.winfo_height()
        if not self._data or W < 4:
            return
        mn, mx = min(self._data), max(self._data)
        rng = mx - mn or 1
        pts = []
        for i, v in enumerate(self._data):
            x = i / max(len(self._data) - 1, 1) * W
            y = H - (v - mn) / rng * (H - 4) - 2
            pts.extend([x, y])
        if len(pts) >= 4:
            self.create_line(*pts, fill=self.color, width=2, smooth=True)


# ═══════════════════════════════════════════════════════════════════
#  D-H PARAMETER POPUP
# ═══════════════════════════════════════════════════════════════════

class DHPopup(tk.Toplevel):
    """Floating editor window for a single D-H link's parameters."""

    def __init__(self, master, idx, dh_params, on_apply, on_close):
        super().__init__(master)
        self.idx       = idx
        self.dh_params = dh_params
        self.on_apply  = on_apply
        self.on_close  = on_close

        p = dh_params[idx]
        self.title(f"D-H Editor — {p['name']}")
        self.configure(bg=C["bg0"])
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.update_idletasks()

        mx = master.winfo_rootx() + master.winfo_width() // 2
        my = master.winfo_rooty() + master.winfo_height() // 2
        self.geometry(f"360x440+{mx - 180}+{my - 220}")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build(p)

    # ── UI construction ───────────────────────────────────────────
    def _build(self, p):
        from tkinter import messagebox

        color = p["color"]

        hdr = tk.Frame(self, bg=C["bg1"], height=46)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        c = tk.Canvas(hdr, width=10, height=10, bg=C["bg1"], highlightthickness=0)
        c.pack(side=tk.LEFT, padx=(12, 6), pady=14)
        c.create_oval(1, 1, 9, 9, fill=color, outline="")

        tk.Label(hdr, text=p["name"].upper(),
                 font=("Consolas", 11, "bold"),
                 bg=C["bg1"], fg=color).pack(side=tk.LEFT)

        tk.Button(hdr, text=" ✕ ", font=("Consolas", 10, "bold"),
                  bg=C["bg1"], fg=C["txt1"],
                  activebackground=C["red"], activeforeground="white",
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  command=self._close).pack(side=tk.RIGHT, padx=6)

        tk.Frame(self, bg=color, height=2).pack(fill=tk.X)

        body = tk.Frame(self, bg=C["bg0"])
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        fields = [
            ("a",     "Link Length (a)", "m"),
            ("alpha", "Twist Angle (α)", "°"),
            ("d",     "Link Offset (d)", "m"),
            ("theta", "Joint Angle (θ)", "°"),
        ]
        self.evars = {}
        for key, lbl_txt, unit in fields:
            g = tk.Frame(body, bg=C["bg0"])
            g.pack(fill=tk.X, pady=5)
            r = tk.Frame(g, bg=C["bg0"])
            r.pack(fill=tk.X)
            tk.Label(r, text=lbl_txt, font=("Consolas", 9, "bold"),
                     bg=C["bg0"], fg=C["txt0"]).pack(side=tk.LEFT)
            tk.Label(r, text=f"  [{unit}]", font=("Consolas", 8),
                     bg=C["bg0"], fg=color).pack(side=tk.LEFT)
            var = tk.StringVar(value=f"{p[key]:.4f}")
            e = tk.Entry(g, textvariable=var, font=("Consolas", 11, "bold"),
                         bg=C["bg3"], fg=color, insertbackground=color,
                         relief=tk.FLAT, bd=0, highlightthickness=1,
                         highlightbackground=C["border"], highlightcolor=color)
            e.pack(fill=tk.X, ipady=6, pady=(3, 0))
            self.evars[key] = var

        br = tk.Frame(self, bg=C["bg0"])
        br.pack(fill=tk.X, padx=16, pady=(0, 14))
        tk.Button(br, text="✕  CLOSE", font=("Consolas", 9, "bold"),
                  bg=C["bg3"], fg=C["txt1"], activebackground=C["border"],
                  relief=tk.FLAT, bd=0, padx=10, pady=9, cursor="hand2",
                  command=self._close).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        tk.Button(br, text="▶  APPLY", font=("Consolas", 9, "bold"),
                  bg=color, fg="white", activebackground=C["cyan"],
                  activeforeground="white",
                  relief=tk.FLAT, bd=0, padx=10, pady=9, cursor="hand2",
                  command=self._apply).pack(side=tk.RIGHT, fill=tk.X, expand=True)

        self.bind("<Return>", lambda e: self._apply())
        self.bind("<Escape>", lambda e: self._close())

        # keep reference for messagebox
        self._messagebox = messagebox

    def _apply(self):
        try:
            p = self.dh_params[self.idx]
            for k in ["a", "alpha", "d", "theta"]:
                p[k] = float(self.evars[k].get())
            self.on_apply(self.idx, p)
            orig = self.cget("bg")
            self.configure(bg="#d4f5e8")
            self.after(150, lambda: self.configure(bg=orig))
        except ValueError as ex:
            self._messagebox.showerror("Error", str(ex), parent=self)

    def _close(self):
        self.on_close(self.idx)
        self.destroy()

    def refresh(self):
        """Sync displayed values from the shared dh_params list."""
        p = self.dh_params[self.idx]
        for k in ["a", "alpha", "d", "theta"]:
            self.evars[k].set(f"{p[k]:.4f}")
