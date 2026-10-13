import copy
import csv
import numpy as np
import pytest
from backend.calibration.homography import RoadCalibration
from backend.traffic.speed_estimator import SpeedEstimator
from backend.traffic.flow_counter import FlowCounter
from backend.traffic.lane_detector import LaneDetector
from backend.vision.tracker import SortTracker
from backend.events.rules import EventDetector
from backend.settings import load_config
from backend.api.schemas import SceneInput, RuntimeSettings


def cal():
    return RoadCalibration(dict(points=[[100,100],[300,100],[300,600],[100,600]],width_m=10,length_m=50))


def test_homography_corners_and_midpoint():
    c=cal()
    assert c.map([100,100]) == pytest.approx([0,0])
    assert c.map([300,600]) == pytest.approx([10,50])
    assert c.map([200,350]) == pytest.approx([5,25])
    assert c.contains([200,350]) and not c.contains([0,0])


@pytest.mark.parametrize('points', [[[0,0],[100,100],[100,0],[0,100]],[[0,0],[1,1],[2,2],[3,3]],[[0,0],[100,0],[10,10],[0,100]]])
def test_invalid_calibration_rejected(points):
    with pytest.raises(ValueError):
        RoadCalibration(dict(points=points,width_m=10,length_m=50))


def test_calibration_save_reload(tmp_path):
    c=cal();p=tmp_path/'calibration.json';c.save(p)
    assert RoadCalibration.load(p).map([200,350]) == pytest.approx([5,25])


def test_constant_speed_and_acceleration_units():
    e=SpeedEstimator(10,5)
    assert e.update(0,[0,0]) == (None,None)
    for i in range(1,30):speed,acc=e.update(i/10,[0,i])
    assert speed == pytest.approx(36,abs=.01)
    assert acc == pytest.approx(0,abs=.01)


def test_stationary_jitter_is_smoothed():
    e=SpeedEstimator(15,5)
    values=[]
    for i in range(100):
        speed,_=e.update(i/30,[0,.01*(-1)**i])
        if speed is not None:values.append(speed)
    assert max(values) < .5


def test_flow_once_for_both_directions_and_finite_segment():
    f=FlowCounter([[0,10],[20,10]])
    assert not f.update(1,[5,5],0,'car','Lane 1')
    assert f.update(1,[5,15],1,'car','Lane 1')
    assert not f.update(1,[5,5],2,'car','Lane 1')
    assert not f.update(2,[30,5],0,'truck','Lane 2')
    assert not f.update(2,[30,15],1,'truck','Lane 2')
    f.update(3,[15,15],0,'bus','Lane 2')
    assert f.update(3,[15,5],2,'bus','Lane 2')
    assert len(f.counted)==2 and f.by_type['car']==1 and f.by_type['bus']==1


def test_flow_endpoint_then_crossing():
    f=FlowCounter([[0,10],[20,10]])
    f.update(1,[5,5],0,'car',None)
    assert f.update(1,[5,10],1,'car',None)
    assert not f.update(1,[5,15],2,'car',None)


def test_short_video_rates_marked_estimates():
    f=FlowCounter([[0,10],[20,10]])
    m=f.metrics(8)
    assert m['flow_estimated'] and m['flow_per_hour'] is None
    assert not f.metrics(60)['flow_estimated']


def det(x,kind='car'):
    return dict(box=np.array([x,0,x+30,60.]),type=kind,confidence=.9)


def test_sort_stable_ids_after_detection_gap():
    t=SortTracker(dict(max_age=10,min_hits=2,iou_threshold=.2))
    assert t.update([det(0)])==[]
    first=t.update([det(2)])[0].id
    for x in range(4,20,2):
        t.update(None)
        assert t.update([det(x)])[0].id==first
    for _ in range(11):t.update([])
    assert t.tracks==[]


