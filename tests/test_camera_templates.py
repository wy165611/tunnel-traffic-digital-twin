import copy
import json
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
import pytest
import backend.main as main
from backend import camera_templates
from backend.service import AnalysisService
from test_api import client, write_video

GEOMETRY=dict(points=[[40,0],[160,0],[160,400],[40,400]],width_m=12,length_m=40,counting_line=[[40,65],[160,65]],lanes=[dict(name='上行',points=[[40,0],[160,0],[160,400],[40,400]],direction=[0,1])])


def target(s):return dict(video_token=s.video_token,scene_revision=s.scene_revision)


def create(c,s,name='固定机位'):
    return c.post('/api/camera-templates',json=dict(**target(s),name=name,note='人工实测保存'))


def preview_payload(s,item,**extra):return dict(**target(s),template_revision=item['revision'],**extra)


def test_named_crud_saved_snapshot_no_live_mutation_and_restart(client):
    c,s=client
    c.post('/api/calibration',json=GEOMETRY)
    s.reset_processor_sync();s.changed()
    before=c.get('/api/state').json();processor=s.processor
    saved=create(c,s).json()
    assert saved['revision']==1 and saved['source']['dimensions']==[200,400]
    assert saved['scene']['lanes'][0]['name']=='上行' and saved['calibration']['width_m']==12
    assert c.get('/api/state').json()==before and s.processor is processor
    s.scene['lanes'][0]['name']='未保存的后端测试草稿'
    assert camera_templates.get_template(main.DATA,saved['id'])['scene']['lanes'][0]['name']=='上行'
    s.scene=copy.deepcopy(before['scene'])
    old_service=main.service;main.service=AnalysisService()
    try:assert c.get('/api/camera-templates').json()['items'][0]['id']==saved['id']
    finally:main.service=old_service
    assert create(c,s).status_code==400
    assert create(c,s,'   ').status_code==400
    renamed=c.post(f"/api/camera-templates/{saved['id']}/rename",json=dict(revision=1,name='重新命名',note='新版')).json()
    assert renamed['revision']==2 and renamed['scene']==saved['scene']
    assert c.post(f"/api/camera-templates/{saved['id']}/rename",json=dict(revision=1,name='陈旧',note='')).status_code==409
    assert c.post('/api/camera-templates/../delete',json=dict(revision=1)).status_code!=200
    assert c.post('/api/camera-templates/invalid/delete',json=dict(revision=1)).status_code==400
    assert c.post(f"/api/camera-templates/{saved['id']}/delete",json=dict(revision=2)).status_code==200
    assert not c.get('/api/camera-templates').json()['items']


def test_scaling_geometry_only_clears_scale_explicit_copy_and_provenance(client):
    c,s=client;c.post('/api/calibration',json=GEOMETRY)
    saved=create(c,s).json()
    path=main.DATA/'videos/smaller.mp4';write_video(path,100,200)
    c.post('/api/video/select',json=dict(video_id=path.name))
    target_geometry=copy.deepcopy(GEOMETRY)
    for name in ('points','counting_line'):target_geometry[name]=[[x/2,y/2] for x,y in target_geometry[name]]
    target_geometry['lanes'][0]['points']=[[x/2,y/2] for x,y in target_geometry['lanes'][0]['points']]
    c.post('/api/calibration',json=target_geometry)
    assert s.calibration is not None
    before=c.get('/api/state').json()
    p=c.post(f"/api/camera-templates/{saved['id']}/preview",json=preview_payload(s,saved)).json()
    assert p['applicable'] and p['scene']['counting_line']==[[20,32.5],[80,32.5]]
    assert p['calibration']['width_m']==12 # resolution never scales physical dimensions
    assert c.get('/api/state').json()==before
    endpoint=f"/api/camera-templates/{saved['id']}/apply"
    assert c.post(endpoint,json=preview_payload(s,saved,geometry_confirmed=False)).status_code==400
    assert c.post(endpoint,json=preview_payload(s,saved,geometry_confirmed=True,copy_scale=True,scale_confirmed=False)).status_code==400
    s.reset_processor_sync();s.changed();old_run=s.processor.exporter.run_id
    applied=c.post(endpoint,json=preview_payload(s,saved,geometry_confirmed=True)).json()
    assert applied['calibration'] is None and s.processor is None
    assert applied['scene']['counting_line']==p['scene']['counting_line']
    assert applied['template_provenance']['template_id']==saved['id'] and not applied['template_provenance']['scale_copied']
    assert json.loads((main.DATA/'runs'/old_run/'run.json').read_text())['status']=='closed'
    c.post('/api/video/select',json=dict(video_id=path.name))
    assert s.calibration is None and s.template_provenance['template_id']==saved['id']
    applied=c.post(endpoint,json=preview_payload(s,saved,geometry_confirmed=True,copy_scale=True,scale_confirmed=True)).json()
    assert applied['calibration']['width_m']==12 and applied['calibration']['points']==target_geometry['points']
    s.reset_processor_sync();s.changed()
    metadata=json.loads((s.processor.exporter.directory/'run.json').read_text())
    assert metadata['video']['width']==100 and metadata['template_provenance']['scale_copied']
    assert c.post(f"/api/camera-templates/{saved['id']}/delete",json=dict(revision=1)).status_code==200
    c.post('/api/video/select',json=dict(video_id=path.name))
    assert s.calibration.payload['width_m']==12 and s.scene['lanes'][0]['name']=='上行'
    # A normal road edit revokes applied-template confirmation/provenance.
    c.post('/api/calibration',json=target_geometry)
    assert s.template_provenance is None and 'template_provenance' not in s.scene
    s.reset_processor_sync();s.changed()
    assert json.loads((s.processor.exporter.directory/'run.json').read_text())['template_provenance'] is None


