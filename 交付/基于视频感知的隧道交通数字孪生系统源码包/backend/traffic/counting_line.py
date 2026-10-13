"""Image-space defaults for flow counting; no metric calibration required."""
import copy


def video_orientation(width, height):
    return 'landscape' if width > height else 'portrait' if height > width else 'square'


def automatic_counting_line(width, height, lanes=None):
    """Cross the frame's long axis at its midpoint, spanning all configured lanes."""
    horizontal_traffic = width > height
    transverse_axis = 1 if horizontal_traffic else 0
    extent = height if horizontal_traffic else width
    points = [p for lane in (lanes or []) for p in lane['points']]
    start = max(0., min(p[transverse_axis] for p in points)) if points else 0.
    end = min(float(extent), max(p[transverse_axis] for p in points)) if points else float(extent)
    if end-start < 1:
        start, end = 0., float(extent)
    if horizontal_traffic:
        return [[width/2, start], [width/2, end]]
    return [[start, height/2], [end, height/2]]


def resolve_counting_line(scene, width, height):
    """Migrate absent legacy lines to auto, preserving manual lines and opt-outs."""
    result = copy.deepcopy(scene)
    mode = result.get('counting_line_mode') or ('manual' if result.get('counting_line') else 'auto')
    if mode == 'auto':
        result['counting_line'] = automatic_counting_line(width, height, result.get('lanes'))
    elif mode == 'disabled':
        result['counting_line'] = None
    result['counting_line_mode'] = mode
    return result
