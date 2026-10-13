import cv2
import numpy as np


class LaneDetector:
    def __init__(self, lanes=None):
        self.lanes = lanes or []

    def find(self, point):
        for lane in self.lanes:
            if cv2.pointPolygonTest(np.asarray(lane['points'], np.float32), tuple(map(float, point)), False) >= 0:
                return lane
        return None
