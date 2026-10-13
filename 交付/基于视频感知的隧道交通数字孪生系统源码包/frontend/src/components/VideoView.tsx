import {FileVideo} from 'lucide-react';
import {useLayoutEffect,useRef} from 'react';
import type {Snapshot,Point,Scene,Calibration} from '../types';
import {formatSpeed} from '../api';
import {readVisualTheme} from '../theme';
import {placeCanvasLabel,type LabelRect} from '../utils/canvasLabel';

interface Props {state:Snapshot;image:HTMLImageElement|null;editing:boolean;scene:Scene;calibration:Calibration|null;pending:Point[];onPoint:(p:Point)=>void;onFinish:()=>void}
export default function VideoView({state,image,editing,scene,calibration,pending,onPoint,onFinish}:Props){
 const themeRef=useRef<ReturnType<typeof readVisualTheme>|null>(null);
 if(!themeRef.current)themeRef.current=readVisualTheme();
 const theme=themeRef.current;
 const canvas=useRef<HTMLCanvasElement>(null);
 const latest=useRef({state,image,editing,scene,calibration,pending});latest.current={state,image,editing,scene,calibration,pending};
 const draw=()=>{
  const c=canvas.current, s=latest.current, video=s.state.video, img=s.image;
  if(!c||!video||!img)return;
  if(c.width!==video.display_width)c.width=video.display_width;if(c.height!==video.display_height)c.height=video.display_height;
  const ctx=c.getContext('2d')!;ctx.drawImage(img,0,0,c.width,c.height);
  const fontSize=Math.max(11,Math.round(11*c.height/Math.max(100,c.clientHeight)));
  const sx=c.width/video.width,sy=c.height/video.height;
  const path=(points:Point[],color:string,fill=false,close=false)=>{
   if(!points.length)return;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p[0]*sx,p[1]*sy):ctx.moveTo(p[0]*sx,p[1]*sy));
   if(close)ctx.closePath();ctx.strokeStyle=color;ctx.lineWidth=2;ctx.stroke();if(fill){ctx.fillStyle=color+'20';ctx.fill();}
  };
  s.scene.lanes.forEach((l,i)=>{path(l.points,theme.series[i%4],true,true);if(l.points.length){ctx.fillStyle=theme.text;ctx.font='12px sans-serif';ctx.fillText(l.name,l.points[0][0]*sx+5,l.points[0][1]*sy+18);}});
  if(s.calibration){path(s.calibration.points,theme.warning,true,true);s.calibration.points.forEach((p,i)=>{ctx.fillStyle=theme.warning;ctx.beginPath();ctx.arc(p[0]*sx,p[1]*sy,5,0,Math.PI*2);ctx.fill();ctx.fillText('P'+(i+1),p[0]*sx+7,p[1]*sy-7);});}
  if(s.scene.counting_line){ctx.setLineDash([8,5]);path(s.scene.counting_line,theme.warning);ctx.setLineDash([]);}
  const labels:LabelRect[]=[];
  if(!s.editing) (s.state.vehicles||[]).forEach(v=>{
   const color=v.status==='NORMAL'?(theme.vehicles[v.type]||theme.accent):theme.danger;path(v.trajectory,color);
   const [x1,y1,x2,y2]=v.box;ctx.strokeStyle=color;ctx.lineWidth=2;ctx.strokeRect(x1*sx,y1*sy,(x2-x1)*sx,(y2-y1)*sy);
   const label=`#${v.id} ${v.type} · ${v.speed==null?(s.state.calibration?(v.world?'待估计':'区域外'):'未标定'):formatSpeed(v.speed)+' km/h'}`;
   ctx.font=fontSize+'px '+theme.font;
   const box=placeCanvasLabel(x1*sx,y1*sy-fontSize-6,ctx.measureText(label).width+10,fontSize+6,c,labels),lx=box.x,ly=box.y+box.height;
   if(Math.abs(ly-y1*sy)>fontSize){ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(lx+5,ly);ctx.lineTo(x1*sx,y1*sy);ctx.stroke();}
   ctx.fillStyle=theme.bg+'e8';ctx.fillRect(lx,box.y,box.width,box.height);ctx.fillStyle=color;ctx.fillText(label,lx+5,ly-4);
   if(v.status!=='NORMAL'){ctx.fillStyle=theme.danger;ctx.fillText('WARNING '+v.status,lx,Math.min(c.height-8,y2*sy+14));}
  });
  path(s.pending,theme.text);s.pending.forEach((p,i)=>{ctx.fillStyle=theme.text;ctx.beginPath();ctx.arc(p[0]*sx,p[1]*sy,5,0,Math.PI*2);ctx.fill();ctx.font='12px monospace';ctx.fillText(String(i+1),p[0]*sx+8,p[1]*sy-8);});
 };
 useLayoutEffect(()=>{draw();},[state,image,scene,calibration,pending,editing]);
 return <div className={'video-stage '+(editing?'editing':'')}>
  {image?<canvas ref={canvas} aria-label="真实视频、车辆检测与轨迹" onClick={e=>{if(!editing||!state.video||e.detail>1)return;const rect=e.currentTarget.getBoundingClientRect();onPoint([(e.clientX-rect.left)/rect.width*state.video.width,(e.clientY-rect.top)/rect.height*state.video.height]);}}/>:<div className="empty"><FileVideo size={30}/><strong>等待视频画面</strong><small>导入录制视频后，在此查看车辆检测框与运行轨迹。</small></div>}
  {state.video&&<span className="stage-tag">{editing?'点击画面绘制标定点':'录制视频'} · {state.video.width} × {state.video.height}</span>}
 </div>
}
