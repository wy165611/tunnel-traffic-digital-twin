import {useEffect,useLayoutEffect,useRef} from 'react';
import type {Snapshot,Point} from '../types';
import {formatSpeed} from '../api';
import {readVisualTheme} from '../theme';
import {createTwinViewport,directionArrow} from '../utils/twinGeometry';
import {placeCanvasLabel,type LabelRect} from '../utils/canvasLabel';
import {roundedRectPath} from '../utils/canvasShape';

export default function DigitalTwin({state}:{state:Snapshot}){
 const themeRef=useRef<ReturnType<typeof readVisualTheme>|null>(null);
 if(!themeRef.current)themeRef.current=readVisualTheme();
 const theme=themeRef.current;
 const canvas=useRef<HTMLCanvasElement>(null), container=useRef<HTMLDivElement>(null);
 const redraw=useRef(()=>{});
 redraw.current=()=>{
  const c=canvas.current, div=container.current;if(!c||!div)return;
   const W=div.clientWidth,H=div.clientHeight,dpr=window.devicePixelRatio||1;if(c.width!==Math.round(W*dpr))c.width=Math.round(W*dpr);if(c.height!==Math.round(H*dpr))c.height=Math.round(H*dpr);c.style.width=W+'px';c.style.height=H+'px';
   const ctx=c.getContext('2d')!;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.textAlign='left';
   ctx.fillStyle=theme.bg;ctx.fillRect(0,0,W,H);
   ctx.strokeStyle=theme.surface;ctx.lineWidth=.5;for(let x=0;x<W;x+=28){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}for(let y=0;y<H;y+=28){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
   if(!state.video){ctx.fillStyle=theme.subtle;ctx.font='12px sans-serif';ctx.textAlign='center';ctx.fillText('导入视频后显示同步道路与车辆',W/2,H/2);return;}
   const calibrated=!!state.calibration;
   const view=createTwinViewport(state,W,H),{map,mapPixel,vector}=view;
   const outline=(points:Point[])=>{ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();};
   outline(view.corners);
   // Without lane geometry this is the image extent, not an invented road.
   ctx.fillStyle=calibrated?theme.raised:theme.surface;ctx.fill();
   ctx.strokeStyle=calibrated?theme.borderStrong:theme.borderStrong;ctx.lineWidth=1.5;ctx.setLineDash(calibrated?[]:[5,6]);ctx.stroke();ctx.setLineDash([]);
   ctx.save();ctx.clip();
   state.scene.lanes.forEach((lane,i)=>{
    if(!lane.points.length)return;
    const points=lane.points.map(mapPixel);outline(points);
    ctx.fillStyle=[theme.raised,theme.hover][i%2];ctx.fill();ctx.strokeStyle=theme.subtle;ctx.setLineDash([8,10]);ctx.lineWidth=1;ctx.stroke();ctx.setLineDash([]);
    const [x,y]=points[0];ctx.fillStyle=theme.muted;ctx.font='11px '+theme.font;ctx.fillText(String(i+1)+' '+directionArrow(vector(lane.direction)),x+4,y+16);
   });
   if(state.scene.counting_line){const a=mapPixel(state.scene.counting_line[0]),b=mapPixel(state.scene.counting_line[1]);ctx.strokeStyle=theme.warning;ctx.lineWidth=2;ctx.setLineDash([6,4]);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();ctx.setLineDash([]);}
   const labels: {x:number;y:number;id:number;speed:number|null}[]=[];
   (state.vehicles||[]).forEach(vehicle=>{
    if(calibrated&&!vehicle.world)return;
    const point=calibrated?vehicle.world!:vehicle.pixel,[x,y]=map(point), color=vehicle.status==='NORMAL'?(theme.vehicles[vehicle.type]||theme.accent):theme.danger;
    const path=calibrated?vehicle.world_trajectory.map(p=>p.point):vehicle.trajectory;
    ctx.beginPath();path.map(map).forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.strokeStyle=color+'80';ctx.lineWidth=1.5;ctx.stroke();
    const heading=vector([Math.cos(vehicle.heading),Math.sin(vehicle.heading)]);
    ctx.save();ctx.translate(x,y);ctx.rotate(Math.atan2(heading[1],heading[0]));ctx.shadowColor=color;ctx.shadowBlur=0;ctx.fillStyle=color;
    const length=vehicle.type==='truck'||vehicle.type==='bus'?23:17;ctx.beginPath();roundedRectPath(ctx,-length/2,-5,length,10,3);ctx.fill();ctx.shadowBlur=0;ctx.fillStyle=theme.bg;ctx.fillRect(length/2-7,-3,4,6);ctx.restore();
    labels.push({x,y,id:vehicle.id,speed:vehicle.speed});
    if(vehicle.status!=='NORMAL'){ctx.strokeStyle=theme.danger;ctx.beginPath();ctx.arc(x,y,18,0,Math.PI*2);ctx.stroke();}
   });ctx.restore();
   const occupied:LabelRect[]=[];
   labels.forEach(label=>{
    ctx.font='11px '+theme.font;
    const text='#'+label.id,speed=label.speed==null?null:formatSpeed(label.speed);
    const width=Math.max(ctx.measureText(text).width,speed?ctx.measureText(speed).width:0)+8;
    const box=placeCanvasLabel(label.x+12,label.y-18,width,speed?30:17,{width:W,height:H},occupied);
    if(Math.abs(box.y+12-label.y)>12){ctx.strokeStyle=theme.subtle;ctx.lineWidth=.75;ctx.beginPath();ctx.moveTo(label.x,label.y);ctx.lineTo(box.x,box.y+8);ctx.stroke();}
    ctx.fillStyle=theme.bg+'e8';ctx.fillRect(box.x,box.y,box.width,box.height);
    ctx.fillStyle=theme.text;ctx.fillText(text,box.x+4,box.y+12);
    if(speed){ctx.fillStyle=theme.muted;ctx.fillText(speed,box.x+4,box.y+25);}
   });
   ctx.fillStyle=theme.subtle;ctx.font='11px '+theme.font;ctx.fillText(calibrated?`${view.width} m × ${view.height} m · 道路平面`:'图像等比例映射 · 未启用真实尺度',18,26);
   const axis=vector([0,-1]);
   ctx.save();ctx.translate(W-24,38);ctx.rotate(Math.atan2(axis[1],axis[0]));ctx.strokeStyle=theme.subtle;ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(-9,0);ctx.lineTo(9,0);ctx.moveTo(4,-4);ctx.lineTo(9,0);ctx.lineTo(4,4);ctx.stroke();ctx.restore();
   ctx.fillStyle=theme.subtle;ctx.font='11px '+theme.mono;ctx.textAlign='right';ctx.fillText('Y−',W-16,62);
 };
 useLayoutEffect(()=>{redraw.current();},[state]);
 useEffect(()=>{const div=container.current;if(!div)return;const observer=new ResizeObserver(()=>redraw.current());observer.observe(div);return()=>observer.disconnect();},[]);
 return <div className="twin-stage" ref={container}><canvas ref={canvas} aria-label="车辆同步数字孪生俯视图"/><span className="stage-tag">{state.calibration?'世界坐标':state.scene.lanes.length?'图像坐标':'图像坐标 · 未绘制车道'} · 2D</span></div>
}
