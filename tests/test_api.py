import csv
import io
import json
import time
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
import backend.main as main
import backend.service as service_module
import backend.exporter as exporter_module
from backend.service import AnalysisService


@pytest.fixture
def client(tmp_path,monkeypatch):
    data=tmp_path/'data'
    for name in ('videos','calibrations','runs'):(data/name).mkdir(parents=True)
    video=data/'videos'/'demo.mp4'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),10,(200,400))
    for i in range(60):writer.write(np.zeros((400,200,3),np.uint8))
    writer.release()
    class Detector:
        device='cpu';detect_ms=1.;config={}
        def __init__(self):self.index=0;self.axis=1;self.step=2;self.base=np.array([80,30,100,50],float)
        def detect(self,frame):
            i=self.index;self.index+=1
            box=self.base.copy()
            box[[self.axis,self.axis+2]]+=i*self.step
            return [dict(box=box,type='car',confidence=.95)]
    s=AnalysisService();s.detector=Detector()
    s.config['video']['detection_interval']=1
    s.config['speed']['smoothing_frames']=5
    monkeypatch.setattr(main,'DATA',data)
    monkeypatch.setattr(service_module,'DATA',data)
    monkeypatch.setattr(exporter_module,'DATA',data)
    monkeypatch.setattr(main,'service',s)
    class LocalClient(TestClient):
        def post(self, url, **kwargs):
            if url in ('/api/calibration', '/api/settings') and 'json' in kwargs:
                kwargs['json'] = {**kwargs['json'], 'video_token': s.video_token}
            return super().post(url, **kwargs)

        def websocket_connect(self, url, **kwargs):
            import anyio
            kwargs['headers'] = {'origin': 'http://127.0.0.1:8000', **kwargs.get('headers', {})}
            session = super().websocket_connect('ws://127.0.0.1:8000' + url, **kwargs)
            async def bounded_receive():
                with anyio.fail_after(10):
                    return await session._send_rx.receive()
            # Starlette's sync receiver has no public timeout; bound its underlying channel.
            session.receive = lambda: session.portal.call(bounded_receive)
            return session

    with LocalClient(main.app, base_url='http://127.0.0.1:8000') as c:yield c,s


def test_health_and_invalid_inputs(client):
    c,s=client
    assert c.get('/api/health').json()['ok']
    assert c.get('/api/state').json()['video']['frames']==60
    assert c.post('/api/video/select',json={'video_id':'../config.yaml'}).status_code==400
    assert c.post('/api/control',json={'action':'seek','seconds':-1}).status_code==422
    assert c.post('/api/settings',json={'confidence':2}).status_code==422
    assert c.post('/api/calibration',json={'counting_line':[[1,1],[1,1]]}).status_code==422
    assert c.post('/api/calibration',json={'counting_line':[[1,1],[300,300]]}).status_code==400


def test_calibrated_websocket_csv_and_pause_resume(client):
    c,s=client
    geometry=dict(points=[[40,0],[160,0],[160,400],[40,400]],width_m=12,length_m=40,
        counting_line=[[40,65],[160,65]],lanes=[dict(name='Lane 1',points=[[40,0],[160,0],[160,400],[40,400]],direction=[0,1])])
    assert c.post('/api/calibration',json=geometry).status_code==200
    assert c.post('/api/control',json={'action':'play'}).status_code==200
    with c.websocket_connect('/ws') as ws:
        for _ in range(30):
            payload=ws.receive_json()
            if payload.get('frame',0)>=12:break
    assert payload['frame']>=12
    assert payload['image'].startswith('data:image/jpeg;base64,')
    v=payload['vehicles'][0]
    assert v['speed']==pytest.approx(7.2,abs=.5) # 2 px / .1 sec * .1m/px *3.6
    assert v['world'][0]==pytest.approx(5,abs=.2)
    assert payload['metrics']['total_flow']==1
    assert v['lane']=='Lane 1' and len(v['trajectory'])>=10
    paused=c.post('/api/control',json={'action':'pause'}).json()
    index=paused['frame'];run_id=paused['run_id']
    assert c.get('/api/state').json()['frame']==index
    resume=c.post('/api/control',json={'action':'play'}).json()
    assert resume['run_id']==run_id
    c.post('/api/control',json={'action':'pause'})
    for kind in ('vehicles','traffic_statistics','events'):
        r=c.get(f'/api/export/{run_id}/{kind}')
        assert r.status_code==200
        assert csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))).fieldnames
    # A seek starts a new segment, with no stale IDs, events or invented counts.
    seek=c.post('/api/control',json={'action':'seek','seconds':3}).json()
    assert seek['frame']==30 and seek['vehicles']==[] and seek['metrics'] is None
    restart=c.post('/api/control',json={'action':'restart'}).json()
    assert restart['run_id']!=run_id
    c.post('/api/control',json={'action':'pause'})


