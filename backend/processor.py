import base64
import json
import math
import time
from collections import deque
import cv2
from backend.calibration.homography import RoadCalibration
from backend.events.rules import EventDetector
from backend.exporter import CSVExporter
from backend.evidence import capture_event
from backend.settings import DATA
from backend.traffic.flow_counter import FlowCounter
from backend.traffic.lane_detector import LaneDetector
from backend.traffic.speed_estimator import SpeedEstimator
from backend.traffic.traffic_metrics import traffic_metrics
from backend.traffic.vehicle_state import VehicleState
from backend.vision.tracker import SortTracker


def encode_frame(frame, quality=80):
    ok, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError('视频帧编码失败')
    return 'data:image/jpeg;base64,'+base64.b64encode(buffer).decode('ascii')


class TrafficProcessor:
    def __init__(self, reader, detector, config, scene, calibration=None, segment_start=0):
        self.reader, self.detector, self.config = reader, detector, config
        self.scene, self.calibration = scene, calibration
        self.segment_start = segment_start
        self.tracker = SortTracker(config['tracking'])
        self.flow = FlowCounter(scene.get('counting_line'))
        self.lanes = LaneDetector(scene.get('lanes'))
        self.events = EventDetector(config['events'])
        self.states, self.seen = {}, set()
        self.event_log = deque(maxlen=500)
        self.total_events = 0
        self.history = deque(maxlen=600)
        self.lane_history = deque(maxlen=600)
        self.last_history_time = -1.
        self.exporter = CSVExporter()
        self.processing_fps = 0.
        self.frame_times = deque(maxlen=30)

    def step(self):
        with self.exporter.lock:
            return self._step_locked()

    def _step_locked(self):
        started = time.perf_counter()
        item = self.reader.read()
        if item is None:
            self.exporter.flush()
            self.exporter.update_metadata(status='completed', end_timestamp=self.exporter.last_timestamp)
            return None
        index, timestamp, frame = item
        interval = self.config['video']['detection_interval']
        detection_frame = (index % interval == 0 or not self.tracker.tracks)
        detections = self.detector.detect(frame) if detection_frame else None
        tracking_start = time.perf_counter()
        tracks = self.tracker.update(detections)
        tracking_ms = (time.perf_counter()-tracking_start)*1000
        sx = self.reader.width/self.reader.display_width
        sy = self.reader.height/self.reader.display_height
        vehicles = []
        for track in tracks:
            if track.missed > min(self.config['tracking']['max_age'], interval*2):
                continue
            box = (track.box * [sx, sy, sx, sy]).tolist()
            pixel = [(box[0]+box[2])/2, box[3]]
            if not 0 <= pixel[0] <= self.reader.width or not 0 <= pixel[1] <= self.reader.height:
                continue
            self.seen.add(track.id)
            if track.id not in self.states:
                self.states[track.id] = VehicleState(SpeedEstimator(self.config['speed']['smoothing_frames'], self.config['speed']['min_samples']))
            state = self.states[track.id]
            observed = track.missed == 0
            lane = self.lanes.find(pixel)
            world = self.calibration.map(pixel) if self.calibration and self.calibration.contains(pixel) else None
            if observed:
                state.trajectory.append(pixel)
                if world is not None:
                    if state.estimator.points and timestamp-state.estimator.points[-1][0] > max(.5, 2.5*interval/getattr(self.reader, 'fps', 30)):
                        state.estimator.reset()
                        state.world_trajectory.clear()
                        self.events.stopped.pop(track.id, None)
                        self.events.reverse.pop(track.id, None)
                        self.events.previous_speed.pop(track.id, None)
                    state.world_trajectory.append(dict(timestamp=timestamp, point=world))
                    state.speed, state.acceleration = state.estimator.update(timestamp, world)
                else:
                    state.estimator.reset()
                    state.world_trajectory.clear()
                    state.speed = state.acceleration = None
            if world is None:
                speed = acceleration = None
            else:
                speed, acceleration = state.speed, state.acceleration
            trajectory = list(state.trajectory)
            wt = list(state.world_trajectory)
            heading_points = [p['point'] for p in wt] if world is not None else trajectory
            heading = 0.
            if len(heading_points) >= 2:
                a, b = heading_points[max(0, len(heading_points)-6)], heading_points[-1]
                heading = math.atan2(b[1]-a[1], b[0]-a[0])
            vehicle = dict(id=track.id, type=track.detection['type'], confidence=track.detection['confidence'],
                           box=box, pixel=pixel, world=world, speed=speed, acceleration=acceleration,
                           lane=lane['name'] if lane else None, timestamp=timestamp,
                           heading=heading, trajectory=trajectory, world_trajectory=wt, observed=observed)
            if observed:
                self.flow.update(track.id, pixel, timestamp, vehicle['type'], vehicle['lane'])
                new_events = self.events.update(vehicle, lane.get('direction', self.config['traffic']['legal_direction']) if lane else self.config['traffic']['legal_direction'])
                for event in new_events:
                    capture_event(self.exporter, event, vehicle, frame, index, self.reader, self.config, self.scene, self.calibration)
                    state.warning, state.warning_until = event['event'], timestamp+2
                    self.event_log.appendleft(event)
                    self.total_events += 1
                    self.exporter.write('events', event)
            vehicle['status'] = state.warning if timestamp < state.warning_until else 'NORMAL'
            vehicles.append(vehicle)
            self.exporter.write('vehicles', dict(timestamp=timestamp, frame=index, vehicle_id=track.id,
                vehicle_type=vehicle['type'], confidence=vehicle['confidence'], lane=vehicle['lane'],
                x_pixel=pixel[0], y_pixel=pixel[1], x=world[0] if world else None,
                y=world[1] if world else None, speed=speed, acceleration=acceleration,
                status=vehicle['status'], observed=observed))
        live_ids = {t.id for t in self.tracker.tracks}
        # Release trajectory and rule buffers when a track expires.
        for vid in set(self.states)-live_ids:
            del self.states[vid]
            self.events.stopped.pop(vid, None)
            self.events.reverse.pop(vid, None)
            self.events.previous_speed.pop(vid, None)
            for key in [key for key in self.events.last_event if key[0] == vid]:
                self.events.last_event.pop(key, None)
            self.flow.previous.pop(vid, None)
        metrics = traffic_metrics(vehicles, self.seen, self.flow, timestamp, self.calibration, self.lanes.lanes, self.segment_start)
        metrics['event_count'] = self.total_events
        self.exporter.write('traffic_statistics', dict(timestamp=timestamp, flow=metrics['total_flow'], **metrics))
        self.exporter.flush()
        if timestamp-self.last_history_time >= .5:
            self.history.append(dict(timestamp=timestamp, vehicle_count=metrics['vehicle_count'],
                average_speed=metrics['average_speed'], flow=metrics['total_flow']))
            lane_rows = []
            lane_names = [lane['name'] for lane in self.lanes.lanes]
            if any(v['lane'] is None for v in vehicles) or self.flow.by_lane['未划分']:
                lane_names.append('未划分')
            for lane_name in lane_names:
                lane_vehicles = [v for v in vehicles if (v['lane'] or '未划分') == lane_name]
                observed = [v for v in lane_vehicles if v['observed']]
                speeds = [v['speed'] for v in observed if v['speed'] is not None]
                for window in (10, 30, 60):
                    row = dict(timestamp=timestamp, lane=lane_name, observed_count=len(observed),
                               predicted_count=len(lane_vehicles)-len(observed),
                               average_speed=sum(speeds)/len(speeds) if speeds else None,
                               cumulative_flow=self.flow.by_lane[lane_name],
                               **self.flow.lane_window(timestamp, lane_name, window, self.segment_start))
                    lane_rows.append(row)
                    self.exporter.write('lane_statistics', row)
            self.lane_history.append(dict(timestamp=timestamp, lanes=lane_rows))
            self.exporter.flush()
            self.last_history_time = timestamp
        image = encode_frame(frame, self.config['video']['jpeg_quality'])
        elapsed = time.perf_counter()-started
        self.frame_times.append(elapsed)
        self.processing_fps = len(self.frame_times)/max(.0001, sum(self.frame_times))
        return dict(frame=index, timestamp=timestamp, image=image, vehicles=vehicles, metrics=metrics,
                    events=list(self.event_log), history=list(self.history), lane_history=list(self.lane_history),
                    detection_ms=self.detector.detect_ms if detection_frame else 0.,
                    tracking_ms=tracking_ms, processing_fps=self.processing_fps,
                    detection_frame=detection_frame, run_id=self.exporter.run_id,
                    segment_start=self.segment_start, device=self.detector.device)

    def close(self):
        self.exporter.close()
