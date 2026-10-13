import assert from 'node:assert/strict';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';

const result = await build({entryPoints: [fileURLToPath(new URL('../src/utils/twinGeometry.ts', import.meta.url))], bundle: true, write: false, format: 'esm', platform: 'node'});
const {createTwinViewport, directionArrow} = await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
const near = (a, b) => assert.ok(Math.abs(a-b)<1e-7, `${a} != ${b}`);
const distance = (a, b) => Math.hypot(a[0]-b[0], a[1]-b[1]);
const state = (width, height, calibration=null) => ({video: {width, height}, calibration});

for (const [width, height] of [[3840,2160], [2160,3840]]) {
  for (const [cw, ch] of [[640,490], [286,370]]) {
    test(`${width}×${height} image preserves orientation and proportions in ${cw}×${ch}`, () => {
      const v = createTwinViewport(state(width,height),cw,ch);
      const [a,b,c,d] = v.corners;
      near(distance(a,b)/distance(a,d),width/height);
      assert.equal(distance(a,b)>distance(a,d),width>height);
      for (const [x,y] of v.corners) assert.ok(x>=0 && x<=cw && y>=0 && y<=ch);
      const pixel=[width*.3,height*.7];
      assert.deepEqual(v.mapPixel(pixel),v.map(pixel));
      near(distance(v.map([0,0]),v.map([100,0])),distance(v.map([0,0]),v.map([0,100])));
    });
  }
}

test('horizontal lanes and counting line retain their image alignment', () => {
  const v=createTwinViewport(state(3840,2160),640,490);
  const lane=[[0,600],[3840,600],[3840,900],[0,900]].map(v.mapPixel);
  near(lane[0][1],lane[1][1]);
  near(lane[2][1],lane[3][1]);
  const car=v.map([2000,750]);
  assert.ok(car[1]>lane[0][1] && car[1]<lane[2][1]);
  const [a,b]=[[2000,600],[2000,900]].map(v.mapPixel);
  near(a[0],car[0]);near(b[0],car[0]);
  assert.equal(directionArrow(v.vector([1,0])),'→');
  assert.equal(directionArrow(v.vector([-1,0])),'←');
});

test('perspective lane vertices and world vehicles use the same metric mapping', () => {
  const calibration={points:[[100,100],[300,120],[400,600],[0,580]],width_m:12,length_m:50};
  const v=createTwinViewport(state(600,800,calibration),640,490);
  calibration.points.forEach((p,i)=>v.mapPixel(p).forEach((n,j)=>near(n,v.corners[i][j])));
  // The world rectangle centre maps to the source diagonals' intersection.
  const car=v.map([6,25]),pixel=v.mapPixel([202.08333333333334,270.1388888888889]);
  near(distance(car,pixel),0);
  near(distance(v.corners[0],v.corners[1])/distance(v.corners[0],v.corners[3]),12/50);
});

test('calibrated horizontal road rotates geometry, heading and axis together', () => {
  const calibration={points:[[100,100],[100,300],[1100,300],[1100,100]],width_m:10,length_m:50};
  const v=createTwinViewport(state(1200,400,calibration),640,490);
  const [a,b,,d]=v.corners;
  near(a[0],b[0]);near(a[1],d[1]);
  assert.ok(d[0]>a[0]);
  assert.equal(directionArrow(v.vector([0,1])),'→');
  assert.equal(directionArrow(v.vector([0,-1])),'←');
  near(distance(v.map([3,25]),v.mapPixel([600,160])),0);
});

test('oblique calibrated road keeps metric distances and fits after resize', () => {
  const calibration={points:[[100,100],[200,200],[0,400],[-100,300]],width_m:10,length_m:20};
  for(const [w,h] of [[640,490],[286,370]]) {
    const v=createTwinViewport(state(800,800,calibration),w,h);
    near(distance(v.corners[0],v.corners[1])/distance(v.corners[0],v.corners[3]),.5);
    for(const [x,y] of v.corners) assert.ok(x>=0 && x<=w && y>=0 && y<=h);
    assert.equal(directionArrow(v.vector([0,1])),'↙');
  }
});
