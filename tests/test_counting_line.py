import pytest
from backend.traffic.counting_line import automatic_counting_line, resolve_counting_line
from backend.traffic.flow_counter import FlowCounter


@pytest.mark.parametrize('width,height,line',[
    (3840,2160,[[1920,0],[1920,2160]]),
    (2160,3840,[[0,1920],[2160,1920]]),
    (400,400,[[0,200],[400,200]]),
])
def test_auto_line_counts_both_directions_once(width,height,line):
    generated=automatic_counting_line(width,height)
    assert generated==line
    f=FlowCounter(generated)
    a,b=([width*.25,height*.5],[width*.75,height*.5]) if width>height else ([width*.5,height*.25],[width*.5,height*.75])
    f.update(1,a,0,'car',None)
    assert f.update(1,b,1,'car',None)
    assert not f.update(1,a,2,'car',None)
    f.update(2,b,0,'truck',None)
    assert f.update(2,a,1,'truck',None)
    assert f.metrics(2)['total_flow']==2


def test_auto_line_spans_all_lanes_and_clamps_to_video():
    lanes=[dict(points=[[0,90],[600,90],[600,120],[0,120]]),dict(points=[[0,180],[600,180],[600,210],[0,210]])]
    assert automatic_counting_line(600,300,lanes)==[[300,90],[300,210]]
    lanes=[dict(points=[[20,0],[60,0],[60,600],[20,600]]),dict(points=[[100,0],[160,0],[160,600],[100,600]])]
    assert automatic_counting_line(300,600,lanes)==[[20,300],[160,300]]
    assert automatic_counting_line(600,300,[dict(points=[[0,-10],[600,-10],[600,400],[0,400]])])==[[300,0],[300,300]]


def test_flow_counter_does_not_bridge_off_screen_jump():
    f = FlowCounter([[100, 0], [100, 200]])
    f.update(1, [10, 50], 0, 'car', 'Lane 1')
    f.forget(1)
    assert not f.update(1, [180, 50], 1, 'car', 'Lane 1')
    assert f.crossing_count == 0


def test_auto_scene_does_not_mutate_input_and_recomputes_for_new_dimensions():
    scene=dict(lanes=[],counting_line=None)
    resolved=resolve_counting_line(scene,400,200)
    assert scene==dict(lanes=[],counting_line=None)
    assert resolved['counting_line_mode']=='auto'
    assert resolve_counting_line(resolved,200,400)['counting_line']==[[0,200],[200,200]]