def test_aspect_token_scene_template_revision_and_invalid_bounds(client):
    c,s=client;c.post('/api/calibration',json=GEOMETRY);saved=create(c,s).json()
    old=preview_payload(s,saved)
    c.post('/api/video/select',json=dict(video_id='demo.mp4'))
    endpoint=f"/api/camera-templates/{saved['id']}/preview"
    assert c.post(endpoint,json=old).status_code==409
    old=preview_payload(s,saved)
    c.post('/api/calibration',json=GEOMETRY)
    assert c.post(endpoint,json=old).status_code==409
    old=preview_payload(s,saved)
    c.post(f"/api/camera-templates/{saved['id']}/rename",json=dict(revision=1,name='新名',note=''))
    assert c.post(endpoint,json=old).status_code==409
    saved['revision']=2
    path=main.DATA/'videos/wide.mp4';write_video(path,400,200)
    c.post('/api/video/select',json=dict(video_id=path.name))
    p=c.post(endpoint,json=preview_payload(s,saved)).json()
    assert not p['applicable'] and p['reasons']
    before=c.get('/api/state').json()
    assert c.post(endpoint.replace('/preview','/apply'),json=preview_payload(s,saved,geometry_confirmed=True,copy_scale=True,scale_confirmed=True)).status_code==400
    assert c.get('/api/state').json()==before
    damaged=camera_templates.get_template(main.DATA,saved['id'])
    damaged['scene']['counting_line']=[[0,0],[10000,10000]]
    (main.DATA/'camera_templates'/f"{saved['id']}.json").write_text(json.dumps(damaged))
    assert c.post(endpoint,json=preview_payload(s,saved)).status_code==400


def test_concurrent_renames_and_applies_have_one_winner_without_deadlock(client):
    c,s=client;c.post('/api/calibration',json=GEOMETRY);saved=create(c,s).json()
    endpoint=f"/api/camera-templates/{saved['id']}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(c.post,endpoint+'/rename',json=dict(revision=1,name=f'并发{i}',note='')) for i in range(2)]
        assert sorted(f.result(timeout=3).status_code for f in futures)==[200,409]
    saved['revision']=2
    payload=preview_payload(s,saved,geometry_confirmed=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(c.post,endpoint+'/apply',json=payload) for _ in range(2)]
        assert sorted(f.result(timeout=3).status_code for f in futures)==[200,409]
    assert s.calibration is None


def test_tolerance_boundary_and_corrupt_saved_template_do_not_crash(client):
    c,s=client;saved=create(c,s).json()
    original_width,original_height=s.reader.width,s.reader.height
    try:
        # Equivalent to target ratio exactly +1%, allowing floating arithmetic tolerance.
        s.reader.width=202;s.reader.height=400
        assert camera_templates.preview_template(main.DATA,s,saved['id'],1)['applicable']
        s.reader.width=203
        assert not camera_templates.preview_template(main.DATA,s,saved['id'],1)['applicable']
    finally:s.reader.width,s.reader.height=original_width,original_height
    path=main.DATA/'camera_templates'/f"{saved['id']}.json"
    path.write_text(json.dumps(dict(schema_version=1,id=saved['id'])))
    assert not c.get('/api/camera-templates').json()['items']
    assert c.post(f"/api/camera-templates/{saved['id']}/preview",json=preview_payload(s,saved)).status_code==404


def test_template_with_missing_scene_keys_is_treated_as_corrupt(client):
    c, s = client
    saved = create(c, s).json()
    path = main.DATA / 'camera_templates' / f"{saved['id']}.json"
    value = json.loads(path.read_text(encoding='utf-8'))
    value['scene'] = {}
    path.write_text(json.dumps(value), encoding='utf-8')
    assert not c.get('/api/camera-templates').json()['items']
    assert c.post(f"/api/camera-templates/{saved['id']}/preview", json=preview_payload(s, saved)).status_code == 404


def test_storage_revision_is_locked_through_actual_road_commit(client, monkeypatch):
    import threading
    c,s=client;saved=create(c,s).json();entered=threading.Event();release=threading.Event()
    original=s.read_preview
    def blocked_preview(reader, seconds):
        entered.set();assert release.wait(3)
        return original(reader,seconds)
    monkeypatch.setattr(s,'read_preview',blocked_preview)
    payload=preview_payload(s,saved,geometry_confirmed=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        apply=pool.submit(c.post,f"/api/camera-templates/{saved['id']}/apply",json=payload)
        assert entered.wait(2)
        rename=pool.submit(camera_templates.rename_template,main.DATA,saved['id'],1,'提交后的新名','')
        try:
            assert not rename.done()
        finally:release.set()
        assert apply.result(timeout=3).status_code==200
        assert rename.result(timeout=3)['revision']==2
    assert s.template_provenance['template_revision']==1
    assert c.post(f"/api/camera-templates/{saved['id']}/preview",json=preview_payload(s,saved)).status_code==409
