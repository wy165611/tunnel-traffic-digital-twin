"""Static road debris heuristic on the existing virtual loops.

A loop that stays covered by foreground pixels while no observed vehicle is
inside is treated as a stationary object or spill. This is deliberately a
heuristic: it never claims a debris class, it only flags an unexplained
occupation that a human should review in the saved evidence.
"""
import cv2
import numpy as np
from backend.events.rules import EVENT_NAMES
from backend.traffic.service_level import scene_loops


class DebrisDetector:
    # Foreground learns very slowly, so a static object survives long enough to
    # alert while gradual exposure drift is still absorbed. A jump covering most
    # of the frame is lighting, not debris, and rebuilds the background.
    FOREGROUND_ALPHA = .002
    GLOBAL_CHANGE_RATIO = .6

    def __init__(self, scene, config, width, height, scale=1., enabled=None):
        self.config = config
        self.size = (int(width), int(height))
        self.scale = float(scale) or 1.
        self.seconds = max(.5, self._number(config.get('debris_seconds'), 2.))
        self.area_ratio = min(1., max(.01, self._number(config.get('debris_area_ratio'), .18)))
        self.threshold = int(min(255, max(1, self._number(config.get('debris_difference_threshold'), 30))))
        self.cooldown = max(0., self._number(config.get('debris_cooldown_seconds'), 30.))
        self.alpha = .05
        self.background = None
        self.loops = self._loops(scene.get('lanes') or [])
        self.enabled = bool(config.get('debris_enabled', True) if enabled is None else enabled) and bool(self.loops)

    @staticmethod
    def _number(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _loops(self, lanes):
        loops = {}
        width, height = self.size
        for item in scene_loops(lanes):
            points = np.asarray(item['points'], float)*self.scale
            points[:, 0] = np.clip(points[:, 0], 0, width-1)
            points[:, 1] = np.clip(points[:, 1], 0, height-1)
            contour = points.astype(np.int32)
            if cv2.contourArea(contour) < 4:
                continue
            mask = np.zeros((height, width), np.uint8)
            cv2.fillPoly(mask, [contour], 255)
            area = int(np.count_nonzero(mask))
            if not area:
                continue
            loops[item['lane']] = dict(mask=mask.astype(bool), points=points, contour=contour,
                                       area=area, since=None, last_event=-1e9)
        return loops

    def _foreground(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self.background is None or self.background.shape != gray.shape:
            self.background = gray.astype(np.float32)
            return None
        difference = cv2.absdiff(gray, cv2.convertScaleAbs(self.background))
        mask = (difference >= self.threshold).astype(np.uint8)
        if float(np.count_nonzero(mask))/mask.size > self.GLOBAL_CHANGE_RATIO:
            self.background = gray.astype(np.float32)
            self._reset_state()
            return None
        rate = np.where(mask > 0, self.FOREGROUND_ALPHA, self.alpha).astype(np.float32)
        self.background = self.background*(1-rate)+gray.astype(np.float32)*rate
        return mask

    def _reset_state(self):
        for data in self.loops.values():
            data['since'] = None

    def _vehicle_inside(self, data, vehicles):
        center = data['points'].mean(axis=0)
        for vehicle in vehicles or []:
            if not vehicle.get('observed') or vehicle.get('pixel') is None:
                continue
            x, y = float(vehicle['pixel'][0])*self.scale, float(vehicle['pixel'][1])*self.scale
            if cv2.pointPolygonTest(data['contour'], (x, y), False) >= 0:
                return True
            box = vehicle.get('box')
            if box and len(box) == 4:
                x1, y1, x2, y2 = [float(value)*self.scale for value in box]
                if x1 <= center[0] <= x2 and y1 <= center[1] <= y2:
                    return True
        return False

    def update(self, timestamp, frame, vehicles=None):
        """Return [(event, pseudo_vehicle)] for loops newly judged as debris."""
        if not self.enabled:
            return []
        foreground = self._foreground(frame)
        if foreground is None:
            return []
        results = []
        for lane, data in self.loops.items():
            ratio = float(np.count_nonzero(foreground[data['mask']]))/data['area']
            if ratio < self.area_ratio or self._vehicle_inside(data, vehicles):
                data['since'] = None
                continue
            if data['since'] is None:
                data['since'] = timestamp
            if timestamp-data['since'] < self.seconds or timestamp-data['last_event'] < self.cooldown:
                continue
            data['last_event'] = timestamp
            results.append(self._event(timestamp, lane, data))
        return results

    def _event(self, timestamp, lane, data):
        points = data['points']/self.scale
        x1, y1 = points.min(axis=0)
        x2, y2 = points.max(axis=0)
        center = points.mean(axis=0)
        event = dict(timestamp=timestamp, vehicle_id=-1, event='ROAD DEBRIS',
                     label=EVENT_NAMES['ROAD DEBRIS'], lane=lane, speed=None, object='debris')
        vehicle = dict(id=-1, type='debris', confidence=1., box=[float(x1), float(y1), float(x2), float(y2)],
                       pixel=[float(center[0]), float(center[1])], world=None, speed=None, lane=lane,
                       timestamp=timestamp, observed=True, world_trajectory=[])
        return event, vehicle
