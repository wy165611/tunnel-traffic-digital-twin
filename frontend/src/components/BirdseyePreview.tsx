import {useMemo} from 'react';
import type {Calibration, Point, Scene} from '../types';
import {buildBirdseye} from '../utils/birdseye';
import {calibrationEdgeLengths, travelEdgeLabel} from '../utils/calibrationGeometry';

const ring = (points: Point[]) => points.map(point => point.join(',')).join(' ');

function centroid(points: Point[]): Point {
  if (!points.length) return [0, 0];
  return [points.reduce((sum, point) => sum+point[0], 0)/points.length,
    points.reduce((sum, point) => sum+point[1], 0)/points.length];
}

/** Top-down road preview built from the four corners and both measured edges. */
export default function BirdseyePreview({calibration,scene}:{calibration:Calibration|null;scene:Scene}){
  const road = useMemo(() => calibration ? buildBirdseye(calibration, scene) : null, [calibration, scene]);
  if (!calibration || !road) {
    return <div className="birdseye-empty hint">完成 4 个角点并填写两条实测边后，这里显示按实际尺度还原的鸟瞰道路。</div>;
  }
  const pad = Math.max(1, Math.max(road.width, road.length)*.06);
  const labelSize = Math.max(road.width, road.length)*.045;
  const view = `${-pad} ${-pad} ${road.width+pad*2} ${road.length+pad*2}`;
  const edges = calibrationEdgeLengths(calibration);
  return <figure className="birdseye">
    <svg viewBox={view} role="img" aria-label={`道路鸟瞰预览：宽 ${road.width.toFixed(1)} 米，长 ${road.length.toFixed(1)} 米`} preserveAspectRatio="xMidYMid meet">
      <rect className="birdseye-road" x="0" y="0" width={road.width} height={road.length}/>
      {road.lanes.map((lane,index) => lane.points.length>2 && <g key={lane.name}>
        <polygon className={'birdseye-lane series-'+index%4} points={ring(lane.points)}/>
        <text className="birdseye-name" fontSize={labelSize} x={centroid(lane.points)[0]} y={centroid(lane.points)[1]}>{lane.name}</text>
      </g>)}
      {road.loops.map((loop,index) => loop.length>2 && <polygon key={'loop-'+index} className="birdseye-loop" points={ring(loop)}/>)}
      {road.countingLine.length===2 && <line className="birdseye-counting" x1={road.countingLine[0][0]} y1={road.countingLine[0][1]} x2={road.countingLine[1][0]} y2={road.countingLine[1][1]}/>}
      <g className="birdseye-arrow" aria-hidden="true">
        <line x1={road.width/2} y1={road.length*.38} x2={road.width/2} y2={road.length*.62}/>
        <polygon points={`${road.width/2},${road.length*.70} ${road.width/2-road.width*.035},${road.length*.62} ${road.width/2+road.width*.035},${road.length*.62}`}/>
      </g>
      <text className="birdseye-axis" fontSize={labelSize} x={road.width/2} y={-pad*.35} textAnchor="middle">宽 {road.width.toFixed(1)} m</text>
      <text className="birdseye-axis" fontSize={labelSize} x={-pad*.25} y={road.length/2} textAnchor="middle" transform={`rotate(-90 ${-pad*.25} ${road.length/2})`}>长 {road.length.toFixed(1)} m</text>
    </svg>
    <figcaption>
      <span>边 1→2（P1→P2，画面上边缘）{edges.edge12.toFixed(1)} m</span>
      <span>边 2→3（P2→P3，画面右边缘）{edges.edge23.toFixed(1)} m</span>
      <strong>行车轴：{travelEdgeLabel(road.travelEdge)} · +Y 箭头方向</strong>
    </figcaption>
  </figure>;
}
