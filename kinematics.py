import math
import numpy as np


# ═══════════════════════════════════════════════════════════════════
#  D-H KINEMATICS
# ═══════════════════════════════════════════════════════════════════

def dh_mat(a, alpha_d, d, theta_d):
    """Build a single D-H transformation matrix."""
    al, th = math.radians(alpha_d), math.radians(theta_d)
    ct, st, ca, sa = math.cos(th), math.sin(th), math.cos(al), math.sin(al)
    return np.array([
        [ct, -st * ca,  st * sa, a * ct],
        [st,  ct * ca, -ct * sa, a * st],
        [0,   sa,       ca,      d     ],
        [0,   0,        0,       1     ],
    ])


def fk(dh):
    """Compute forward kinematics for the full chain.

    Returns a list of 4×4 homogeneous transforms, one per joint
    (index 0 is the base frame, last is the end-effector frame).
    """
    T, Ts = np.eye(4), [np.eye(4)]
    for p in dh:
        T = T @ dh_mat(p["a"], p["alpha"], p["d"], p["theta"])
        Ts.append(T.copy())
    return Ts


def joint_pos(Ts):
    """Extract the origin (XYZ) of each frame from a list of transforms."""
    return [T[:3, 3] for T in Ts]


# ═══════════════════════════════════════════════════════════════════
#  CAMERA
# ═══════════════════════════════════════════════════════════════════

class Camera3D:
    """Simple orthographic-ish camera for 3-D viewport projection."""

    def __init__(self):
        self.az    = 40.0   # azimuth  (degrees)
        self.el    = 28.0   # elevation (degrees)
        self.scale = 380.0
        self.cx    = 0.0    # canvas centre X
        self.cy    = 0.0    # canvas centre Y

    def project(self, x, y, z):
        """Project a 3-D world point to 2-D canvas coordinates."""
        az  = math.radians(self.az)
        el  = math.radians(self.el)
        x2  =  x * math.cos(az) + y * math.sin(az)
        y2  = -x * math.sin(az) + y * math.cos(az)
        y3  =  y2 * math.cos(el) - z * math.sin(el)
        return x2 * self.scale + self.cx, -y3 * self.scale + self.cy, 0
