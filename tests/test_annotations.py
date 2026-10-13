import copy
import csv
import json
from pathlib import Path
import pytest
import backend.main as main
from backend.annotations import AnnotationDocument, fingerprint
from backend.evaluation import evaluate_run
from backend.service import AnalysisService
from test_api import client

GEOMETRY=dict(counting_line=[[40,65],[160,65]],lanes=[dict(name='车道',points=[[40,0],[160,0],[160,400],[40,400]],direction=[0,1])])


def run_segment(c,s,close=True):
    c.post('/api/calibration',json=GEOMETRY)
    s.reset_processor_sync()
    last=None
    for _ in range(50):last=s.processor.step()
    s.snapshot=last;s.status='paused'
    if close:s.processor.close()
    s.changed()
    return last['run_id']


def load(c,run):return c.get(f'/api/runs/{run}/annotations').json()


def post(c,run,doc,revision=None):return c.post(f'/api/runs/{run}/annotations',json=dict(expected_revision=doc['revision'] if revision is None else revision,document=doc))


def complete(doc,sections=('crossings',)):
    return dict(copy.deepcopy(doc),annotator='人工测试核验者',reviewed_sections=list(sections),verified=True,completeness_confirmed=True)


def test_independent_no_event_source_range_observed_ids_and_no_live_mutation(client):
    c,s=client;run=run_segment(c,s)
    before=c.get('/api/state').json()
    files={p.name:p.read_bytes() for p in s.processor.exporter.directory.glob('*.csv')}
    metadata=(s.processor.exporter.directory/'run.json').read_bytes()
    context=c.get(f'/api/runs/{run}/annotation-context').json()
    assert context['available'] and context['closed'] and context['dimensions']==[200,400]
    assert context['source_available'] and context['source_url']==f'/api/runs/{run}/source'
    r=c.get(context['source_url'],headers={'Range':'bytes=0-15'})
    assert r.status_code==206 and len(r.content)==16
    observations=c.get(f'/api/runs/{run}/observations?seconds=1.03').json()
    assert observations['sample_timestamp']==pytest.approx(1.0) and observations['items'][0]['vehicle_id']==1
    assert observations['items'][0]['pixel'][0]==pytest.approx(90,abs=.5)
    assert c.get(f'/api/runs/{run}/observations?seconds=nan').status_code==400
    assert c.get(f'/api/runs/{run}/observations?seconds=100').status_code==400
    doc=load(c,run)['document'];doc['annotator']='草稿作者';doc['crossings']=[dict(timestamp=.8,physical_vehicle_note='人工白车')]
    saved=post(c,run,doc)
    assert saved.status_code==200 and saved.json()['revision']==1 and not saved.json()['verified']
    assert c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=1)).status_code==400
    assert c.get('/api/state').json()==before
    assert files=={p.name:p.read_bytes() for p in s.processor.exporter.directory.glob('*.csv')}
    assert metadata==(s.processor.exporter.directory/'run.json').read_bytes()
    assert c.get(f'/api/runs/{run}/annotations/download?revision=1').json()['speed_state']=='unreviewed'
    assert post(c,run,doc,0).status_code==409
    original=main.service;main.service=AnalysisService()
    try:assert load(c,run)['document']['crossings'][0]['physical_vehicle_note']=='人工白车'
    finally:main.service=original


