import csv
import copy
import json
import threading
import time
from pathlib import Path
import cv2
import numpy as np
import pytest
import backend.main as main
from backend.exporter import CSVExporter, FIELDS
from backend.reports import build_report, compare_reports, report_html, BoundedTrend
from backend.traffic.flow_counter import FlowCounter
from backend.service import AnalysisService
from test_api import client


def write_csv(directory, name, columns, values):
    with (directory / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(values)


def test_report_totals_observed_coverage_empty_and_legacy(tmp_path):
    write_csv(tmp_path, 'traffic_statistics', ['timestamp','flow','vehicle_count','average_speed'], [dict(timestamp=t,flow=f,vehicle_count=1,average_speed=10) for t,f in [(5,1),(6,2),(7,2)]])
    write_csv(tmp_path, 'vehicles', ['observed','speed'], [dict(observed=True,speed=10),dict(observed=False,speed=1000),dict(observed=True,speed=''),dict(observed=True,speed=20)])
    write_csv(tmp_path, 'events', ['timestamp','event','vehicle_id','event_id','run_id','speed'], [dict(timestamp=6,event='WRONG WAY',vehicle_id=1,event_id='a'*32,run_id='x',speed=10)])
    (tmp_path/'run.json').write_text(json.dumps(dict(segment_start=5,video_id='<script>alert(1)</script>')))
    report=build_report(tmp_path,'run')
    assert report['summary']['cumulative_crossings']==2 # not 1+2+2
    assert report['summary']['machine_event_count']==1
    assert report['range']['duration']==2
    assert report['speed']['mean']==15 and report['speed']['coverage']==pytest.approx(2/3)
    assert report['events'][0]['event_id']=='a'*32
    html=report_html(report)
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html and '<svg' in html
    write_csv(tmp_path,'vehicles',['speed'],[dict(speed=50)])
    report=build_report(tmp_path,'run')
    assert report['speed']['mean'] is None and report['speed']['observed_samples'] is None
    (tmp_path/'vehicles.csv').unlink()
    (tmp_path/'traffic_statistics.csv').unlink()
    assert build_report(tmp_path,'run')['summary']['cumulative_crossings'] is None
    write_csv(tmp_path,'vehicles',['observed','speed'],[])
    assert build_report(tmp_path,'run')['speed']['observed_samples']==0


def test_comparison_requires_metadata_and_geometry_and_labels_traffic():
    report=dict(run_id='a',metadata=dict(video_identity='same',scene=dict(counting_line=None,lanes=[]),calibration=None,config={'traffic':{'legal_direction':[0,1]}}),range=dict(start=1,end=3))
    other=copy.deepcopy(report);other['run_id']='b'
    other['metadata']['config']['traffic']['legal_direction']=[1,0]
    assert compare_reports(report,other)['comparable']
    assert compare_reports(report,other)['settings_differences']==['traffic']
    for change in ('identity','geometry','calibration','interval'):
        modified=copy.deepcopy(other)
        if change=='identity':modified['metadata']['video_identity']='changed'
        elif change=='geometry':modified['metadata']['scene']={}
        elif change=='calibration':modified['metadata'].pop('calibration')
        else:modified['range']['end']=3.2
        assert not compare_reports(report,modified)['comparable']


def cross(counter,vid,t,lane='A'):
    counter.update(vid,[0,-1],t-.1,'car',lane)
    assert counter.update(vid,[0,1],t,'car',lane)


def test_lane_window_edges_segment_offset_irregular_time_and_reset():
    flow=FlowCounter([[-1,0],[1,0]])
    cross(flow,1,100);cross(flow,2,100.01);cross(flow,3,105,'B');cross(flow,4,110)
    result=flow.lane_window(110,'A',10,100)
    assert result==dict(window_seconds=10,window_flow=2,covered_seconds=10,complete=True)
    assert flow.lane_window(110,'A',30,100)['covered_seconds']==10
    assert not flow.lane_window(110,'A',30,100)['complete']
    assert flow.lane_window(113.72,'B',10,100)['window_flow']==1
    assert flow.lane_window(170,'A',60,100)['window_flow']==0
    assert FlowCounter().lane_window(110,'A',10,110)['window_flow']==0
    with pytest.raises(ValueError):flow.lane_window(10,'A',20)


def test_each_lane_window_downsampling_preserves_first_last(tmp_path):
    values=[dict(timestamp=t,lane='A',observed_count=1,predicted_count=0,average_speed='',cumulative_flow=t,window_seconds=w,window_flow=1,covered_seconds=min(t,w),complete=t>=w,lane_json='"A"') for t in range(1500) for w in (10,30,60)]
    write_csv(tmp_path,'lane_statistics',FIELDS['lane_statistics'],values)
    report=build_report(tmp_path,'a')
    for window in (10,30,60):
        points=[row for row in report['lanes']['A'] if row['window_seconds']==window]
        assert points[0]['timestamp']==0 and points[-1]['timestamp']==1499
        assert len(points)<=300
    assert '30 秒窗口过线' in report_html(report)


def test_formula_safe_lane_roundtrip(client):
    c,s=client
    s.reset_processor_sync()
    exp=s.processor.exporter
    for name in ('@北侧车道',"'@北侧车道"):
        exp.write('lane_statistics',dict(timestamp=1,lane=name,observed_count=0,predicted_count=0,average_speed=None,cumulative_flow=0,window_seconds=10,window_flow=0,covered_seconds=1,complete=False))
        exp.write('events',dict(timestamp=1,lane=name,event='WRONG WAY',vehicle_id=1,event_id='',run_id=exp.run_id))
    exp.flush()
    report=c.get(f'/api/runs/{exp.run_id}/report').json()
    assert set(report['lanes'])=={'@北侧车道',"'@北侧车道"}
    assert {e['lane'] for e in c.get(f'/api/runs/{exp.run_id}/events').json()['items']}==set(report['lanes'])
    exported=c.get(f'/api/export/{exp.run_id}/lane_statistics').content.decode('utf-8-sig')
    assert 'lane_json' in exported and "'@北侧车道" in exported


def run_steps(s,count):
    for _ in range(count):
        frame=s.processor.step()
        if frame is None:break
        s.snapshot=frame
    s.status='paused';s.changed()
    return s.state()


def test_actual_rule_capture_review_persistence_source_and_no_live_mutation(client):
    c,s=client
    geometry=dict(points=[[40,0],[160,0],[160,400],[40,400]],width_m=12,length_m=40,counting_line=[[40,65],[160,65]],lanes=[dict(name='Lane 1',points=[[40,0],[160,0],[160,400],[40,400]],direction=[0,1])])
    assert c.post('/api/calibration',json=geometry).status_code==200
    s.config['events']['stop_seconds']=.5
    s.config['events']['stop_speed']=10 # actual calibrated 7.2 km/h triggers stop threshold
    s.config['video']['display_max_side']=100
    # Re-select makes a resized frame; deterministic detector emits display coordinates.
    c.post('/api/video/select',json={'video_id':'demo.mp4'})
    s.detector.base=np.array([20,7.5,25,12.5]);s.detector.step=.5
    s.reset_processor_sync()
    state=run_steps(s,20);run=state['run_id']
    assert state['events'] and state['events'][0]['event']=='ABNORMAL STOP'
    event=state['events'][0];eid=event['event_id']
    before=c.get('/api/state').json()
    report=c.get(f'/api/runs/{run}/report')
    assert report.status_code==200 and report.json()['summary']['machine_event_count']>=1
    listed=c.get(f'/api/runs/{run}/events').json()
    assert listed['items'][0]['event_id'] and listed['items'][0]['evidence_available']
    detail=c.get(f'/api/runs/{run}/events/{eid}').json()
    assert detail['source_available'] and detail['review']['status']=='pending'
    assert detail['original_dimensions']==[200,400] and detail['display_dimensions']==[50,100]
    assert detail['display_box'][0]==round(detail['vehicle']['box'][0]/4)
    screenshot=c.get(detail['screenshot_url'])
    image=cv2.imdecode(np.frombuffer(screenshot.content,np.uint8),cv2.IMREAD_COLOR)
    assert image.shape[:2]==(100,50)
    x,y=detail['display_box'][:2]
    assert image[y,x,2]>image[y,x,0] # actual red annotated edge
    source=c.get(detail['source_url'],headers={'Range':'bytes=0-31'})
    assert source.status_code==206 and len(source.content)==32
    raw=(main.DATA/'runs'/run/'events.csv').read_bytes()
    reviewed=c.post(f'/api/runs/{run}/events/{eid}/review',json=dict(status='false_positive',note='人工核对记录'))
    assert reviewed.status_code==200
    assert c.get('/api/state').json()==before
    assert (main.DATA/'runs'/run/'events.csv').read_bytes()==raw
    original_service=main.service
    main.service=AnalysisService()
    try:
        assert c.get(f'/api/runs/{run}/events/{eid}').json()['review']['note']=='人工核对记录'
    finally:main.service=original_service
    source_path=main.DATA/'videos/demo.mp4'
    original=source_path.read_bytes();source_path.write_bytes(original+b'changed')
    assert not c.get(f'/api/runs/{run}/events/{eid}').json()['source_available']
    assert c.get(f'/api/runs/{run}/events/{eid}/source').status_code==404
    source_path.unlink()
    assert c.get(f'/api/runs/{run}/events/{eid}/screenshot').status_code==200
    assert c.get('/api/state').json()==before
    assert c.post(f'/api/runs/{run}/events/{eid}/review',json=dict(status='bad',note='')).status_code==422
    assert c.post(f'/api/runs/{run}/events/{eid}/review',json=dict(status='pending',note='x'*1001)).status_code==422
    assert c.get(f'/api/runs/{run}/events/invalid').status_code==400
    assert c.get('/api/runs/invalid/report').status_code==400
    assert c.get(f'/api/runs/{run}/report.html').status_code==200


def test_uncalibrated_no_events_predicted_excluded_no_lanes_and_active_report(client):
    c,s=client
    s.reset_processor_sync()
    run_steps(s,6)
    # Omit one observed sample: tracker predicts position and retained speed is never a lane sample.
    s.detector.detect=lambda frame:[]
    s.processor.last_history_time=-1
    state=run_steps(s,1)
    row=state['lane_history'][-1]['lanes'][0]
    assert row['lane']=='未划分' and row['average_speed'] is None
    assert row['observed_count']==0 and row['predicted_count']==1
    report=c.get(f"/api/runs/{state['run_id']}/report").json()
    assert report['speed']['mean'] is None and report['speed']['coverage']==0
    assert report['summary']['machine_event_count']==0
    assert not state['events']
    # Pause a real step after its vehicle row; a report must wait for statistics and lane rows.
    exp=s.processor.exporter
    complete=threading.Event();vehicle_written=threading.Event();release=threading.Event()
    original_write=exp.write
    def intercepted_write(kind,row):
        original_write(kind,row)
        if kind=='vehicles':
            vehicle_written.set()
            assert release.wait(2)
    exp.write=intercepted_write
    step_thread=threading.Thread(target=s.processor.step)
    step_thread.start();assert vehicle_written.wait(2)
    results=[]
    def read():
        results.append(c.get(f'/api/runs/{exp.run_id}/report').json());complete.set()
    worker=threading.Thread(target=read);worker.start()
    try:
        assert not complete.wait(.05)
    finally:
        release.set()
    step_thread.join(2);worker.join(2);assert complete.is_set()
    assert results[0]['range']['end']==pytest.approx(.7)


def test_legacy_and_missing_report_endpoints(client):
    c,s=client
    directory=main.DATA/'runs/20260101-000000-abcdef';directory.mkdir()
    write_csv(directory,'events',['timestamp','vehicle_id','event','lane','speed'],[dict(timestamp=1,vehicle_id=1,event='WRONG WAY',lane='',speed='')])
    report=c.get('/api/runs/20260101-000000-abcdef/report').json()
    assert report['range']['start'] is None and report['summary']['cumulative_crossings'] is None
    details=c.get('/api/runs/details').json()['items']
    assert not next(r for r in details if r['run_id']==directory.name)['available']['lane_statistics']
    assert report['speed']['coverage'] is None and report['events'][0]['event_id'] is None
    assert not c.get('/api/runs/20260101-000000-abcdef/events').json()['items'][0]['evidence_available']
    assert c.get('/api/runs/20260101-000000-abcdee/report').status_code==404
    assert c.get('/api/runs/20260101-000000-abcdef/events?limit=1000').status_code==400
    (directory/'events.csv').unlink()
    missing=c.get('/api/runs/20260101-000000-abcdef/events').json()
    assert missing['total'] is None and not missing['available']


def test_safe_ids_and_unknown_or_escaped_source_paths(tmp_path):
    from backend.reports import run_directory
    from backend.evidence import evidence_directory, source_path
    (tmp_path/'runs').mkdir();(tmp_path/'videos').mkdir()
    run='20260101-000000-abcdef'
    folder=tmp_path/'runs'/run;folder.mkdir()
    for value in ('../videos','../../outside','20260101-000000-abcdef/../videos'):
        with pytest.raises(ValueError):run_directory(tmp_path,value)
    with pytest.raises(ValueError):evidence_directory(tmp_path,run,'../capture.json')
    assert source_path(tmp_path,dict(video_id='demo.mp4',video_identity=None))[0] is None
    outside=tmp_path/'outside.mp4';outside.write_bytes(b'video')
    (tmp_path/'videos/demo.mp4').symlink_to(outside)
    assert source_path(tmp_path,dict(video_id='demo.mp4',video_identity='known'))[0] is None
    assert source_path(tmp_path,dict(video_id='../outside.mp4',video_identity='known'))[0] is None
    (folder/'evidence').symlink_to(tmp_path/'videos')
    (tmp_path/'videos'/('a'*32)).mkdir()
    with pytest.raises(FileNotFoundError):evidence_directory(tmp_path,run,'a'*32)
