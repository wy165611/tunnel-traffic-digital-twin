import csv
import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from backend.settings import DATA

FIELDS = {
    'vehicles': ['timestamp', 'frame', 'vehicle_id', 'vehicle_type', 'confidence', 'lane', 'x_pixel', 'y_pixel', 'x', 'y', 'speed', 'acceleration', 'status', 'observed'],
    'traffic_statistics': ['timestamp', 'vehicle_count', 'total_vehicles', 'average_speed', 'max_speed', 'min_speed', 'flow', 'flow_per_min', 'flow_estimated', 'density', 'density_estimated', 'density_per_lane', 'occupancy', 'level_of_service', 'service_level_label', 'queue_vehicles', 'queue_length_m', 'queue_estimated', 'congestion_level', 'congestion_label'],
    'events': ['timestamp', 'vehicle_id', 'event', 'lane', 'speed', 'event_id', 'run_id', 'lane_json'],
    'lane_statistics': ['timestamp', 'lane', 'observed_count', 'predicted_count', 'average_speed', 'cumulative_flow', 'window_seconds', 'window_flow', 'covered_seconds', 'complete', 'density', 'flow_per_hour', 'occupancy', 'level_of_service', 'service_level_label', 'queue_vehicles', 'queue_length_m', 'queue_estimated', 'congestion_level', 'congestion_label', 'lane_json'],
}


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def csv_value(value):
    if isinstance(value, float):
        return round(value, 5)
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


class CSVExporter:
    def __init__(self):
        self.run_id = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:6]
        self.directory = DATA / 'runs' / self.run_id
        self.directory.mkdir(parents=True)
        self.lock = threading.RLock()
        self.files, self.writers = {}, {}
        self.metadata = dict(run_id=self.run_id, created_at=datetime.now(timezone.utc).isoformat(),
                             status='recording', end_timestamp=None)
        self.last_timestamp = None
        try:
            for name, columns in FIELDS.items():
                f = (self.directory / f'{name}.csv').open('w', newline='', encoding='utf-8-sig')
                self.files[name] = f
                w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                w.writeheader()
                f.flush()
                self.writers[name] = w
            self.update_metadata()
        except Exception:
            for f in self.files.values():
                f.close()
            raise

    def update_metadata(self, **changes):
        with self.lock:
            self.metadata.update(changes)
            atomic_json(self.directory / 'run.json', self.metadata)

    def write(self, name, row):
        with self.lock:
            if 'lane_json' in FIELDS[name]:
                row = dict(row, lane_json=json.dumps(row.get('lane'), ensure_ascii=False))
            self.writers[name].writerow({k: csv_value(v) for k, v in row.items()})
            if row.get('timestamp') is not None:
                self.last_timestamp = row['timestamp']

    def flush(self):
        with self.lock:
            for f in self.files.values():
                if not f.closed:
                    f.flush()

    def snapshot(self, kind, destination):
        with self.lock:
            self.flush()
            shutil.copyfile(self.directory / (kind + '.csv'), destination)

    def snapshot_all(self, destination):
        with self.lock:
            self.flush()
            metadata = dict(self.metadata, end_timestamp=self.last_timestamp)
            atomic_json(destination / 'run.json', metadata)
            for name in FIELDS:
                shutil.copyfile(self.directory / (name + '.csv'), destination / (name + '.csv'))
            if (self.directory / 'reviews.json').is_file():
                shutil.copyfile(self.directory / 'reviews.json', destination / 'reviews.json')

    def close(self):
        with self.lock:
            if all(f.closed for f in self.files.values()):
                return
            self.flush()
            self.update_metadata(status='completed' if self.metadata['status'] == 'completed' else 'closed',
                                 end_timestamp=self.last_timestamp)
            for f in self.files.values():
                f.close()
