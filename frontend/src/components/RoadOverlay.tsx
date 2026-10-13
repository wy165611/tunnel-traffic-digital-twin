import {useEffect,useRef,useState,type ReactNode} from 'react';
import type {Calibration,ObservationSamples,Scene} from '../types';
import {containRect,sceneLabelPoint} from '../utils/manualAnalysis';
export function SceneOverlay({width,height,viewWidth,viewHeight,scene,calibration,samples}:{width:number;height:number;viewWidth:number;viewHeight:number;scene:Scene;calibration?:Calibration|null;samples?:ObservationSamples|null}){
 const fit=containRect(width,height,viewWidth,viewHeight),scale=fit.scale||1;
 return <svg className="road-overlay" viewBox={`0 0 ${viewWidth||1} ${viewHeight||1}`} aria-label="保存道路的计数线、车道与观测 ID" role="img"><g transform={`translate(${fit.x} ${fit.y}) scale(${scale})`}>
 {scene.lanes.map(lane=>{const [x,y]=sceneLabelPoint(lane.points);return <g key={lane.name}><polygon points={lane.points.map(p=>p.join(',')).join(' ')} fill="color-mix(in srgb, var(--accent) 10%, transparent)" stroke="var(--accent)" strokeWidth="1.5" vectorEffect="non-scaling-stroke"/><text x={x} y={y} fontSize={13/scale} fill="var(--text)" textAnchor="middle" stroke="var(--bg)" strokeWidth={2/scale} paintOrder="stroke">{lane.name}</text></g>;})}
 {scene.counting_line&&<g><polyline points={scene.counting_line.map(p=>p.join(',')).join(' ')} fill="none" stroke="var(--warning)" strokeWidth="2.5" vectorEffect="non-scaling-stroke"/><text x={scene.counting_line[0][0]} y={scene.counting_line[0][1]+18/scale} fontSize={12/scale} fill="var(--warning)" stroke="var(--bg)" strokeWidth={2/scale} paintOrder="stroke">计数线</text></g>}
 {calibration?.points.map(([x,y],index)=><g key={index}><circle cx={x} cy={y} r={4/scale} fill="var(--accent)"/><text x={x+6/scale} y={y-6/scale} fontSize={12/scale} fill="var(--text)">标定{index+1}</text></g>)}
 {samples?.items.map(item=><g key={item.vehicle_id}><circle cx={item.pixel[0]} cy={item.pixel[1]} r={4/scale} fill="var(--danger)"/><text x={item.pixel[0]+6/scale} y={item.pixel[1]-7/scale} fontSize={13/scale} fill="var(--danger)" stroke="var(--bg)" strokeWidth={2/scale} paintOrder="stroke">#{item.vehicle_id}</text></g>)}
 </g></svg>;
}
export default function RoadOverlay({children,width,height,scene,calibration,samples}:{children:ReactNode;width:number;height:number;scene:Scene;calibration?:Calibration|null;samples?:ObservationSamples|null}){
 const ref=useRef<HTMLDivElement>(null),[size,setSize]=useState([1,1]);
 useEffect(()=>{const observer=new ResizeObserver(()=>{if(ref.current)setSize([ref.current.clientWidth,ref.current.clientHeight]);});observer.observe(ref.current!);return()=>observer.disconnect();},[]);
 return <div ref={ref} className="road-preview">{children}<SceneOverlay width={width} height={height} viewWidth={size[0]} viewHeight={size[1]} scene={scene} calibration={calibration} samples={samples}/></div>;
}
