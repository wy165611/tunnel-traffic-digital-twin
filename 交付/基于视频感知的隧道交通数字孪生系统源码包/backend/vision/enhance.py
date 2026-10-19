"""Optional tunnel low-light enhancement: CLAHE on luminance plus gamma."""
import cv2
import numpy as np


def clamp(value, default, low, high):
    try:
        return min(high, max(low, float(value)))
    except (TypeError, ValueError):
        return default


class LowLightEnhancer:
    """Compiled once per processor; disabled instances leave frames untouched."""

    def __init__(self, config=None):
        config = config or {}
        self.enabled = bool(config.get('low_light_enabled'))
        self.clip_limit = clamp(config.get('clahe_clip_limit', 2.), 2., 1., 10.)
        self.gamma = clamp(config.get('gamma', 1.5), 1.5, .5, 3.)
        self.clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=(8, 8)) if self.enabled else None
        self.lut = None
        if self.enabled and abs(self.gamma-1.) > 1e-6:
            values = np.arange(256, dtype=np.float32)/255.
            self.lut = np.clip((values**(1./self.gamma))*255., 0, 255).astype(np.uint8)

    def apply(self, frame):
        if not self.enabled:
            return frame
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        luminance, a, b = cv2.split(lab)
        luminance = self.clahe.apply(luminance)
        result = cv2.cvtColor(cv2.merge((luminance, a, b)), cv2.COLOR_LAB2BGR)
        if self.lut is not None:
            result = cv2.LUT(result, self.lut)
        return result
