import numpy as np

EVENT_NAMES = {'ABNORMAL STOP': '异常停车', 'HARD BRAKING': '急减速', 'WRONG WAY': '逆行'}


class EventDetector:
    def __init__(self, config):
        self.config = config
        self.stopped = {}
        self.reverse = {}
        self.last_event = {}
        self.previous_speed = {}

    def update(self, vehicle, legal_direction):
        vid, t, speed = vehicle['id'], vehicle['timestamp'], vehicle['speed']
        if speed is None:
            self.stopped.pop(vid, None)
            self.reverse.pop(vid, None)
            self.previous_speed.pop(vid, None)
            return []
        candidates = []
        if speed < self.config['stop_speed']:
            self.stopped.setdefault(vid, t)
            if t-self.stopped[vid] >= self.config['stop_seconds']:
                candidates.append('ABNORMAL STOP')
        else:
            self.stopped.pop(vid, None)
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
        result = []
        for event in candidates:
            key = vid, event
            if t-self.last_event.get(key, -1e9) >= self.config['cooldown_seconds']:
                self.last_event[key] = t
                result.append(dict(timestamp=t, vehicle_id=vid, event=event,
                                   label=EVENT_NAMES[event], lane=vehicle['lane'], speed=speed))
        return result
