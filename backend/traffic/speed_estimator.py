from collections import deque
import numpy as np


class SpeedEstimator:
    def __init__(self, window=10, min_samples=5):
        self.points = deque(maxlen=window)
        self.speeds = deque(maxlen=3)
        self.min_samples = min_samples
        self.last = None

    def reset(self):
        self.points.clear()
        self.speeds.clear()
        self.last = None

    def update(self, timestamp, world):
        self.points.append((timestamp, *world))
        if len(self.points) < self.min_samples or self.points[-1][0]-self.points[0][0] < .1:
            return None, None
        data = np.array(self.points)
        dt = data[:, 0] - data[:, 0].mean()
        # Least-squares velocity across a window reduces bbox jitter.
        velocity = dt @ (data[:, 1:] - data[:, 1:].mean(axis=0)) / (dt @ dt)
        self.speeds.append(float(np.linalg.norm(velocity)))
        speed_ms = float(np.mean(self.speeds))
        acceleration = None
        if self.last is not None and timestamp > self.last[0]:
            acceleration = (speed_ms - self.last[1]) / (timestamp-self.last[0])
        self.last = timestamp, speed_ms
        return speed_ms*3.6, acceleration
