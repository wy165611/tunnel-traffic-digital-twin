import os
import types
import cv2
import numpy as np
import pytest
import backend.service as service_module
import backend.vision.video_reader as video_reader
from backend.processor import TrafficProcessor
from backend.settings import load_config
from backend.vision.video_reader import VideoReader
from test_api import client


class Clock:
    def __init__(self): self.value = 0.
    def now(self): return self.value


class FakeCapture:
    instances = []
    opened_plan = [True, False, False, True]

    def __init__(self, source, api=None, params=None):
        self.number = len(FakeCapture.instances)
        FakeCapture.instances.append(self)
        self.source = source
        self.api, self.params = api, params
        self.raw_ms = 1000. if self.number == 0 else 5000.
        self.reads = 0
    def isOpened(self): return self.opened_plan[self.number]
    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: 320., cv2.CAP_PROP_FRAME_HEIGHT: 240.,
                cv2.CAP_PROP_FPS: 10., cv2.CAP_PROP_FRAME_COUNT: 0., cv2.CAP_PROP_POS_MSEC: self.raw_ms}.get(prop, 0.)
    def read(self):
        self.reads += 1
        if self.number == 0 and self.reads == 1: return True, np.zeros((240, 320, 3), np.uint8)
        if self.number == 3: return True, np.zeros((240, 320, 3), np.uint8)
        return False, None
    def set(self, *args): return True
    def release(self): pass


def test_live_reader_prefers_tcp_and_bounds_open_and_read_timeouts(monkeypatch):
    FakeCapture.instances = []
    monkeypatch.setenv('OPENCV_FFMPEG_CAPTURE_OPTIONS', '')
    monkeypatch.setattr(video_reader.cv2, 'VideoCapture', FakeCapture)
    reader = VideoReader('rtsp://camera.local/live', open_timeout=5, read_timeout=7)
    capture = FakeCapture.instances[0]
    assert capture.api == cv2.CAP_FFMPEG
    assert capture.params == [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                              cv2.CAP_PROP_READ_TIMEOUT_MSEC, 7000]
    assert 'rtsp_transport;tcp' in os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS']
    assert reader.open_timeout == 5 and reader.read_timeout == 7
    reader.close()


def test_live_reader_reconnects_with_exponential_backoff(monkeypatch):
    FakeCapture.instances = []
    clock = Clock()
    monkeypatch.setattr(video_reader.cv2, 'VideoCapture', FakeCapture)
    monkeypatch.setattr(video_reader, 'time', types.SimpleNamespace(monotonic=clock.now))
    reader = VideoReader('rtsp://camera.local/live')
    first = reader.read()
    assert first is not None and first[1] == pytest.approx(1.)
    assert reader.metadata['stream_state'] == 'connected'
    assert reader.read() is None
    assert reader.metadata['stream_state'] == 'reconnecting' and reader.metadata['reconnect_attempt'] == 1
    assert reader.read() is None and len(FakeCapture.instances) == 1  # waits one second
    clock.value = 1.
    assert reader.read() is None and len(FakeCapture.instances) == 2  # first retry fails
    assert FakeCapture.instances[1].api == cv2.CAP_FFMPEG and FakeCapture.instances[1].params
    assert reader.metadata['reconnect_attempt'] == 2
    clock.value = 3.
    assert reader.read() is None and len(FakeCapture.instances) == 3  # waits two seconds
    clock.value = 7.
    resumed = reader.read()  # waits four seconds, then succeeds
    assert resumed is not None and len(FakeCapture.instances) == 4
    assert resumed[1] == pytest.approx(1.1) and resumed[1] > first[1]
    assert reader.metadata['stream_state'] == 'connected' and reader.metadata['reconnect_attempt'] == 0
    with pytest.raises(ValueError, match='实时流'):
        reader.seek(1)


def test_live_reconnect_flags_resolution_change_and_keeps_original_space(monkeypatch):
    class ChangingCapture(FakeCapture):
        opened_plan = [True, True]
        def get(self, prop):
            if prop == cv2.CAP_PROP_FRAME_WIDTH: return 320. if self.number == 0 else 640.
            if prop == cv2.CAP_PROP_FRAME_HEIGHT: return 240. if self.number == 0 else 480.
            return super().get(prop)
        def read(self):
            self.reads += 1
            if self.number == 0 and self.reads == 1: return True, np.zeros((240, 320, 3), np.uint8)
            if self.number == 1: return True, np.zeros((480, 640, 3), np.uint8)
            return False, None
    FakeCapture.instances = []
    clock = Clock()
    monkeypatch.setattr(video_reader.cv2, 'VideoCapture', ChangingCapture)
    monkeypatch.setattr(video_reader, 'time', types.SimpleNamespace(monotonic=clock.now))
    reader = VideoReader('rtsp://camera.local/live')
    assert reader.metadata['resolution_changed'] is False
    assert reader.read() is not None and reader.read() is None
    clock.value = 7.
    assert reader.read() is not None
    metadata = reader.metadata
    assert metadata['resolution_changed'] is True
    assert metadata['resolution_change'] == dict(previous=[320, 240], current=[640, 480])
    assert (reader.width, reader.height, reader.display_width, reader.display_height) == (320, 240, 320, 240)
    reader.clear_resolution_change()
    assert reader.metadata['resolution_changed'] is False
    reader.close()


def test_live_processor_does_not_finalize_run_on_missing_frame():
    class Reader:
        live = True
        width = height = 100
        display_width = display_height = 100
        fps = 10
        index = 0
        def read(self): return None
    class Detector:
        device = 'cpu'; detect_ms = 1.
        def detect(self, frame): return []
    config = load_config()
    processor = TrafficProcessor(Reader(), Detector(), config, dict(lanes=[], counting_line=None))
    assert processor.step() is None
    assert processor.exporter.metadata['status'] == 'recording'
    processor.close()


def test_stream_api_validates_url_and_keeps_local_video_working(client, monkeypatch):
    c, s = client
    assert c.post('/api/video/stream', json={'url': 'file:///etc/passwd'}).status_code == 400
    assert c.post('/api/video/stream', json={'url': 'not-a-url'}).status_code == 400

    class StreamReader:
        width = 320; height = 240; fps = 10.; frames = 0; duration = 0.; duration_estimated = True
        display_width = 320; display_height = 240; live = True; index = 0
        def __init__(self, source, max_side=960, **kwargs): self.source = source
        @property
        def metadata(self):
            return dict(width=320, height=240, fps=10., frames=0, duration=0., live=True,
                        stream_state='connected', reconnect_attempt=0, stream_error=None)
        def read(self): return 0, 1., np.zeros((240, 320, 3), np.uint8)
        def seek(self, seconds): raise ValueError('实时流不支持拖动')
        def close(self): pass

    original_reader = service_module.VideoReader
    monkeypatch.setattr(service_module, 'VideoReader', StreamReader)
    response = c.post('/api/video/stream', json={'url': 'rtsp://camera.local/live'})
    assert response.status_code == 200
    body = response.json()
    assert body['video']['live'] is True and body['video_id'].startswith('实时流')
    assert c.post('/api/control', json={'action': 'seek', 'seconds': 1}).status_code == 400
    monkeypatch.setattr(service_module, 'VideoReader', original_reader)
    local = c.post('/api/video/select', json={'video_id': 'demo.mp4'}).json()
    assert local['video']['live'] is False and local['video_id'] == 'demo.mp4'