def test_partial_categories_count_events_unmapped_matching_and_stale_result(client):
    c,s=client;run=run_segment(c,s)
    exporter=s.processor.exporter
    # Representative saved event rows, independent manual items are deliberately distinct.
    with (exporter.directory/'events.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['timestamp','vehicle_id','event']);writer.writeheader()
        writer.writerows([dict(timestamp=1,vehicle_id=1,event='WRONG WAY'),dict(timestamp=1.05,vehicle_id=1,event='WRONG WAY'),dict(timestamp=3,vehicle_id=2,event='HARD BRAKING')])
    doc=complete(load(c,run)['document'],('crossings','events'))
    doc['crossings']=[dict(timestamp=.8,physical_vehicle_note='人工计数')]
    doc['events']=[dict(timestamp=1,event='WRONG WAY',vehicle_id=1,physical_vehicle_note='映射车'),dict(timestamp=1.08,event='WRONG WAY',vehicle_id=1,physical_vehicle_note='另一重复事件'),dict(timestamp=3,event='HARD BRAKING',vehicle_id=None,physical_vehicle_note='没有轨迹的物理目标')]
    saved=post(c,run,doc).json()
    evaluated=c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=1,tolerance_seconds=.15))
    assert evaluated.status_code==200
    result=evaluated.json()
    assert result['flow']['absolute_error']==0
    assert (result['events']['true_positive'],result['events']['false_positive'],result['events']['false_negative'])==(2,1,1)
    assert result['events']['unmapped_truth']==1 and not result['speed']['available'] and result['speed']['mae_kmh'] is None
    assert c.get(f'/api/runs/{run}/evaluation/download?revision=1').status_code==200
    saved['note']='修改';saved['verified']=False;saved['completeness_confirmed']=False
    assert post(c,run,saved).json()['revision']==2
    assert load(c,run)['result_stale']
    assert c.get(f'/api/runs/{run}/evaluation/download?revision=1').status_code==409
    assert c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=1)).status_code==409
    assert c.get(f'/api/runs/{run}/annotations/download?revision=1').status_code==409
    # Count-only review never requires files from the unreviewed categories.
    (exporter.directory/'events.csv').unlink();(exporter.directory/'vehicles.csv').unlink()
    saved=complete(load(c,run)['document']);saved['crossings']=[]
    saved=post(c,run,saved).json()
    result=c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=saved['revision'])).json()
    assert result['flow']['available'] and result['flow']['truth']==0
    assert not result['events']['available'] and result['events']['true_positive'] is None


def test_event_only_verified_empty_null_precision_recall_and_corrupt_required_headers(client):
    c,s=client;run=run_segment(c,s);directory=s.processor.exporter.directory
    doc=complete(load(c,run)['document'],('events',))
    saved=post(c,run,doc).json()
    result=c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=1)).json()
    assert not result['flow']['available'] and result['events']['available']
    assert result['events']['truth']==0 and result['events']['predicted']==0
    assert result['events']['precision'] is None and result['events']['recall'] is None
    for contents in ('','unrelated_column\n','timestamp,vehicle_id,event\n1,0,WRONG WAY\n','timestamp,vehicle_id,event\nnan,1,WRONG WAY\n'):
        (directory/'events.csv').write_text(contents)
        assert c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=1)).status_code==400
    (directory/'events.csv').write_text('timestamp,vehicle_id,event\n')
    assert c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=1)).status_code==200
    for contents in ('','wrong\n','timestamp,flow\n0,-1\n4.9,1\n','timestamp,flow\n0,1\n4.9,0\n','timestamp,flow\n0,0.5\n4.9,1\n'):
        (directory/'traffic_statistics.csv').write_text(contents)
        assert c.post(f'/api/runs/{run}/evaluate',json=dict(expected_revision=1)).status_code==400


def test_strict_bindings_bounds_payload_types_active_and_missing_source(client):
    c,s=client;run=run_segment(c,s,False)
    value=load(c,run);doc=value['document'];assert not value['context']['closed']
    assert post(c,run,complete(doc)).status_code==400
    saved=post(c,run,doc).json();assert saved['revision']==1
    s.processor.close()
    source=main.DATA/'videos/demo.mp4';source.write_bytes(source.read_bytes()+b'changed')
    assert not load(c,run)['context']['source_available']
    draft=load(c,run)['document'];draft['note']='仍可编辑';assert post(c,run,draft).status_code==200
    assert post(c,run,complete(load(c,run)['document'])).status_code==400
    assert c.get(f'/api/runs/{run}/source').status_code==404
    source.unlink()
    doc=load(c,run)['document']
    for key,new in [('run_id','20260101-000000-abcdef'),('video_identity','a'*24),('run_fingerprint','f'*64),('dimensions',[1,1]),('interval',[-1,5]),('interval',[0,100]),('verified','true'),('revision',True)]:
        invalid=copy.deepcopy(doc);invalid[key]=new
        assert post(c,run,invalid).status_code in (400,422)
    for row in [dict(timestamp=1,event='UNKNOWN',vehicle_id=1,physical_vehicle_note=''),dict(timestamp=1,event='WRONG WAY',vehicle_id=0,physical_vehicle_note=''),dict(timestamp=1,event='WRONG WAY',vehicle_id=None,physical_vehicle_note=''),dict(timestamp=True,event='WRONG WAY',vehicle_id=1,physical_vehicle_note=''),dict(timestamp=1,event='WRONG WAY',vehicle_id=True,physical_vehicle_note='')]:
        invalid=copy.deepcopy(doc);invalid['events']=[row];assert post(c,run,invalid).status_code==422
    invalid=copy.deepcopy(doc);invalid['unknown']='rejected';assert post(c,run,invalid).status_code==422
    assert c.get('/api/runs/invalid/annotations').status_code==400


