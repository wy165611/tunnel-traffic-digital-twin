import numpy as np

EVENT_NAMES = {
    'ABNORMAL STOP': '异常停车',
    'HARD BRAKING': '急减速',
    'WRONG WAY': '逆行',
    'SPEEDING': '超速',
    'SLOW SPEED': '低速行驶',
    'ILLEGAL LANE CHANGE': '违规变道',
    'CLOSE FOLLOWING': '跟车过近',
    'PEDESTRIAN INTRUSION': '行人闯入',
    'NON MOTOR INTRUSION': '非机动车闯入',
}
INTRUSION_TYPES = {'person': 'PEDESTRIAN INTRUSION', 'bicycle': 'NON MOTOR INTRUSION'}


class EventDetector:
    """Per-track trajectory rules; speed rules only run with calibrated speed."""

    def __init__(self, config, calibration_available=True):
        self.config = config
        # Speed, headway and queue rules are one calibration-dependent group.
        # Without a metric road scale they stay silent instead of faking values.
        self.calibration_available = calibration_available
        self.stopped = {}
        self.reverse = {}
        self.last_event = {}
        self.previous_speed = {}
        self.lane_state = {}

    def forget(self, vehicle_id):
        for values in (self.stopped, self.reverse, self.previous_speed, self.lane_state):
            values.pop(vehicle_id, None)
        for key in [key for key in self.last_event if key[0] == vehicle_id]:
            self.last_event.pop(key, None)

    def _lane_change(self, vid, lane, t):
        state = self.lane_state.get(vid)
        if lane is None:
            self.lane_state.pop(vid, None)
            return False
        if state is None:
            self.lane_state[vid] = dict(lane=lane, since=t, reported=True)
            return False
        if state['lane'] != lane:
            self.lane_state[vid] = dict(lane=lane, since=t, reported=False)
            return False
        if (self.config.get('lane_change_enabled', True) and not state['reported']
                and t-state['since'] >= self.config['lane_change_seconds']):
            state['reported'] = True
            return True
        return False

    def _close_following(self, vehicle, vehicles):
        if not self.config.get('tailgating_enabled', True):
            return False
        speed, world, lane = vehicle.get('speed'), vehicle.get('world'), vehicle.get('lane')
        if speed is None or speed <= self.config['stop_speed'] or world is None or lane is None:
            return False
        direction = np.asarray(vehicle.get('lane_direction') or [0, 1], float)
        norm = float(np.linalg.norm(direction))
        if norm < .1:
            return False
        direction = direction/norm
        position = float(np.asarray(world, float)@direction)
        gaps = []
        for other in vehicles or []:
            if other.get('id') == vehicle.get('id') or other.get('lane') != lane:
                continue
            if not other.get('observed') or other.get('world') is None:
                continue
            gap = float(np.asarray(other['world'], float)@direction)-position
            if gap > 0:
                gaps.append(gap)
        if not gaps:
            return False
        headway = min(gaps)/(speed/3.6)
        return headway < self.config['tailgating_headway_seconds']

    def update(self, vehicle, legal_direction, vehicles=None, speed_limit=None):
        vid, t, speed = vehicle['id'], vehicle['timestamp'], vehicle['speed']
        candidates = []
        intrusion = INTRUSION_TYPES.get(vehicle.get('type'))
        if intrusion and self.config.get('intrusion_enabled', True):
            candidates.append(intrusion)
        if not intrusion and self._lane_change(vid, vehicle.get('lane'), t) and vehicle.get('lane_solid', True):
            candidates.append('ILLEGAL LANE CHANGE')
        if intrusion:
            pass
        elif speed is None or not self.calibration_available:
            for values in (self.stopped, self.reverse, self.previous_speed):
                values.pop(vid, None)
        else:
            if speed < self.config['stop_speed']:
                self.stopped.setdefault(vid, t)
                if t-self.stopped[vid] >= self.config['stop_seconds']:
                    candidates.append('ABNORMAL STOP')
            else:
                self.stopped.pop(vid, None)
            if self.config.get('speeding_enabled', True) and speed > (speed_limit if speed_limit is not None else self.config['speeding_kmh']):
                candidates.append('SPEEDING')
            if (self.config.get('slow_speed_enabled', True) and speed < self.config['slow_speed_kmh']
                    and speed > self.config['stop_speed']):
                candidates.append('SLOW SPEED')
            # Difference over >=0.5s avoids per-frame acceleration spikes.
            samples = self.previous_speed.setdefault(vid, [])
            samples.append((t, speed/3.6))
            while len(samples) > 1 and t-samples[1][0] >= .5:
                samples.pop(0)
            if t-samples[0][0] >= .5:
                acc = (speed/3.6-samples[0][1])/(t-samples[0][0])
                if acc < self.config['hard_braking_acceleration']:
                    candidates.append('HARD BRAKING')
            direction = np.asarray(legal_direction, float)
            trajectory = vehicle['world_trajectory']
            interval = trajectory[-1]['timestamp']-trajectory[-2]['timestamp'] if len(trajectory) >= 2 else 0
            window = max(.7, interval * 1.5)
            valid = [p for p in trajectory if p['timestamp'] >= t-window]
            if len(valid) >= 2:
                movement = np.asarray(valid[-1]['point'])-np.asarray(valid[0]['point'])
                norm = np.linalg.norm(movement)*np.linalg.norm(direction)
                reverse = speed > self.config['stop_speed'] and norm > .05 and movement@direction/norm < self.config['wrong_way_cosine']
                if reverse:
                    self.reverse.setdefault(vid, t)
                    if t-self.reverse[vid] >= self.config['wrong_way_seconds']:
                        candidates.append('WRONG WAY')
                else:
                    self.reverse.pop(vid, None)
            else:
                self.reverse.pop(vid, None)
            if self._close_following(vehicle, vehicles):
                candidates.append('CLOSE FOLLOWING')
        result = []
        for event in candidates:
            key = vid, event
            if t-self.last_event.get(key, -1e9) >= self.config['cooldown_seconds']:
                self.last_event[key] = t
                result.append(dict(timestamp=t, vehicle_id=vid, event=event,
                                   label=EVENT_NAMES[event], lane=vehicle['lane'], speed=speed))
        return result