def test_saved_calibration_reimport_and_settings(client):
    c,s=client
    geometry=dict(points=[[40,0],[160,0],[160,400],[40,400]],width_m=12,length_m=40,lanes=[])
    c.post('/api/calibration',json=geometry)
    selected=c.post('/api/video/select',json={'video_id':'demo.mp4'}).json()
    assert selected['calibration']['width_m']==12
    assert c.post('/api/settings',json={'smoothing_frames':15,'stop_seconds':4}).status_code==200
    assert c.get('/api/state').json()['settings']['smoothing_frames']==15
    assert c.post('/api/calibration',json={'lanes':[]}).status_code==200
    assert c.get('/api/state').json()['calibration'] is None


def test_upload_validation(client):
    c,s=client
    assert c.post('/api/video/upload',files={'file':('test.txt',b'bad','text/plain')}).status_code==400
    assert c.post('/api/video/upload',files={'file':('bad.mp4',b'not a video','video/mp4')}).status_code==400
    path=s.reader.cap.get(cv2.CAP_PROP_FRAME_COUNT)
    assert path==60


def test_valid_upload_and_local_path_import(client):
    c,s=client
    source=main.DATA/'videos/demo.mp4'
    uploaded=c.post('/api/video/upload',files={'file':('uploaded.mp4',source.read_bytes(),'video/mp4')})
    assert uploaded.status_code==200 and uploaded.json()['video']['frames']==60
    assert uploaded.json()['video_id'].endswith('uploaded.mp4')
    imported=c.post('/api/video/import',json={'path':str(source)})
    assert imported.status_code==200 and imported.json()['video']['width']==200


def write_video(path,width,height):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(width,height))
    for _ in range(30):writer.write(np.zeros((height,width,3),np.uint8))
    writer.release()


@pytest.mark.parametrize('width,height,orientation,line',[
    (400,200,'landscape',[[200,0],[200,200]]),
    (200,400,'portrait',[[0,200],[200,200]]),
    (240,240,'square',[[0,120],[240,120]]),
])
@pytest.mark.parametrize('method',['upload','import'])
def test_import_generates_and_persists_counting_line(client,tmp_path,width,height,orientation,line,method):
    c,s=client
    source=tmp_path/f'{orientation}.mp4';write_video(source,width,height)
    if method=='upload':
        response=c.post('/api/video/upload',files={'file':(source.name,source.read_bytes(),'video/mp4')})
    else:
        response=c.post('/api/video/import',json={'path':str(source)})
    assert response.status_code==200
    state=response.json()
    assert state['video']['orientation']==orientation
    assert state['scene']['counting_line']==line
    assert state['scene']['counting_line_mode']=='auto'
    assert state['calibration'] is None
    selected=c.post('/api/video/select',json={'video_id':state['video_id']}).json()
    assert selected['scene']==state['scene']
    saved=json.loads((main.DATA/'calibrations'/f'{s.identity}-scene.json').read_text())
    assert saved['counting_line_mode']=='auto' and saved['counting_line']==line


@pytest.mark.parametrize('width,height,axis,step',[(400,200,0,4),(200,400,1,4)])
def test_automatic_line_produces_uncalibrated_websocket_and_csv_flow(client,width,height,axis,step):
    c,s=client
    source=main.DATA/'videos'/'new.mp4';write_video(source,width,height)
    c.post('/api/video/select',json={'video_id':'new.mp4'})
    s.detector.axis=axis;s.detector.step=step
    s.detector.base=np.array([150,60,190,100] if axis==0 else [60,130,100,170],float)
    assert c.post('/api/control',json={'action':'play'}).status_code==200
    with c.websocket_connect('/ws') as ws:
        for _ in range(30):
            payload=ws.receive_json()
            if payload.get('frame',0)>=10:break
    c.post('/api/control',json={'action':'pause'})
    assert payload['frame']>=10
    assert payload['scene']['counting_line_mode']=='auto'
    assert payload['metrics']['total_flow']==1
    assert payload['metrics']['flow_per_min']>0
    assert payload['metrics']['average_speed'] is None
    assert payload['vehicles'] and all(v['speed'] is None for v in payload['vehicles'])
    response=c.get(f"/api/export/{payload['run_id']}/traffic_statistics")
    rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert any(int(row['flow'])==1 for row in rows)


def test_manual_clear_and_restore_auto_survive_reselect(client):
    c,s=client
    line=[[20,75],[180,75]]
    manual=c.post('/api/calibration',json={'counting_line':line}).json()
    assert manual['scene']['counting_line_mode']=='manual'
    selected=c.post('/api/video/select',json={'video_id':'demo.mp4'}).json()
    assert selected['scene']['counting_line']==line
    # A legacy client clearing the line also persists an explicit opt-out.
    cleared=c.post('/api/calibration',json={'counting_line':None}).json()
    assert cleared['scene']['counting_line_mode']=='disabled'
    selected=c.post('/api/video/select',json={'video_id':'demo.mp4'}).json()
    assert selected['scene']['counting_line'] is None
    restored=c.post('/api/calibration',json={'counting_line_mode':'auto'}).json()
    assert restored['scene']['counting_line']==[[0,200],[200,200]]
    assert restored['scene']['counting_line_mode']=='auto'


