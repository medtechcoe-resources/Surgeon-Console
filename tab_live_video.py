import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from constants import C, PATIENT
from data_models import ALERTS, VITALS

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ── YOLO ──────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    YOLO_OK = True
except ImportError:
    YOLO_OK = False


class LiveVideoTab:
    def __init__(self, parent, app):
        self._app    = app
        self._parent = parent

        self._video_cap        = None
        self._video_running    = False
        self._video_path       = None
        self._video_photo      = None
        self._video_fps        = 25.0
        self._vid_total_frames = 0
        self._vid_duration_s   = 0

        self._frame_queue   = queue.Queue(maxsize=2)
        self._reader_thread = None
        self._render_job    = None

        self._hud_var    = tk.BooleanVar(value=True)
        self._yolo_var   = tk.BooleanVar(value=False)   # ← NEW: YOLO toggle
        self._zoom_var   = tk.StringVar(value="")

        self._vid_status_var = tk.StringVar(value="NO SOURCE — Load a video file")
        self._vid_time_var   = tk.StringVar(value="00:00 / 00:00")
        self._vid_res_var    = tk.StringVar(value="")

        self._vid_info_vars = {k: tk.StringVar(value="—")
                               for k in ("Source", "FPS", "Frame", "Duration", "Resolution")}

        self._rec_dot_visible = True

        # ── YOLO model (lazy-loaded on first use) ─────────────────
        self._yolo_model      = None          # ← NEW
        self._yolo_loading    = False         # ← NEW
        self._yolo_status_var = tk.StringVar(value="")  # ← NEW

        self._build(parent)
        self._blink_rec_dot()

    # ── YOLO loader ───────────────────────────────────────────────

    def _ensure_yolo(self):
        """Load YOLOv8x in a background thread (only once)."""
        if self._yolo_model or self._yolo_loading:
            return
        if not YOLO_OK:
            messagebox.showerror("Missing library",
                                 "ultralytics not installed.\n\npip install ultralytics")
            self._yolo_var.set(False)
            return

        self._yolo_loading = True
        self._yolo_status_var.set("⏳ Loading YOLO model...")

        def _load():
            try:
                model = YOLO("yolov8x.pt")   # downloads weights if absent
                self._yolo_model = model
                self._app.after(0, lambda: self._yolo_status_var.set("✔ YOLO ready"))
            except Exception as ex:
                self._app.after(0, lambda: self._yolo_status_var.set(f"✖ {ex}"))
                self._app.after(0, lambda: self._yolo_var.set(False))
            finally:
                self._yolo_loading = False

        threading.Thread(target=_load, daemon=True).start()

    # ── UI ────────────────────────────────────────────────────────

    def _build(self, parent):
        toolbar = tk.Frame(parent, bg="#0d0d0d", height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        tk.Frame(toolbar, bg=C["red"], width=4).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(toolbar, text="  ▶  LIVE SURGICAL FEED",
                 font=("Consolas", 11, "bold"),
                 bg="#0d0d0d", fg=C["red"]).pack(side=tk.LEFT, padx=6)

        self._rec_canvas = tk.Canvas(toolbar, width=14, height=14,
                                     bg="#0d0d0d", highlightthickness=0)
        self._rec_canvas.pack(side=tk.LEFT, pady=14)
        self._rec_canvas.create_oval(1, 1, 13, 13, fill=C["red"], outline="", tags="dot")

        tk.Label(toolbar, textvariable=self._vid_status_var,
                 font=("Consolas", 8), bg="#0d0d0d", fg="#666666").pack(side=tk.LEFT, padx=10)

        right_tb = tk.Frame(toolbar, bg="#0d0d0d")
        right_tb.pack(side=tk.RIGHT, padx=10)

        tk.Checkbutton(right_tb, text="Vitals HUD",
                       variable=self._hud_var,
                       font=("Consolas", 8, "bold"),
                       bg="#0d0d0d", fg=C["cyan"],
                       selectcolor="#1a1a1a",
                       activebackground="#0d0d0d",
                       activeforeground=C["cyan"]).pack(side=tk.LEFT, padx=8)

        # ── YOLO toggle checkbox ───────────────────────────────────
        tk.Checkbutton(right_tb, text="YOLO Detect",
                       variable=self._yolo_var,
                       font=("Consolas", 8, "bold"),
                       bg="#0d0d0d", fg=C["amber"],
                       selectcolor="#1a1a1a",
                       activebackground="#0d0d0d",
                       activeforeground=C["amber"],
                       command=self._on_yolo_toggle).pack(side=tk.LEFT, padx=8)

        # YOLO status label
        tk.Label(right_tb, textvariable=self._yolo_status_var,
                 font=("Consolas", 7), bg="#0d0d0d",
                 fg=C["amber"]).pack(side=tk.LEFT, padx=4)

        tk.Label(right_tb, textvariable=self._zoom_var,
                 font=("Consolas", 8), bg="#0d0d0d", fg="#555555").pack(side=tk.LEFT, padx=4)

        tk.Button(right_tb, text="📂  LOAD VIDEO",
                  font=("Consolas", 8, "bold"), bg=C["violet"], fg="white",
                  activebackground=C["cyan"], activeforeground="white",
                  relief=tk.FLAT, bd=0, padx=10, pady=6, cursor="hand2",
                  command=self.load_video).pack(side=tk.LEFT, padx=4)

        self._play_btn = tk.Button(right_tb, text="▶  PLAY",
                                   font=("Consolas", 8, "bold"),
                                   bg=C["green"], fg="white",
                                   activebackground=C["teal"], activeforeground="white",
                                   relief=tk.FLAT, bd=0, padx=10, pady=6, cursor="hand2",
                                   command=self.toggle_video)
        self._play_btn.pack(side=tk.LEFT, padx=4)

        tk.Button(right_tb, text="■  STOP",
                  font=("Consolas", 8, "bold"), bg=C["red"], fg="white",
                  activebackground="#8b0000", activeforeground="white",
                  relief=tk.FLAT, bd=0, padx=10, pady=6, cursor="hand2",
                  command=self.stop_video).pack(side=tk.LEFT, padx=4)

        self._vid_canvas = tk.Canvas(parent, bg="#000000",
                                     highlightthickness=0, cursor="crosshair")
        self._vid_canvas.pack(fill=tk.BOTH, expand=True)
        self._vid_canvas.bind("<Configure>", self._on_vid_resize)
        self._draw_vid_placeholder()

        bottom = tk.Frame(parent, bg="#0d0d0d", height=40)
        bottom.pack(fill=tk.X)
        bottom.pack_propagate(False)

        tl_wrap = tk.Frame(bottom, bg="#0d0d0d")
        tl_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=8)

        self._timeline_canvas = tk.Canvas(tl_wrap, bg="#1a1a1a",
                                          height=8, highlightthickness=0)
        self._timeline_canvas.pack(fill=tk.X)

        tk.Label(bottom, textvariable=self._vid_time_var,
                 font=("Consolas", 8), bg="#0d0d0d", fg="#888888").pack(side=tk.LEFT, padx=(0, 20))

        self._vid_alert_lbl = tk.Label(bottom, text="",
                                       font=("Consolas", 8, "bold"),
                                       bg="#0d0d0d", fg=C["red"], anchor=tk.W)
        self._vid_alert_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(bottom, textvariable=self._vid_res_var,
                 font=("Consolas", 7), bg="#0d0d0d", fg="#444444").pack(side=tk.RIGHT, padx=10)

    def _on_yolo_toggle(self):
        """Called when the YOLO checkbox is clicked."""
        if self._yolo_var.get():
            self._ensure_yolo()

    # ── Public API ────────────────────────────────────────────────

    def load_video(self):
        path = filedialog.askopenfilename(
            title="Select Surgical Video",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.m4v"),
                ("All files",   "*.*"),
            ],
        )
        if not path:
            return
        self.stop_video()
        if not CV2_OK:
            messagebox.showerror("Missing library",
                                 "OpenCV (cv2) is required.\n\npip install opencv-python")
            return
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            messagebox.showerror("Cannot open video", f"Failed to open:\n{path}")
            return

        self._video_cap        = cap
        self._video_path       = path
        self._video_fps        = max(1.0, cap.get(cv2.CAP_PROP_FPS) or 25.0)
        total_frames           = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width                  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height                 = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_s             = total_frames / self._video_fps

        self._vid_total_frames = total_frames
        self._vid_duration_s   = duration_s

        fname = os.path.basename(path)
        self._vid_status_var.set(f"LOADED  {fname}")
        self._vid_info_vars["Source"].set(fname[:14])
        self._vid_info_vars["FPS"].set(f"{self._video_fps:.1f}")
        self._vid_info_vars["Frame"].set(f"0/{total_frames}")
        self._vid_info_vars["Duration"].set(
            f"{int(duration_s // 60)}:{int(duration_s % 60):02d}")
        self._vid_info_vars["Resolution"].set(f"{width}×{height}")

        ALERTS.add("INFO", f"Video loaded: {fname}")
        self._start_video()

    def toggle_video(self):
        if not self._video_cap:
            self.load_video()
            return
        if self._video_running:
            self._video_running = False
            self._play_btn.configure(text="▶  PLAY", bg=C["green"])
            self._vid_status_var.set("⏸ PAUSED")
        else:
            self._start_video()

    def stop_video(self):
        self._video_running = False
        if self._render_job is not None:
            try:
                self._app.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        self._reader_thread = None
        if self._video_cap:
            self._video_cap.release()
            self._video_cap = None
        self._play_btn.configure(text="▶  PLAY", bg=C["green"])
        self._vid_status_var.set("■ STOPPED")
        self._draw_vid_placeholder()
        self._vid_time_var.set("00:00 / 00:00")
        self._draw_timeline(0, 1)

    @property
    def is_running(self):
        return self._video_running

    # ── Internal engine ───────────────────────────────────────────

    def _start_video(self):
        if not self._video_cap:
            return
        self._video_running = True
        self._play_btn.configure(text="⏸  PAUSE", bg=C["amber"])
        self._vid_status_var.set(f"▶ PLAYING  {os.path.basename(self._video_path)}")
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break
        self._reader_thread = threading.Thread(target=self._reader_worker, daemon=True)
        self._reader_thread.start()
        self._render_loop()

    def _reader_worker(self):
        cap         = self._video_cap
        fps         = self._video_fps
        frame_delay = 1.0 / fps
        while self._video_running:
            t_start = time.monotonic()
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break
            cur_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            payload = {
                "frame":     frame,
                "cur_frame": cur_frame,
                "total":     self._vid_total_frames,
                "fps":       fps,
                "duration":  self._vid_duration_s,
            }
            try:
                self._frame_queue.put_nowait(payload)
            except queue.Full:
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frame_queue.put_nowait(payload)
                except queue.Full:
                    pass
            elapsed = time.monotonic() - t_start
            sleep_s = frame_delay - elapsed
            if sleep_s > 0:
                time.sleep(sleep_s)

    def _render_loop(self):
        if not self._video_running:
            self._render_job = None
            return
        payload = None
        try:
            payload = self._frame_queue.get_nowait()
        except queue.Empty:
            pass
        if payload is not None:
            self._render_frame(payload)
        self._render_job = self._app.after(30, self._render_loop)

    def _render_frame(self, payload):
        if not CV2_OK or not PIL_OK:
            return
        frame     = payload["frame"]
        cur_frame = payload["cur_frame"]
        total     = payload["total"]
        fps       = payload["fps"]
        duration  = payload["duration"]

        W = self._vid_canvas.winfo_width()
        H = self._vid_canvas.winfo_height()
        if W < 4 or H < 4:
            return

        # ── YOLO inference (runs on main thread, on resized frame) ──
        if self._yolo_var.get() and self._yolo_model:
            results = self._yolo_model.predict(frame, conf=0.25, verbose=False)
            frame   = results[0].plot()   # draws boxes + labels onto frame

        fh, fw  = frame.shape[:2]
        scale   = min(W / fw, H / fh)
        nw, nh  = max(1, int(fw * scale)), max(1, int(fh * scale))
        frame_r   = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        frame_rgb = cv2.cvtColor(frame_r, cv2.COLOR_BGR2RGB)

        if self._hud_var.get():
            frame_rgb = self._draw_hud_overlay(frame_rgb, nw, nh)

        import numpy as np
        img = Image.fromarray(frame_rgb)
        self._video_photo = ImageTk.PhotoImage(image=img)

        self._vid_canvas.delete("all")
        self._vid_canvas.configure(bg="#000000")
        x_off = (W - nw) // 2
        y_off = (H - nh) // 2
        self._vid_canvas.create_image(x_off, y_off, anchor=tk.NW, image=self._video_photo)

        elapsed_s = cur_frame / fps if fps else 0
        self._vid_info_vars["Frame"].set(f"{cur_frame}/{total}")
        self._vid_time_var.set(
            f"{int(elapsed_s // 60)}:{int(elapsed_s % 60):02d} / "
            f"{int(duration // 60)}:{int(duration % 60):02d}")
        self._draw_timeline(cur_frame, total)
        self._zoom_var.set(f"{scale:.2f}×")
        try:
            self._vid_res_var.set(
                f"{self._vid_info_vars['Resolution'].get()}  "
                f"{self._vid_info_vars['FPS'].get()} fps")
        except Exception:
            pass

        unacked = [a for a in ALERTS.alerts if not a["ack"]]
        if unacked:
            a       = unacked[0]
            lvl_col = C["red"] if a["level"] == "CRITICAL" else C["amber"]
            self._vid_alert_lbl.configure(
                text=f"⚠  {a['level']}  —  {a['msg'][:60]}", fg=lvl_col)
        else:
            self._vid_alert_lbl.configure(text="✔  No active alerts", fg="#2e7d32")

    # ── HUD overlay (unchanged) ───────────────────────────────────

    def _draw_hud_overlay(self, frame_rgb, W, H):
        import numpy as np
        img     = Image.fromarray(frame_rgb).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)
        v   = VITALS
        pad = 12

        draw.rectangle([pad, pad, 280, pad + 36], fill=(0, 0, 0, 160))
        draw.rectangle([pad, pad, pad + 4, pad + 36], fill=(0, 119, 182, 255))
        self._hud_text(draw, f"  {PATIENT['name']}  ·  {PATIENT['id']}",
                       pad + 8, pad + 4, size=11, color=(220, 240, 255, 255))
        self._hud_text(draw, f"  {PATIENT['procedure']}",
                       pad + 8, pad + 18, size=9, color=(160, 200, 230, 200))

        from datetime import datetime
        phase = self._app._op_phase.get()
        clk   = datetime.now().strftime("%H:%M:%S")
        tr_x  = W - 180
        draw.rectangle([tr_x, pad, W - pad, pad + 36], fill=(0, 0, 0, 160))
        self._hud_text(draw, clk,   tr_x + 10, pad + 4,  size=14, color=(0, 212, 255, 255))
        self._hud_text(draw, phase, tr_x + 10, pad + 20, size=9,  color=(180, 180, 255, 200))

        box_w, box_h = 100, 52
        vitals_data = [
            ("HR",    f"{v.hr:.0f}",                    "bpm",  (232, 67,  147)),
            ("SpO₂",  f"{v.spo2:.1f}",                  "%",    (0,  212, 255)),
            ("EtCO₂", f"{v.etco2:.1f}",                 "mmHg", (0,  137, 123)),
            ("NIBP",  f"{v.nibp_s:.0f}/{v.nibp_d:.0f}", "mmHg", (108, 92, 231)),
            ("RR",    f"{v.rr:.0f}",                    "/min", (212, 134, 10)),
            ("Temp",  f"{v.temp:.1f}",                  "°C",   (10,  158, 106)),
        ]
        cols = 3
        by   = H - (2 * box_h + pad + 20)
        for idx, (label, val, unit, rgb) in enumerate(vitals_data):
            col = idx % cols
            row = idx // cols
            bx  = pad + col * (box_w + 6)
            ybx = by  + row * (box_h + 4)
            draw.rectangle([bx, ybx, bx + box_w, ybx + box_h], fill=(0, 0, 0, 150))
            draw.rectangle([bx, ybx, bx + 3, ybx + box_h], fill=(*rgb, 255))
            self._hud_text(draw, label, bx + 8, ybx + 4,  size=9,  color=(180, 200, 220, 200))
            self._hud_text(draw, val,   bx + 8, ybx + 16, size=14, color=(*rgb, 255))
            self._hud_text(draw, unit,  bx + 8, ybx + 36, size=8,  color=(140, 160, 180, 180))

        unacked = [a for a in ALERTS.alerts if not a["ack"]]
        if unacked:
            a      = unacked[0]
            al_col = (214, 48, 49) if a["level"] == "CRITICAL" else (212, 134, 10)
            bx2    = W - 260
            draw.rectangle([bx2, H - 60, W - pad, H - pad], fill=(0, 0, 0, 170))
            draw.rectangle([bx2, H - 60, bx2 + 3, H - pad], fill=(*al_col, 255))
            self._hud_text(draw, f"⚠ {a['level']}", bx2 + 8, H - 56, size=10, color=(*al_col, 255))
            self._hud_text(draw, a["msg"][:38],       bx2 + 8, H - 42, size=8,  color=(220, 220, 220, 200))
            self._hud_text(draw, a["time"],            bx2 + 8, H - 28, size=7,  color=(160, 160, 160, 180))

        merged = Image.alpha_composite(img, overlay).convert("RGB")
        import numpy as np
        return np.array(merged)

    @staticmethod
    def _hud_text(draw, text, x, y, size=10, color=(255, 255, 255, 255)):
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        ):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                font = ImageFont.load_default()
        draw.text((x, y), text, font=font, fill=color)

    # ── Helpers (unchanged) ───────────────────────────────────────

    def _draw_timeline(self, cur, total):
        c = self._timeline_canvas
        c.delete("all")
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 4 or total <= 0:
            return
        pct = min(1.0, cur / total)
        c.create_rectangle(0, 0, W, H, fill=C["bg3"], outline="")
        c.create_rectangle(0, 0, int(W * pct), H, fill=C["cyan"], outline="")
        tx = int(W * pct)
        c.create_rectangle(tx - 2, 0, tx + 2, H, fill="white", outline="")

    def _draw_vid_placeholder(self):
        c = self._vid_canvas
        c.delete("all")
        c.configure(bg="#0a0a0a")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        cx, cy = W // 2, H // 2
        for i in range(0, W, 40):
            c.create_line(i, 0, i, H, fill="#111111")
        for j in range(0, H, 40):
            c.create_line(0, j, W, j, fill="#111111")
        c.create_rectangle(cx - 60, cy - 36, cx + 60, cy + 36, outline="#333333", width=2)
        c.create_oval(cx - 20, cy - 16, cx + 20, cy + 16, outline="#444444", width=2)
        c.create_oval(cx - 6,  cy - 6,  cx + 6,  cy + 6,  fill="#333333", outline="")
        c.create_text(cx, cy + 60, text="No video source loaded",
                      fill="#444444", font=("Consolas", 11))
        c.create_text(cx, cy + 80, text="Click  📂 LOAD VIDEO  to select a file",
                      fill="#333333", font=("Consolas", 9))

    def _on_vid_resize(self, event):
        if not self._video_running:
            self._draw_vid_placeholder()

    def _blink_rec_dot(self):
        try:
            if self._video_running:
                self._rec_dot_visible = not self._rec_dot_visible
                color = C["red"] if self._rec_dot_visible else C["bg2"]
                self._rec_canvas.itemconfig("dot", fill=color)
            else:
                self._rec_canvas.itemconfig("dot", fill="#cccccc")
        except Exception:
            pass
        self._app.after(600, self._blink_rec_dot)
