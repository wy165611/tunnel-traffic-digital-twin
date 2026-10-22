import assert from 'node:assert/strict';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';

const result = await build({entryPoints: [fileURLToPath(new URL('../src/utils/birdseye.ts', import.meta.url))], bundle: true, write: false, format: 'esm', platform: 'node'});
const {homography, project, buildBirdseye} = await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
const near = (a, b) => assert.ok(Math.abs(a-b)<1e-7, `${a} != ${b}`);

const image = [[0,0],[100,0],[100,200],[0,200]];
const metres = [[0,0],[12,0],[12,40],[0,40]];

test('identity homography maps every point to itself', () => {
  const h = homography(image, image);
  for (const point of image) {
    const mapped = project(h, point);
    near(mapped[0], point[0]); near(mapped[1], point[1]);
  }
});

test('rectangle homography converts pixels to metres', () => {
  const h = homography(image, metres);
  assert.ok(h);
  const centre = project(h, [50,100]);
  near(centre[0], 6); near(centre[1], 20);
  const corner = project(h, [100,200]);
  near(corner[0], 12); near(corner[1], 40);
});

test('degenerate four points are rejected instead of guessing', () => {
  assert.equal(homography([[0,0],[0,0],[10,10],[10,10]], metres), null);
});

test('birdseye projects lanes, virtual loops and counting line onto the road', () => {
  const calibration = {points:image, width_m:40, length_m:12, edge_1_2_m:12, edge_2_3_m:40, travel_edge_mode:'auto'};
  const scene = {
    counting_line:[[0,100],[100,100]],
    lanes:[{name:'Lane 1', points:[[0,0],[50,0],[50,200],[0,200]], direction:[0,1]}],
    virtual_loops:[{lane:'Lane 1', points:[[10,80],[40,80],[40,120],[10,120]]}],
  };
  const road = buildBirdseye(calibration, scene);
  assert.ok(road);
  near(road.width, 12); near(road.length, 40);
  assert.deepEqual(road.lanes[0].points.map(point => point.map(value => Math.round(value*1000)/1000)),
    [[0,0],[6,0],[6,40],[0,40]]);
  near(road.countingLine[0][0], 0); near(road.countingLine[0][1], 20);
  near(road.countingLine[1][0], 12); near(road.countingLine[1][1], 20);
  near(road.loops[0][0][0], 1.2); near(road.loops[0][0][1], 16);
});

test('incomplete or invalid measurements do not produce a preview', () => {
  const calibration = {points:image, width_m:0, length_m:0, edge_1_2_m:0, edge_2_3_m:0, travel_edge_mode:'auto'};
  assert.equal(buildBirdseye(calibration, {counting_line:null, lanes:[]}), null);
  assert.equal(buildBirdseye({...calibration, points:[[0,0],[1,1]]}, {counting_line:null, lanes:[]}), null);
});
