from collections import Counter, deque
import numpy as np


class FlowCounter:
    def __init__(self, line=None):
        self.line = np.array(line, float) if line is not None else None
        self.previous = {}
        self.counted = set()
        self.crossings = deque()
        self.first_crossing = self.last_crossing = None
        self.crossing_count = 0
        self.by_type = Counter()
        self.by_lane = Counter()

    def forget(self, vehicle_id):
        self.previous.pop(vehicle_id, None)

    def update(self, vehicle_id, point, timestamp, vehicle_type, lane):
        previous = self.previous.get(vehicle_id)
        self.previous[vehicle_id] = np.asarray(point, float)
        if self.line is None or previous is None or vehicle_id in self.counted:
            return False
        a, b = self.line
        r, s = b-a, np.asarray(point)-previous
        cross = lambda x, y: float(x[0]*y[1]-x[1]*y[0])
        denominator = cross(r, s)
        if abs(denominator) < 1e-9:
            return False
        t = cross(previous-a, s)/denominator
        u = cross(previous-a, r)/denominator
        if 0 <= t <= 1 and 0 < u <= 1:
            self.counted.add(vehicle_id)
            self.crossings.append((timestamp, lane or '未划分'))
            if self.first_crossing is None:
                self.first_crossing = timestamp
            self.last_crossing = timestamp
            self.crossing_count += 1
            self.by_type[vehicle_type] += 1
            self.by_lane[lane or '未划分'] += 1
            return True
        return False

    def metrics(self, timestamp, segment_start=0):
        elapsed = max(0., timestamp-segment_start)
        while self.crossings and self.crossings[0][0] <= timestamp-60:
            self.crossings.popleft()
        count = len(self.crossings)
        # Rates are explicitly estimates until a full observation window exists.
        return dict(total_flow=len(self.counted), flow_per_min=count*60/min(60, elapsed) if elapsed > 0 else 0,
                    flow_per_hour=count*60 if elapsed >= 60 else None,
                    flow_estimated=elapsed < 60, flow_by_type=dict(self.by_type), flow_by_lane=dict(self.by_lane))

    def lane_window(self, timestamp, lane, window, segment_start=0):
        if window not in (10, 30, 60):
            raise ValueError('窗口必须是 10、30 或 60 秒')
        covered = min(window, max(0., timestamp - segment_start))
        count = sum(1 for t, name in self.crossings if name == lane and timestamp-window < t <= timestamp)
        return dict(window_seconds=window, window_flow=count, covered_seconds=covered,
                    complete=covered >= window)

    @property
    def average_headway(self):
        return (self.last_crossing-self.first_crossing)/(self.crossing_count-1) if self.crossing_count > 1 else None
