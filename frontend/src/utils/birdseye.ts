import type {Calibration, Point, Scene} from '../types';
import {calibrationDimensions, calibrationTarget, type TravelEdge} from './calibrationGeometry';

/** Eight coefficients of a plane-to-plane projective transform. */
export type Homography = number[];

function solve(matrix: number[][], values: number[]): number[] | null {
  const size = values.length;
  const rows = matrix.map((row, index) => [...row, values[index]]);
  for (let column = 0; column < size; column++) {
    let pivot = column;
    for (let row = column+1; row < size; row++) {
      if (Math.abs(rows[row][column]) > Math.abs(rows[pivot][column])) pivot = row;
    }
    if (Math.abs(rows[pivot][column]) < 1e-10) return null;
    [rows[column], rows[pivot]] = [rows[pivot], rows[column]];
    const divisor = rows[column][column];
    for (let index = column; index <= size; index++) rows[column][index] /= divisor;
    for (let row = 0; row < size; row++) {
      if (row === column) continue;
      const factor = rows[row][column];
      if (!factor) continue;
      for (let index = column; index <= size; index++) rows[row][index] -= factor*rows[column][index];
    }
  }
  return rows.map(row => row[size]);
}

/** Solve the 4-point homography mapping source pixels to road metres. */
export function homography(source: Point[], target: Point[]): Homography | null {
  if (source.length !== 4 || target.length !== 4) return null;
  const matrix: number[][] = [], values: number[] = [];
  for (let index = 0; index < 4; index++) {
    const [x, y] = source[index], [u, v] = target[index];
    matrix.push([x, y, 1, 0, 0, 0, -u*x, -u*y]);
    values.push(u);
    matrix.push([0, 0, 0, x, y, 1, -v*x, -v*y]);
    values.push(v);
  }
  return solve(matrix, values);
}

export function project(transform: Homography, [x, y]: Point): Point | null {
  const denominator = transform[6]*x+transform[7]*y+1;
  if (Math.abs(denominator) < 1e-9 || !Number.isFinite(denominator)) return null;
  const point: Point = [(transform[0]*x+transform[1]*y+transform[2])/denominator,
    (transform[3]*x+transform[4]*y+transform[5])/denominator];
  return point.every(Number.isFinite) ? point : null;
}

function mapRing(transform: Homography, points: Point[]): Point[] {
  const mapped = points.map(point => project(transform, point));
  return mapped.every((point): point is Point => point !== null) ? mapped as Point[] : [];
}

export interface BirdseyeRoad {
  width: number;
  length: number;
  travelEdge: TravelEdge;
  lanes: {name: string; points: Point[]}[];
  loops: Point[][];
  countingLine: Point[];
}

/** Project the saved scene onto the measured road plane for a top-down preview. */
export function buildBirdseye(calibration: Calibration, scene?: Pick<Scene, 'lanes'|'counting_line'|'virtual_loops'>): BirdseyeRoad | null {
  const points = calibration.points;
  if (!points || points.length !== 4) return null;
  const dimensions = calibrationDimensions(calibration, scene);
  if (!(dimensions.width >= .1 && dimensions.length >= .1)) return null;
  const transform = homography(points, calibrationTarget(calibration, scene));
  if (!transform) return null;
  return {
    width: dimensions.width,
    length: dimensions.length,
    travelEdge: dimensions.edge,
    lanes: (scene?.lanes || []).map(lane => ({name: lane.name, points: mapRing(transform, lane.points)})),
    loops: (scene?.virtual_loops || []).map(loop => mapRing(transform, loop.points)),
    countingLine: mapRing(transform, scene?.counting_line || []),
  };
}
