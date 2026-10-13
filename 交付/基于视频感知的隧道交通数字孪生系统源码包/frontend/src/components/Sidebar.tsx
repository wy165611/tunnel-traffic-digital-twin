import {useState,type MouseEvent} from 'react';
import {Activity,BarChart3,Download,FileVideo,Layers,List,LoaderCircle,PanelLeftClose,PanelLeftOpen,Pause,Play,ScanLine,Settings2,TriangleAlert} from 'lucide-react';
import BrandMark from './BrandMark';
import type {SectionId} from '../hooks/useSectionNavigation';

interface Props{
 active:SectionId;onNavigate:(id:SectionId)=>void;connected:boolean;playing:boolean;working:boolean;
 hasVideo:boolean;editing:boolean;editorSection:'road'|'settings';importing:boolean;vehicleCount:number;eventCount:number;
 onTemplates:()=>void;onImport:()=>void;onCalibration:()=>void;onSettings:()=>void;onToggleAnalysis:()=>void;
}
const destinations=[
 {id:'overview',label:'监测总览',short:'总览',icon:Activity},
 {id:'perception',label:'感知与孪生',short:'感知',icon:Layers},
 {id:'analysis',label:'交通分析',short:'分析',icon:BarChart3},
 {id:'events',label:'事件记录',short:'事件',icon:TriangleAlert},
 {id:'details',label:'车辆明细',short:'明细',icon:List},
 {id:'exports',label:'数据导出',short:'导出',icon:Download},
] as const;

export default function Sidebar(p:Props){
 const [collapsed,setCollapsed]=useState(()=>{try{return localStorage.getItem('tunnel-twin.sidebar-collapsed')==='true';}catch{return false;}});
 const toggle=()=>{setCollapsed(!collapsed);try{localStorage.setItem('tunnel-twin.sidebar-collapsed',String(!collapsed));}catch{/* Navigation remains usable when storage is unavailable. */}};
 const go=(e:MouseEvent<HTMLAnchorElement>,id:SectionId)=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();p.onNavigate(id);};
 return <nav className={'rail '+(collapsed?'compact':'')} inert={p.importing} aria-label="工作台导航">
  <div className="rail-header"><a href="#overview" className="brand-mark" aria-label="Tunnel Twin 监测首页" onClick={e=>go(e,'overview')}><BrandMark/><span className="rail-wordmark">TUNNEL<small>TWIN 工作台</small></span></a><button className="icon-button rail-toggle" title={collapsed?'展开导航':'收起导航'} aria-label={collapsed?'展开导航':'收起导航'} aria-expanded={!collapsed} aria-controls="rail-menu" onClick={toggle}>{collapsed?<PanelLeftOpen size={17}/>:<PanelLeftClose size={17}/>}</button></div>
  <div className="rail-menu" id="rail-menu"><div className="rail-group"><p className="rail-group-title">工作区</p>{destinations.map(({id,label,short,icon:Icon})=>{
   const count=id==='events'?p.eventCount:id==='details'?p.vehicleCount:0;
   return <a key={id} href={'#'+id} className={'rail-button '+(p.active===id?'active':'')} title={label} aria-label={label} aria-current={p.active===id?'location':undefined} onClick={e=>go(e,id)}><Icon size={19}/><span className="rail-label">{label}</span><span className="rail-short" aria-hidden="true">{short}</span>{count>0&&<em className={'rail-count '+(id==='events'?'alert':'')} aria-label={`${count} ${id==='events'?'条事件':'辆在场车辆'}`}>{count>99?'99+':count}</em>}</a>;
  })}</div>
  <div className="rail-group rail-tools"><p className="rail-group-title">工具</p>
   <button className="rail-button" title="视频管理" aria-label="视频管理" aria-haspopup="dialog" onClick={p.onImport} disabled={p.working}><FileVideo size={19}/><span className="rail-label">视频管理</span><span className="rail-short" aria-hidden="true">视频</span></button>
   <button className={'rail-button '+(p.editing&&p.editorSection==='road'?'selected-tool':'')} title="道路标定" aria-label="道路标定" aria-pressed={p.editing&&p.editorSection==='road'} disabled={!p.hasVideo||p.working} onClick={p.onCalibration}><ScanLine size={19}/><span className="rail-label">道路标定</span><span className="rail-short" aria-hidden="true">标定</span></button>
   <button className={'rail-button '+(p.editing&&p.editorSection==='settings'?'selected-tool':'')} title="分析参数" aria-label="分析参数" aria-pressed={p.editing&&p.editorSection==='settings'} disabled={!p.hasVideo||p.working} onClick={p.onSettings}><Settings2 size={19}/><span className="rail-label">分析参数</span><span className="rail-short" aria-hidden="true">参数</span></button>
   <button className="rail-button" title="固定机位模板" aria-label="固定机位模板" aria-haspopup="dialog" disabled={!p.hasVideo||p.working} onClick={p.onTemplates}><Layers size={19}/><span className="rail-label">固定机位模板</span><span className="rail-short" aria-hidden="true">模板</span></button>
  </div></div>
  <div className="rail-bottom"><button className={'rail-run '+(p.playing?'running':'')} aria-label={p.working?'侧栏正在加载模型':p.playing?'侧栏暂停分析':'侧栏开始分析'} title={p.editing?'先保存或关闭道路标定':p.playing?'暂停分析':'开始分析'} disabled={!p.hasVideo||p.working||p.editing} onClick={p.onToggleAnalysis}>{p.working?<LoaderCircle size={18} className="spin"/>:p.playing?<Pause size={18}/>:<Play size={18}/>}<span className="rail-label">{p.working?'加载模型…':p.playing?'暂停分析':'开始分析'}</span><span className="rail-short" aria-hidden="true">{p.working?'加载':p.playing?'暂停':'开始'}</span></button><div className="rail-connection" role="status" aria-label={p.connected?'本机感知服务已连接':'本机感知服务正在重连'}><span className={'rail-dot '+(p.connected?'online':'')}/><small>{p.connected?'本机已连接':'正在重连'}</small></div></div>
 </nav>;
}
