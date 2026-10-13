import asyncio
import hashlib
import json
import numpy as np
import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from backend.security import UploadBodyLimit
from backend.service import AnalysisService
from backend.events.rules import EventDetector
from backend.settings import load_config
from backend.traffic.flow_counter import FlowCounter
from backend.vision.video_reader import VideoReader
import backend.vision.video_reader as reader_module
import backend.vision.weights as weights_module


def test_invalid_playing_state_yields_to_event_loop():
    async def check():
        service = AnalysisService()
        service.status = 'playing'
        task = asyncio.create_task(service.run())
        await asyncio.wait_for(asyncio.sleep(.02), .3)
        assert service.status == 'error'
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(check())


@pytest.mark.parametrize('interval', [.1, .5, 1.])
def test_sparse_reverse_observations_still_trigger(interval):
    detector = EventDetector(load_config()['events'])
    path, events = [], []
    for i in range(1, int(6/interval)):
        t = i*interval
        path.append(dict(timestamp=t, point=[0, 100-t*10]))
        events += detector.update(dict(id=1, timestamp=t, speed=36, lane='lane', world_trajectory=path), [0, 1])
    assert any(e['event'] == 'WRONG WAY' for e in events)


def test_flow_window_stays_bounded_and_headway_preserves_all_crossings():
    flow = FlowCounter([[0, 0], [0, 100]])
    for i in range(200):
        flow.update(i, [-5, 50], i-0.1, 'car', 'lane')
        flow.update(i, [5, 50], float(i), 'car', 'lane')
        result = flow.metrics(i)
    assert result['total_flow'] == 200 and result['flow_per_min'] == 60
    assert len(flow.crossings) == 60 and flow.average_headway == pytest.approx(1.)


@pytest.mark.parametrize('chunked', [False, True])
def test_upload_rejected_before_endpoint_runs(chunked):
    app = FastAPI()
    entered = []
    @app.post('/api/video/upload')
    async def upload(file: UploadFile):
        entered.append(True)
        await file.close()
        return {'ok': True}
    app.add_middleware(UploadBodyLimit, max_bytes=256)
    body = b'--test\r\nContent-Disposition: form-data; name="file"; filename="large.mp4"\r\nContent-Type: video/mp4\r\n\r\n' + b'x'*500 + b'\r\n--test--\r\n'
    with TestClient(app) as client:
        data = iter([body[:100], body[100:]]) if chunked else body
        response = client.post('/api/video/upload', content=data, headers={'content-type': 'multipart/form-data; boundary=test'})
    assert response.status_code == 413 and not entered


def test_chunked_limit_closes_files_already_spooled_by_multipart(monkeypatch):
    import starlette.formparsers as parsers
    files, entered, sent = [], [], []
    original = parsers.SpooledTemporaryFile
    def tracked_file(*args, **kwargs):
        file = original(*args, **kwargs)
        files.append(file)
        return file
    monkeypatch.setattr(parsers, 'SpooledTemporaryFile', tracked_file)
    monkeypatch.setattr(parsers.MultiPartParser, 'spool_max_size', 64)
    app = FastAPI()
    @app.post('/api/video/upload')
    async def upload(file: UploadFile):
        entered.append(True)
        return {'ok': True}
    app.add_middleware(UploadBodyLimit, max_bytes=300)
    body = b'--test\r\nContent-Disposition: form-data; name="file"; filename="large.mp4"\r\nContent-Type: video/mp4\r\n\r\n' + b'x'*500 + b'\r\n--test--\r\n'
    chunks = iter([body[:200], body[200:400], body[400:]])
    async def receive():
        chunk = next(chunks, b'')
        return dict(type='http.request', body=chunk, more_body=bool(chunk))
    async def send(message): sent.append(message)
    scope = dict(type='http', method='POST', path='/api/video/upload', raw_path=b'/api/video/upload',
                 query_string=b'', root_path='', scheme='http', http_version='1.1',
                 headers=[(b'content-type', b'multipart/form-data; boundary=test')], server=('127.0.0.1', 8000), client=('127.0.0.1', 1234))
    asyncio.run(app(scope, receive, send))
    assert sent[0]['status'] == 413 and not entered
    assert files and all(file.closed for file in files)


def test_weight_integrity_before_loading(tmp_path, monkeypatch):
    data = tmp_path/'data'; (data/'models').mkdir(parents=True)
    path = data/'models'/'test.pt'; path.write_bytes(b'known-weight')
    (tmp_path/'models.json').write_text(json.dumps([dict(filename='test.pt', sha256=hashlib.sha256(path.read_bytes()).hexdigest())]))
    monkeypatch.setattr(weights_module, 'ROOT', tmp_path)
    monkeypatch.setattr(weights_module, 'DATA', data)
    assert weights_module.verified_weight('test.pt') == path
    path.write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='校验失败'): weights_module.verified_weight('test.pt')
    path.unlink()
    with pytest.raises(ValueError, match='缺失'): weights_module.verified_weight('test.pt')


def test_decoder_timestamps_are_used_instead_of_average_fps(monkeypatch):
    cv2 = reader_module.cv2
    class Capture:
        def __init__(self, *args): self.index = 0
        def isOpened(self): return True
        def set(self, key, value):
            if key == cv2.CAP_PROP_POS_FRAMES:
                self.index = int(value)
                return True
            return False
        def get(self, key):
            return {cv2.CAP_PROP_FRAME_WIDTH: 100, cv2.CAP_PROP_FRAME_HEIGHT: 100,
                    cv2.CAP_PROP_FPS: 10, cv2.CAP_PROP_FRAME_COUNT: 3,
                    cv2.CAP_PROP_POS_MSEC: [0, 0, 200, 500][self.index]}.get(key, 0)
        def read(self):
            self.index += 1
            return True, np.zeros((100, 100, 3), np.uint8)
        def release(self): pass
    monkeypatch.setattr(cv2, 'VideoCapture', Capture)
    reader = VideoReader('synthetic.mp4')
    assert reader.duration == pytest.approx(.6)
    assert not reader.metadata['duration_estimated']
    assert [reader.read()[1] for _ in range(3)] == pytest.approx([0, .2, .5])
