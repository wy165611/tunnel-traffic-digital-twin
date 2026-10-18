import type {Calibration, Point, Scene, Snapshot} from '../types';
import {calibrationDimensions, calibrationTarget, worldAxisImageVectors} from './calibrationGeometry';

// Lane outlines use pixels; calibrated vehicles already use metres.
// Solve this once per redraw so both layers share the same projection.
function pixelProjection(calibration: Calibration | null, scene?: Pick<Scene, 'lanes' | 'counting_line'>): (p: Point) => Point {
  if (!calibration) return p => p;
  const target: Point[] = calibrationTarget(calibration, scene);
  const rows: number[][] = [];
  calibration.points.forEach(([x, y], i) => {
    const [u, v] = target[i];
    rows.push([x, y, 1, 0, 0, 0, -u*x, -u*y, u], [0, 0, 0, x, y, 1, -v*x, -v*y, v]);
  });
  for (let i = 0; i < 8; i++) {
    let pivot = i;
    for (let j = i + 1; j < 8; j++) if (Math.abs(rows[j][i]) > Math.abs(rows[pivot][i])) pivot = j;
    [rows[i], rows[pivot]] = [rows[pivot], rows[i]];
    const divisor = rows[i][i];
    if (Math.abs(divisor) < 1e-10) return () => [NaN, NaN];
    for (let j = i; j < 9; j++) rows[i][j] /= divisor;
    for (let k = 0; k < 8; k++) if (k !== i) {
      const factor = rows[k][i];
      for (let j = i; j < 9; j++) rows[k][j] -= factor*rows[i][j];
    }
  }
  const h = rows.map(row => row[8]);
  return ([x, y]) => {
    const denominator = h[6]*x + h[7]*y + 1;
    return [(h[0]*x + h[1]*y + h[2])/denominator, (h[3]*x + h[4]*y + h[5])/denominator];
  };
}

export function createTwinViewport(state: Pick<Snapshot, 'video' | 'calibration'> & {scene?: Scene}, canvasWidth: number, canvasHeight: number) {
  const calibration = state.calibration;
  const dimensions = calibration ? calibrationDimensions(calibration, state.scene) : null;
  const width = dimensions?.width || state.video?.width || 1;
  const height = dimensions?.length || state.video?.height || 1;
  const projectPixel = pixelProjection(calibration, state.scene);
  let angle = 0, handedness = 1;
  if (calibration) {
    const vectors = worldAxisImageVectors(calibration.points, dimensions?.edge ?? '2-3');
    const x = vectors.x, y = vectors.y;
    handedness = x[0]*y[1]-x[1]*y[0] < 0 ? -1 : 1;
    // Align the longer road axis to the source image, retaining metric shape.
    angle = height >= width ? Math.atan2(y[1], y[0])-handedness*Math.PI/2 : Math.atan2(x[1], x[0]);
  }
  const cosine = Math.cos(angle), sine = Math.sin(angle);
  const rotate = ([x, y]: Point): Point => [x*cosine-y*handedness*sine, x*sine+y*handedness*cosine];
  const corners: Point[] = [[0, 0], [width, 0], [width, height], [0, height]];
  const rotated = corners.map(rotate);
  const left = Math.min(...rotated.map(p => p[0])), top = Math.min(...rotated.map(p => p[1]));
  const extentX = Math.max(...rotated.map(p => p[0]))-left, extentY = Math.max(...rotated.map(p => p[1]))-top;
  // Reserve space for the coordinate caption and footer on narrow screens too.
  const paddingX = Math.min(32, canvasWidth*.08), paddingY = 48;
  const scale = Math.min(Math.max(1, canvasWidth-2*paddingX)/extentX, Math.max(1, canvasHeight-2*paddingY)/extentY);
  const offsetX = (canvasWidth-extentX*scale)/2-left*scale;
  const offsetY = (canvasHeight-extentY*scale)/2-top*scale;
  const map = (p: Point): Point => {const [x, y] = rotate(p); return [offsetX+x*scale, offsetY+y*scale];};
  const vector = (p: Point): Point => {const [x, y] = rotate(p); return [x*scale, y*scale];};
  return {width, height, scale, map, vector, mapPixel: (p: Point) => map(projectPixel(p)), corners: corners.map(map)};
}

export function directionArrow([x, y]: Point): string {
  return ['→', '↘', '↓', '↙', '←', '↖', '↑', '↗'][(Math.round(Math.atan2(y, x)/(Math.PI/4))+8)%8];
}
