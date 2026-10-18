import copy
import csv
import math
import numpy as np
import pytest
from backend.calibration.homography import RoadCalibration, detect_travel_edge
from backend.traffic.speed_estimator import SpeedEstimator
from backend.traffic.flow_counter import FlowCounter
from backend.traffic.lane_detector import LaneDetector
from backend.traffic.traffic_metrics import traffic_metrics
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


def test_calibration_rejects_wrong_corner_order():
    with pytest.raises(ValueError, match='左上'):
        RoadCalibration(dict(points=[[100,100],[100,600],[300,600],[300,100]],width_m=10,length_m=50))


def test_calibration_accepts_diagonal_clockwise_quad_and_uses_first_point_as_top_left():
    points=[[200,0],[400,200],[200,400],[0,150]]
    c=RoadCalibration(dict(points=points,width_m=6,length_m=20))
    assert c.map(points[0]) == pytest.approx([0,0])
    assert c.map(points[1]) == pytest.approx([6,0])
    assert c.map(points[2]) == pytest.approx([6,20])
    assert c.map(points[3]) == pytest.approx([0,20])


def test_calibration_edge_1_2_and_2_3_map_to_supplied_lengths():
    points=[[20,30],[220,30],[220,130],[20,130]]
    c=RoadCalibration(dict(points=points,width_m=7,length_m=50))
    assert c.map(points[1]) == pytest.approx([7,0])
    assert c.map(points[2]) == pytest.approx([7,50])


def test_calibration_horizontal_speed_scale():
    import math
    good = RoadCalibration(dict(points=[[100,100],[300,100],[300,600],[100,600]],width_m=10,length_m=50))
    a, b = good.map([100,350]), good.map([120,350])
    assert math.hypot(b[0]-a[0], b[1]-a[1]) * 3.6 == pytest.approx(3.6, rel=.01)


def test_calibration_save_reload(tmp_path):
    c=cal();p=tmp_path/'calibration.json';c.save(p)
    assert RoadCalibration.load(p).map([200,350]) == pytest.approx([5,25])


def test_calibration_auto_detects_travel_edge_for_portrait_landscape_and_diagonal():
    portrait=[[100,100],[300,100],[300,900],[100,900]]
    landscape=[[100,100],[900,100],[900,400],[100,400]]
    diagonal=[[200,0],[400,200],[200,400],[0,150]]
    for points,edge_12,edge_23,travel,width,length in (
            (portrait,12,40,'2-3',12,40),
            (landscape,40,12,'1-2',12,40),
            (diagonal,40,12,'1-2',12,40)):
        c=RoadCalibration(dict(points=points,edge_1_2_m=edge_12,edge_2_3_m=edge_23))
        assert c.travel_edge==travel and c.travel_edge_source=='measured_length'
        assert (c.width,c.length)==(width,length)
        assert c.travel_direction == pytest.approx([0,1])
        assert math.dist(c.map(points[0]),c.map(points[1])) == pytest.approx(edge_12)
        assert math.dist(c.map(points[1]),c.map(points[2])) == pytest.approx(edge_23)
        assert c.payload['width_m']==width and c.payload['length_m']==length
        assert c.payload['edge_1_2_m']==edge_12 and c.payload['edge_2_3_m']==edge_23
    # Travel always maps to +Y: a horizontal movement on a landscape road is
    # the 40 m road length, while the 12 m width is across it.
    c=RoadCalibration(dict(points=landscape,edge_1_2_m=40,edge_2_3_m=12))
    assert c.map([500,250]) == pytest.approx([6,20])
    assert math.dist(c.map([500,100]),c.map([500,400])) == pytest.approx(12)


def test_calibration_manual_travel_edge_override_wins(tmp_path):
    points=[[100,100],[900,100],[900,400],[100,400]]
    c=RoadCalibration(dict(points=points,edge_1_2_m=40,edge_2_3_m=12,
                           travel_edge='2-3',travel_edge_mode='manual'))
    assert c.travel_edge=='2-3' and c.travel_edge_source=='manual'
    assert (c.width,c.length)==(40,12)
    assert c.map(points[1]) == pytest.approx([40,0])
    p=tmp_path/'manual.json';c.save(p)
    reloaded=RoadCalibration.load(p)
    assert reloaded.travel_edge=='2-3' and reloaded.travel_edge_source=='manual'
    with pytest.raises(ValueError,match='手动指定'):
        RoadCalibration(dict(points=points,edge_1_2_m=40,edge_2_3_m=12,travel_edge_mode='manual'))


def test_calibration_near_equal_lengths_fall_back_to_lane_then_counting_line():
    points=[[100,100],[900,100],[900,400],[100,400]]
    assert detect_travel_edge(points,20,20,dict(lanes=[
        dict(name='along',points=[[100,150],[900,150],[900,250],[100,250]])])) == ('1-2','lane_alignment')
    assert detect_travel_edge(points,20,20,dict(lanes=[
        dict(name='across',points=[[300,100],[500,100],[500,400],[300,400]])])) == ('2-3','lane_alignment')
    assert detect_travel_edge(points,20,20,dict(counting_line=[[500,0],[500,500]])) == ('1-2','counting_line')
    assert detect_travel_edge(points,20,20,dict(counting_line=[[0,250],[1000,250]])) == ('2-3','counting_line')
    assert detect_travel_edge(points,20,20) == ('2-3','default')


def test_calibration_legacy_payload_is_migrated_to_schema_2():
    points=[[100,100],[900,100],[900,400],[100,400]]
    c=RoadCalibration(dict(points=points,width_m=40,length_m=12))
    assert c.travel_edge=='1-2' and c.payload['schema_version']==2
    assert c.payload['edge_1_2_m']==40 and c.payload['edge_2_3_m']==12
    assert c.payload['width_m']==12 and c.payload['length_m']==40
    # A legacy portrait payload keeps the original mapping and dimensions.
    portrait=[[100,100],[300,100],[300,900],[100,900]]
    legacy=RoadCalibration(dict(points=portrait,width_m=12,length_m=40))
    assert legacy.map(portrait[2]) == pytest.approx([12,40])


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


def test_traffic_metrics_ignore_predicted_speeds():
    vehicles = [
        dict(observed=True, speed=36, type='car', lane='A', world=[0, 0]),
        dict(observed=False, speed=36, type='car', lane='A', world=[1, 0]),
    ]
    metrics = traffic_metrics(vehicles, {1}, FlowCounter(), 1, None, [])
    assert metrics['average_speed'] == 36


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
