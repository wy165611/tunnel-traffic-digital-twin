from dataclasses import dataclass, field
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


def box_state(box):
    x1, y1, x2, y2 = box
    return np.array([(x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1], np.float32)


def state_box(state):
    x, y, w, h = np.asarray(state).flatten()[:4]
    w, h = max(2., w), max(2., h)
    return np.array([x-w/2, y-h/2, x+w/2, y+h/2])


def iou(a, b):
    lo, hi = np.maximum(a[:2], b[:2]), np.minimum(a[2:], b[2:])
    inter = float(np.prod(np.maximum(hi-lo, 0)))
    area_a = np.prod(np.maximum(a[2:]-a[:2], 0))
    area_b = np.prod(np.maximum(b[2:]-b[:2], 0))
    return inter / max(1e-9, area_a+area_b-inter)


@dataclass
class Track:
    id: int
    detection: dict
    filter: object = field(init=False)
    missed: int = 0
    hits: int = 1

    def __post_init__(self):
        k = cv2.KalmanFilter(8, 4)
        k.transitionMatrix = np.eye(8, dtype=np.float32)
        k.transitionMatrix[:4, 4:] = np.eye(4, dtype=np.float32)
        k.measurementMatrix = np.eye(4, 8, dtype=np.float32)
        k.processNoiseCov = np.diag([1, 1, .1, .1, .3, .3, .01, .01]).astype(np.float32)
        k.measurementNoiseCov = np.eye(4, dtype=np.float32) * 4
        k.errorCovPost = np.diag([10]*4 + [100]*4).astype(np.float32)
        k.statePost = np.r_[box_state(self.detection['box']), np.zeros(4)].astype(np.float32).reshape(8, 1)
        self.filter = k

    @property
    def box(self):
        return state_box(self.filter.statePost)

    def predict(self):
        self.filter.predict()
        self.missed += 1

    def update(self, detection):
        self.filter.correct(box_state(detection['box']).reshape(4, 1))
        # Retain class on low-confidence fluctuations.
        if detection['confidence'] >= self.detection['confidence'] - .1:
            self.detection['type'] = detection['type']
        self.detection['confidence'] = detection['confidence']
        self.hits += 1
        self.missed = 0


class SortTracker:
    """SORT style constant velocity Kalman filter + gated Hungarian IoU matching."""
    def __init__(self, config):
        self.config, self.tracks, self.next_id = config, [], 1

    def update(self, detections=None):
        for track in self.tracks:
            track.predict()
        if detections is not None:
            unmatched = set(range(len(detections)))
            if self.tracks and detections:
                overlaps = np.array([[iou(t.box, d['box']) for d in detections] for t in self.tracks])
                # Gating before assignment avoids invalid pairs stealing valid ones.
                cost = np.where(overlaps >= self.config['iou_threshold'], 1-overlaps, 1e5)
                rows, cols = linear_sum_assignment(cost)
                for row, col in zip(rows, cols):
                    if cost[row, col] < 1e5:
                        self.tracks[row].update(detections[col])
                        unmatched.discard(int(col))
            for index in sorted(unmatched):
                self.tracks.append(Track(self.next_id, detections[index].copy()))
                self.next_id += 1
        self.tracks = [t for t in self.tracks if t.missed <= self.config['max_age']]
        return [t for t in self.tracks if t.hits >= self.config['min_hits']]