def test_sort_separate_vehicles_and_reentry():
    t=SortTracker(dict(max_age=2,min_hits=1,iou_threshold=.2))
    tracks=t.update([det(0),det(100)])
    ids=[v.id for v in tracks]
    assert len(set(ids))==2
    assert [v.id for v in t.update([det(2),det(102)])]==ids
    for _ in range(3):t.update([])
    assert t.update([det(0)])[0].id not in ids


def vehicle(t,speed=0,path=None):
    return dict(id=1,timestamp=t,speed=speed,lane='Lane 1',world_trajectory=path or [])


def test_abnormal_stop_duration_and_cooldown():
    e=EventDetector(load_config()['events'])
    assert e.update(vehicle(0),[0,1])==[]
    assert e.update(vehicle(2.9),[0,1])==[]
    assert e.update(vehicle(3.1),[0,1])[0]['event']=='ABNORMAL STOP'
    assert e.update(vehicle(4),[0,1])==[]


def test_no_uncalibrated_events():
    e=EventDetector(load_config()['events'])
    for i in range(10):assert e.update(vehicle(i,None),[0,1])==[]


def test_hard_braking_after_half_second():
    e=EventDetector(load_config()['events'])
    e.update(vehicle(0,72),[0,1])
    assert not e.update(vehicle(.1,60),[0,1])
    assert any(x['event']=='HARD BRAKING' for x in e.update(vehicle(.6,36),[0,1]))


def test_wrong_way_and_lane_specific_direction():
    cfg=load_config()['events'];cfg['wrong_way_seconds']=.5
    e=EventDetector(cfg)
    def v(t):return vehicle(t,36,[dict(timestamp=t-.5,point=[0,10]),dict(timestamp=t,point=[0,5])])
    assert not e.update(v(1),[0,1])
    assert any(x['event']=='WRONG WAY' for x in e.update(v(1.6),[0,1]))
    e=EventDetector(cfg)
    for t in (1,2,3):assert not e.update(v(t),[0,-1])


def test_lanes_are_pixel_polygons():
    lanes=LaneDetector([dict(name='left',points=[[0,0],[10,0],[10,100],[0,100]])])
    assert lanes.find([5,50])['name']=='left'
    assert lanes.find([20,50]) is None


def test_scene_input_invalid_geometry():
    with pytest.raises(ValueError):SceneInput(counting_line=[[1,1],[1,1]])
    with pytest.raises(ValueError):SceneInput(lanes=[dict(name='bad',points=[[0,0],[1,0],[1,1]],direction=[0,0])])
    with pytest.raises(ValueError):RuntimeSettings(legal_direction=[0,0])


def test_pipeline_no_fake_speed_csv_and_bottom_center():
    from backend.processor import TrafficProcessor
    class Reader:
        width=200;height=400;display_width=100;display_height=200
        def __init__(self):self.index=0
        def read(self):
            i=self.index;self.index+=1
            return (i,i/30,np.zeros((200,100,3),np.uint8)) if i<20 else None
    class Detector:
        device='cpu';detect_ms=1
        def __init__(self):self.i=0
        def detect(self,frame):self.i+=1;return [det(self.i)]
    c=load_config();c['video']['detection_interval']=1
    processor=TrafficProcessor(Reader(),Detector(),c,dict(lanes=[],counting_line=None))
    frames=[]
    while (frame:=processor.step()) is not None:frames.append(frame)
    processor.close()
    assert len(frames)==20 and frames[-1]['vehicles']
    v=frames[-1]['vehicles'][0]
    assert v['pixel'][1]==pytest.approx(120)  # y2, not bbox center; 2x display scale.
    assert v['speed'] is None and v['world'] is None
    assert frames[-1]['metrics']['average_speed'] is None
    assert len(v['trajectory'])>10
    rows=list(csv.DictReader((processor.exporter.directory/'vehicles.csv').open(encoding='utf-8-sig')))
    assert rows and all(r['speed']=='' for r in rows)
