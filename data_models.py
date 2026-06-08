import random
import threading
import time
from datetime import datetime

from constants import C


# ═══════════════════════════════════════════════════════════════════
#  ALERT SYSTEM
# ═══════════════════════════════════════════════════════════════════

class AlertSystem:
    """Manages system alerts and safety notifications."""

    def __init__(self):
        self.alerts = [
            {"level": "INFO",     "msg": "Robot calibration verified — all axes nominal",    "time": "08:14", "ack": True},
            {"level": "WARNING",  "msg": "Joint 2 approaching soft limit (142° / 150°)",    "time": "08:31", "ack": False},
            {"level": "INFO",     "msg": "Target zone confirmed by imaging overlay",         "time": "08:33", "ack": True},
            {"level": "CRITICAL", "msg": "Proximity alert — 8 mm from No-Go Zone A",        "time": "08:47", "ack": False},
            {"level": "WARNING",  "msg": "Instrument force exceeded 4 N — reduce pressure", "time": "08:52", "ack": False},
        ]
        self.callbacks = []

    def add(self, level, msg):
        """Add a new alert and notify all registered callbacks."""
        t = datetime.now().strftime("%H:%M")
        self.alerts.insert(0, {"level": level, "msg": msg, "time": t, "ack": False})
        for cb in self.callbacks:
            cb()

    def ack_all(self):
        """Acknowledge all pending alerts."""
        for a in self.alerts:
            a["ack"] = True
        for cb in self.callbacks:
            cb()


# Singleton instance used application-wide
ALERTS = AlertSystem()


# ═══════════════════════════════════════════════════════════════════
#  VITALS MONITOR  (simulated streaming)
# ═══════════════════════════════════════════════════════════════════

class VitalsMonitor:
    """Continuously simulates patient vital signs on a background thread."""

    def __init__(self):
        self.hr      = 72.0
        self.spo2    = 98.0
        self.nibp_s  = 124.0
        self.nibp_d  = 78.0
        self.etco2   = 35.0
        self.rr      = 14.0
        self.temp    = 36.6
        self.history = {"hr": [], "spo2": [], "etco2": []}
        self._running = False

    def start(self, callback):
        """Start the background simulation loop.

        Args:
            callback: Called on the main thread once per second with updated values.
        """
        self._running = True

        def _loop():
            while self._running:
                self.hr     = max(50,  min(120,  self.hr    + random.gauss(0, 0.6)))
                self.spo2   = max(92,  min(100,  self.spo2  + random.gauss(0, 0.08)))
                self.nibp_s = max(100, min(160,  self.nibp_s + random.gauss(0, 0.4)))
                self.nibp_d = max(60,  min(100,  self.nibp_d + random.gauss(0, 0.3)))
                self.etco2  = max(28,  min(50,   self.etco2 + random.gauss(0, 0.3)))
                self.rr     = max(8,   min(22,   self.rr    + random.gauss(0, 0.1)))
                self.temp   = max(35,  min(38.5, self.temp  + random.gauss(0, 0.02)))

                for k, v in [("hr", self.hr), ("spo2", self.spo2), ("etco2", self.etco2)]:
                    self.history[k].append(v)
                    if len(self.history[k]) > 60:
                        self.history[k].pop(0)

                callback()
                time.sleep(1.0)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def stop(self):
        """Stop the background simulation loop."""
        self._running = False


# Singleton instance used application-wide
VITALS = VitalsMonitor()