def test_legacy_source_facts_persist_when_original_missing_and_corrupt_metadata(client):
    c,s=client;run=run_segment(c,s);directory=s.processor.exporter.directory
    metadata=json.loads((directory/'run.json').read_text());metadata.pop('video')
    (directory/'run.json').write_text(json.dumps(metadata))
    s.processor=None # legacy closed segment, no active exporter overwrites its metadata snapshot
    doc=load(c,run)['document'];assert doc['dimensions']==[200,400]
    saved=post(c,run,doc).json();assert saved['source_video']['width']==200
    before=(directory/'run.json').read_bytes()
    (main.DATA/'videos/demo.mp4').unlink()
    value=load(c,run);assert value['context']['available'] and not value['context']['source_available']
    draft=value['document'];draft['note']='无原视频时仍能保留草稿'
    assert post(c,run,draft).status_code==200
    assert post(c,run,complete(load(c,run)['document'])).status_code==400
    assert (directory/'run.json').read_bytes()==before
    (directory/'run.json').write_text('{broken')
    assert not c.get(f'/api/runs/{run}/annotation-context').json()['available']
    assert load(c,run)['document']['note']=='无原视频时仍能保留草稿'
    assert c.get(f'/api/runs/{run}/annotations/download').status_code==200


def test_public_schema2_evaluator_dimensions_facts_and_cli_contract(client):
    c,s=client;run=run_segment(c,s);directory=s.processor.exporter.directory
    doc=complete(load(c,run)['document']);doc=post(c,run,doc).json()
    result=evaluate_run(directory,doc)
    assert result['schema_version']==2
    bad=copy.deepcopy(doc);bad['dimensions']=[1,1]
    with pytest.raises(ValueError):evaluate_run(directory,bad)
    metadata=json.loads((directory/'run.json').read_text());metadata.pop('video');(directory/'run.json').write_text(json.dumps(metadata))
    assert evaluate_run(directory,doc)['flow']['available']
    bad=copy.deepcopy(doc);bad['source_video']['width']=1
    with pytest.raises(ValueError):evaluate_run(directory,bad)
    (directory/'annotations.json').unlink()
    with pytest.raises(ValueError):evaluate_run(directory,doc)


def test_observation_helper_excludes_predictions_and_unknown_legacy_unavailable(client):
    c,s=client;run=run_segment(c,s);directory=s.processor.exporter.directory
    with (directory/'vehicles.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['timestamp','vehicle_id','x_pixel','y_pixel','observed']);writer.writeheader()
        writer.writerows([dict(timestamp=1,vehicle_id=1,x_pixel=10,y_pixel=20,observed=True),dict(timestamp=1.04,vehicle_id=2,x_pixel=30,y_pixel=40,observed=False)])
    value=c.get(f'/api/runs/{run}/observations?seconds=1.04').json()
    assert value['sample_timestamp']==1 and [r['vehicle_id'] for r in value['items']]==[1]
    assert not c.get(f'/api/runs/{run}/observations?seconds=3').json()['items']
    directory=main.DATA/'runs/20260101-000000-abcdef';directory.mkdir()
    context=c.get('/api/runs/20260101-000000-abcdef/annotation-context').json()
    assert not context['available'] and not context['source_available']
    assert load(c,directory.name)['document'] is None