def test_legacy_scene_without_line_upgrades_without_losing_lanes(client):
    c,s=client
    lane=dict(name='Lane',points=[[40,0],[160,0],[160,400],[40,400]],direction=[0,1])
    path=main.DATA/'calibrations'/f'{s.identity}-scene.json'
    path.write_text(json.dumps(dict(counting_line=None,lanes=[lane])))
    selected=c.post('/api/video/select',json={'video_id':'demo.mp4'}).json()
    assert selected['scene']['counting_line']==[[40,200],[160,200]]
    assert selected['scene']['lanes']==[lane]
    assert selected['scene']['counting_line_mode']=='auto'
    # Existing manual lines from pre-upgrade scene files remain unchanged.
    path.write_text(json.dumps(dict(counting_line=[[40,75],[160,75]],lanes=[lane])))
    selected=c.post('/api/video/select',json={'video_id':'demo.mp4'}).json()
    assert selected['scene']['counting_line']==[[40,75],[160,75]]
    assert selected['scene']['counting_line_mode']=='manual'


def test_websocket_origin_and_http_host_boundaries(client):
    from starlette.websockets import WebSocketDisconnect
    c, s = client
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect('/ws', headers={'origin': 'https://untrusted.invalid'}) as ws:
            ws.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with TestClient.websocket_connect(c, 'ws://127.0.0.1:8000/ws') as ws:
            ws.receive_json()
    assert c.post('/api/control', json={'action': 'pause'}, headers={'origin': 'https://untrusted.invalid'}).status_code == 403
    assert c.get('/api/health', headers={'host': 'untrusted.invalid'}).status_code == 400
    with c.websocket_connect('/ws', headers={'origin': 'http://127.0.0.1:5173'}) as ws:
        assert ws.receive_json()['session_id'] == s.session_id


def test_stale_video_and_scene_cannot_be_saved(client):
    c, s = client
    old_token = s.video_token
    c.post('/api/video/select', json={'video_id': 'demo.mp4'})
    assert s.video_token != old_token
    before = c.get('/api/state').json()
    response = c.request('POST', '/api/calibration', json={'video_token': old_token, 'lanes': []})
    assert response.status_code == 409
    assert c.request('POST', '/api/settings', json={'video_token': old_token}).status_code == 409
    assert c.request('POST', '/api/calibration', json={'lanes': []}).status_code == 409
    assert c.post('/api/calibration', json={'scene_revision': before['scene_revision'], 'counting_line_mode': 'auto'}).status_code == 200
    assert c.post('/api/calibration', json={'scene_revision': before['scene_revision'], 'lanes': []}).status_code == 409


def test_play_after_ended_restarts_segment(client):
    c, s = client
    c.post('/api/control', json={'action': 'play'})
    old_run = s.processor.exporter.run_id
    s.status = 'ended'
    s.reader.frames = 999
    c.post('/api/control', json={'action': 'play'})
    assert s.status == 'playing'
    assert s.processor is not None
    assert s.processor.exporter.run_id != old_run


def test_frontend_placeholder_when_dist_missing():
    from backend.settings import ROOT
    if (ROOT / 'frontend' / 'dist').exists():
        pytest.skip('frontend/dist 已存在')
    from fastapi.testclient import TestClient
    import backend.main as main
    with TestClient(main.app, base_url='http://127.0.0.1:8000') as c:
        response = c.get('/')
        assert response.status_code == 200
        assert '前端尚未构建' in response.text


def test_failed_new_video_keeps_running_session(client, monkeypatch):
    c, s = client
    c.post('/api/control', json={'action': 'play'})
    token, processor, reader = s.video_token, s.processor, s.reader
    path = main.DATA / 'videos' / 'broken.mp4'
    path.write_bytes(b'invalid-first-frame')
    class BadReader:
        width = 200; height = 400
        def __init__(self, *args): self.closed = False
        def seek(self, seconds): pass
        def read(self): return None
        def close(self): self.closed = True
    monkeypatch.setattr(service_module, 'VideoReader', BadReader)
    assert c.post('/api/video/select', json={'video_id': path.name}).status_code == 400
    assert s.video_token == token and s.reader is reader and s.processor is processor
    assert c.get('/api/health').status_code == 200
    assert c.post('/api/control', json={'action': 'pause'}).status_code == 200


def test_download_while_writing_and_run_history(client):
    c, s = client
    start = c.post('/api/control', json={'action': 'play'}).json()
    run = start['run_id']
    time.sleep(.2)
    response = c.get(f'/api/export/{run}/traffic_statistics')
    assert response.status_code == 200
    assert int(response.headers['content-length']) == len(response.content)
    rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert rows and all(None not in row and all(value is not None for value in row.values()) for row in rows)
    c.post('/api/control', json={'action': 'pause'})
    details = c.get('/api/runs/details').json()
    assert details['items'][0]['run_id'] == run and details['items'][0]['video_id'] == 'demo.mp4'
    c.post('/api/control', json={'action': 'restart'})
    c.post('/api/control', json={'action': 'pause'})
    assert run in [r['run_id'] for r in c.get('/api/runs/details').json()['items']]
    assert c.get('/api/export/../events').status_code != 200
    assert c.get('/api/runs/details?limit=1000').status_code == 400
