import assert from 'node:assert/strict';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';

const result = await build({entryPoints: [fileURLToPath(new URL('../src/utils/calibrationGeometry.ts', import.meta.url))], bundle: true, write: false, format: 'esm', platform: 'node'});
const {calibrationDimensions, calibrationTarget, detectTravelEdge, resolveTravelEdge, worldAxisImageVectors} = await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
const near = (a, b) => assert.ok(Math.abs(a-b)<1e-7, `${a} != ${b}`);
const calibration = (points, edge12, edge23, extra={}) => ({points, width_m:edge23, length_m:edge12, edge_1_2_m:edge12, edge_2_3_m:edge23, schema_version:2, travel_edge_mode:'auto', ...extra});

const portrait = [[100,100],[300,100],[300,900],[100,900]];
const landscape = [[100,100],[900,100],[900,400],[100,400]];
const diagonal = [[200,0],[400,200],[200,400],[0,150]];

test('portrait road detects edge 2->3 as travel', () => {
  const points = portrait, cal = calibration(points, 12, 40);
  assert.deepEqual(detectTravelEdge(points, 12, 40), {edge:'2-3', source:'measured_length'});
  const dims = calibrationDimensions(cal);
  assert.equal(dims.edge, '2-3');
  assert.equal(dims.width, 12);
  assert.equal(dims.length, 40);
  assert.deepEqual(calibrationTarget(cal), [[0,0],[12,0],[12,40],[0,40]]);
});

test('landscape road detects edge 1->2 as travel and swaps width/length', () => {
  const points = landscape, cal = calibration(points, 40, 12);
  assert.deepEqual(detectTravelEdge(points, 40, 12), {edge:'1-2', source:'measured_length'});
  const dims = calibrationDimensions(cal);
  assert.equal(dims.edge, '1-2');
  assert.equal(dims.width, 12);
  assert.equal(dims.length, 40);
  assert.deepEqual(calibrationTarget(cal), [[0,0],[0,40],[12,40],[12,0]]);
});

test('diagonal road detects the longer measured edge regardless of image orientation', () => {
  const points = diagonal, cal = calibration(points, 40, 12);
  assert.deepEqual(detectTravelEdge(points, 40, 12), {edge:'1-2', source:'measured_length'});
  const dims = calibrationDimensions(cal);
  assert.equal(dims.width, 12);
  assert.equal(dims.length, 40);
  const {x,y} = worldAxisImageVectors(points, '1-2');
  near(x[0], -400); near(x[1], 350); // across the road, P1->P4 + P2->P3
  near(y[0], 400); near(y[1], 450); // along travel, P1->P2 + P4->P3
});

test('manual override swaps the travel edge and dimensions', () => {
  const cal = calibration(landscape, 40, 12, {travel_edge:'2-3', travel_edge_mode:'manual', travel_edge_source:'manual'});
  assert.deepEqual(resolveTravelEdge(cal), {edge:'2-3', source:'manual'});
  const dims = calibrationDimensions(cal);
  assert.equal(dims.width, 40);
  assert.equal(dims.length, 12);
  assert.deepEqual(calibrationTarget(cal), [[0,0],[40,0],[40,12],[0,12]]);
});

test('near-equal measurements fall back to lanes, counting line, then legacy edge', () => {
  const lanesAlong = {lanes:[{name:'L',points:[[100,150],[900,150],[900,250],[100,250]],direction:[0,1]}], counting_line:null};
  assert.deepEqual(detectTravelEdge(landscape, 20, 20, lanesAlong), {edge:'1-2', source:'lane_alignment'});
  const lanesAcross = {lanes:[{name:'L',points:[[300,100],[500,100],[500,400],[300,400]],direction:[0,1]}], counting_line:null};
  assert.deepEqual(detectTravelEdge(landscape, 20, 20, lanesAcross), {edge:'2-3', source:'lane_alignment'});
  assert.deepEqual(detectTravelEdge(landscape, 20, 20, {lanes:[], counting_line:[[500,0],[500,500]]}), {edge:'1-2', source:'counting_line'});
  assert.deepEqual(detectTravelEdge(landscape, 20, 20), {edge:'2-3', source:'default'});
});

test('legacy calibration without edge fields keeps the legacy edge 2->3 mapping', () => {
  const cal = {points:portrait, width_m:12, length_m:40};
  assert.deepEqual(resolveTravelEdge(cal), {edge:'2-3', source:'measured_length'});
  const dims = calibrationDimensions(cal);
  assert.equal(dims.width, 12);
  assert.equal(dims.length, 40);
});
