import type {Calibration, Point, Scene} from '../types';

export type TravelEdge = '1-2' | '2-3';
export type TravelSource = 'measured_length' | 'lane_alignment' | 'counting_line' | 'default' | 'manual';
export interface TravelDetection {edge: TravelEdge; source: TravelSource}
type SceneGeometry = Pick<Scene, 'lanes' | 'counting_line'> | undefined;

export const MEASURED_LENGTH_MARGIN = 0.02;
export const ALIGNMENT_MARGIN = 0.15;

const unit = ([x, y]: Point): Point => {
  const length = Math.hypot(x, y);
  return length < 1e-9 || !Number.isFinite(length) ? [0, 0] : [x/length, y/length];
};
const dot = (a: Point, b: Point) => a[0]*b[0]+a[1]*b[1];

function pairDirection(points: Point[], edge: TravelEdge): Point {
  const [a, b, c, d] = points;
  const vectors = edge === '1-2'
    ? [[b[0]-a[0], b[1]-a[1]], [c[0]-d[0], c[1]-d[1]]]
    : [[c[0]-b[0], c[1]-b[1]], [d[0]-a[0], d[1]-a[1]]];
  const first = unit(vectors[0] as Point), second = unit(vectors[1] as Point);
  return unit([first[0]+second[0], first[1]+second[1]]);
}

function laneAxisScore(lanes: Scene['lanes'], direction: Point): number | null {
  let total = 0, weight = 0;
  for (const lane of lanes) {
    if (lane.points.length < 2) continue;
    let longest = 0, axis: Point = [0, 0];
    for (let i = 0; i < lane.points.length; i++) {
      for (let j = i+1; j < lane.points.length; j++) {
        const dx = lane.points[j][0]-lane.points[i][0], dy = lane.points[j][1]-lane.points[i][1];
        const length = Math.hypot(dx, dy);
        if (length > longest) {
          longest = length;
          axis = [dx, dy];
        }
      }
    }
    if (longest < 1 || !Number.isFinite(longest)) continue;
    const unitAxis = unit(axis);
    total += longest*Math.abs(dot(unitAxis, direction));
    weight += longest;
  }
  return weight ? total/weight : null;
}

function countingAxisScore(countingLine: Scene['counting_line'], direction: Point): number | null {
  if (!countingLine) return null;
  const line = unit([countingLine[1][0]-countingLine[0][0], countingLine[1][1]-countingLine[0][1]]);
  if (Math.hypot(...line) < .5) return null;
  return Math.abs(dot([-line[1], line[0]], direction));
}

export function detectTravelEdge(points: Point[], edge12: number, edge23: number, scene?: SceneGeometry): TravelDetection {
  if (!(edge12 >= .1 && edge12 <= 10000 && edge23 >= .1 && edge23 <= 10000)) {
    throw new Error('请输入合理的道路实际宽度和长度');
  }
  if (Math.max(edge12, edge23)/Math.min(edge12, edge23) >= 1+MEASURED_LENGTH_MARGIN) {
    return {edge: edge12 > edge23 ? '1-2' : '2-3', source: 'measured_length'};
  }
  const directions: Record<TravelEdge, Point> = {'1-2': pairDirection(points, '1-2'), '2-3': pairDirection(points, '2-3')};
  if (scene?.lanes.length) {
    const first = laneAxisScore(scene.lanes, directions['1-2']);
    const second = laneAxisScore(scene.lanes, directions['2-3']);
    if (first !== null && second !== null && Math.abs(first-second) >= ALIGNMENT_MARGIN) {
      return {edge: first > second ? '1-2' : '2-3', source: 'lane_alignment'};
    }
  }
  if (scene?.counting_line) {
    const first = countingAxisScore(scene.counting_line, directions['1-2']);
    const second = countingAxisScore(scene.counting_line, directions['2-3']);
    if (first !== null && second !== null && Math.abs(first-second) >= ALIGNMENT_MARGIN) {
      return {edge: first > second ? '1-2' : '2-3', source: 'counting_line'};
    }
  }
  return {edge: '2-3', source: 'default'};
}

export function calibrationEdgeLengths(calibration: Calibration): {edge12: number; edge23: number} {
  return {edge12: calibration.edge_1_2_m ?? calibration.width_m, edge23: calibration.edge_2_3_m ?? calibration.length_m};
}

export function resolveTravelEdge(calibration: Calibration, scene?: SceneGeometry): TravelDetection {
  if (calibration.travel_edge_mode === 'manual' && calibration.travel_edge) {
    return {edge: calibration.travel_edge, source: 'manual'};
  }
  const {edge12, edge23} = calibrationEdgeLengths(calibration);
  if (edge12 >= .1 && edge23 >= .1) return detectTravelEdge(calibration.points, edge12, edge23, scene);
  if (calibration.travel_edge) return {edge: calibration.travel_edge, source: calibration.travel_edge_source ?? 'measured_length'};
  return {edge: '2-3', source: 'default'};
}

export function calibrationDimensions(calibration: Calibration, scene?: SceneGeometry) {
  const edges = calibrationEdgeLengths(calibration);
  const travel = resolveTravelEdge(calibration, scene);
  return {
    width: travel.edge === '1-2' ? edges.edge23 : edges.edge12,
    length: travel.edge === '1-2' ? edges.edge12 : edges.edge23,
    ...travel,
  };
}

/** Target quad in road coordinates; +Y always follows the detected travel edge. */
export function calibrationTarget(calibration: Calibration, scene?: SceneGeometry): Point[] {
  const {width, length, edge} = calibrationDimensions(calibration, scene);
  return edge === '1-2'
    ? [[0, 0], [0, length], [width, length], [width, 0]]
    : [[0, 0], [width, 0], [width, length], [0, length]];
}

/** Image-space directions of the world +X (across) and +Y (travel) axes. */
export function worldAxisImageVectors(points: Point[], edge: TravelEdge): {x: Point; y: Point} {
  const [a, b, c, d] = points;
  if (edge === '1-2') {
    return {
      x: [d[0]-a[0]+c[0]-b[0], d[1]-a[1]+c[1]-b[1]],
      y: [b[0]-a[0]+c[0]-d[0], b[1]-a[1]+c[1]-d[1]],
    };
  }
  return {
    x: [b[0]-a[0]+c[0]-d[0], b[1]-a[1]+c[1]-d[1]],
    y: [d[0]-a[0]+c[0]-b[0], d[1]-a[1]+c[1]-b[1]],
  };
}

export const travelEdgeLabel = (edge: TravelEdge) => edge === '1-2' ? '边 1→2' : '边 2→3';
export const travelSourceLabel = (source: TravelSource) => ({
  measured_length: '实测长度', lane_alignment: '车道走向', counting_line: '计数线方向', default: '默认回退', manual: '手动指定',
})[source];
