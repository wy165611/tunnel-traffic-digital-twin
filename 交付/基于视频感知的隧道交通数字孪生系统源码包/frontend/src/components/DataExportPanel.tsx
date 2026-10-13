import {useEffect, useState} from 'react';
import {Download,FileSpreadsheet,ListChecks,Play,Upload,History,RefreshCw} from 'lucide-react';
import type {Snapshot, RunSummary} from '../types';
import {api,formatTime} from '../api';
import ReportDialog from './ReportDialog';
import AnnotationDialog from './AnnotationDialog';

export default function DataExportPanel({state,canStart,onStart,onImport}:{state:Snapshot;canStart:boolean;onStart:()=>void;onImport:()=>void}){
 const [reportId,setReportId]=useState<string|null>(null),[annotationId,setAnnotationId]=useState<string|null>(null);
 const files=[{kind:'vehicles',name:'车辆数据 CSV',description:'逐帧车辆 ID、位置、类型与速度',icon:FileSpreadsheet},{kind:'traffic_statistics',name:'交通统计 CSV',description:'过线流量、车辆数量与流率估计',icon:Download},{kind:'events',name:'事件记录 CSV',description:'报警时间、车辆 ID 与事件类型',icon:ListChecks},{kind:'lane_statistics',name:'车道趋势 CSV',description:'10 / 30 / 60 秒窗口与观测样本',icon:FileSpreadsheet}];
 const [expanded,setExpanded]=useState(false),[page,setPage]=useState(0),[refresh,setRefresh]=useState(0),[runs,setRuns]=useState<RunSummary[]>([]),[total,setTotal]=useState(0),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const ended=state.status==='ended';
 useEffect(()=>{
  if(!expanded)return;
  let active=true;setLoading(true);setError('');
  api<{items:RunSummary[];total:number}>(`/runs/details?limit=10&offset=${page*10}`).then(result=>{if(active){setRuns(result.items);setTotal(result.total);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
 },[expanded,page,refresh,state.run_id,ended]);
 return <section id="exports" className="workspace-section" tabIndex={-1} aria-labelledby="exports-title">
  <div className="section-heading"><div><span className="section-index">04</span><h2 id="exports-title">数据导出</h2></div><p>当前统计段 · 本地 CSV</p></div>
  <div className="panel export-panel"><div className="export-summary"><div><strong>{state.run_id?'下载当前分析数据':'开始分析后即可导出数据'}</strong><p>{state.run_id?`统计段起点 ${formatTime(state.segment_start)} · 视频时间 ${formatTime(state.timestamp)}${state.status==='playing'?' · 下载时生成完整快照':''}`:'选择视频并开始分析，车辆、交通统计和事件记录会自动保存。'}</p></div>{!state.run_id&&(state.video?<button className="button" disabled={!canStart} onClick={onStart}><Play size={14}/>开始分析并生成数据</button>:<button className="button" onClick={onImport}><Upload size={14}/>导入视频</button>)}</div>
   {state.run_id&&<div className="report-actions"><button className="button" onClick={()=>setReportId(state.run_id!)}>阅读当前分析报告 / 对照</button><button className="button" onClick={()=>setAnnotationId(state.run_id!)}>人工过线 / 事件评测</button></div>}
   <div className="export-files">{files.map(({kind,name,description,icon:Icon})=>state.run_id?<a className="export-file" key={kind} href={`/api/export/${state.run_id}/${kind}`} download><Icon size={20}/><div><strong>{name}</strong><small>{description}</small></div><Download size={14} className="export-download"/></a>:<div className="export-file unavailable" key={kind} aria-disabled="true"><Icon size={20}/><div><strong>{name}</strong><small>等待分析数据</small></div></div>)}</div>
   {state.run_id&&<p className="export-note">分析中下载使用当时的完整 CSV 快照。没有事件时保留表头，未标定的真实速度与世界坐标保持空值。</p>}
   <button className="button run-history-toggle" aria-expanded={expanded} aria-controls="run-history" onClick={()=>setExpanded(!expanded)}><History size={15}/>{expanded?'收起历史统计段':'查看历史统计段'}</button>
   {expanded&&<div id="run-history" className="run-history"><div className="export-summary"><strong>历史分析 · {total} 段</strong><button className="text-button" disabled={loading} onClick={()=>setRefresh(refresh+1)}><RefreshCw size={13}/>刷新</button></div>{error&&<p role="alert" className="danger">{error}</p>}{loading&&<p role="status" className="hint">正在读取历史记录…</p>}{!loading&&!error&&!runs.length&&<p className="hint">还没有已保存的分析段。</p>}{runs.map(run=><article className="run-row" key={run.run_id}><div><strong>{run.video_id||'旧统计段 · 未记录视频来源'}</strong><p>{run.created_at?new Date(run.created_at).toLocaleString('zh-CN'):run.run_id} · {run.segment_start==null?'起点未记录':formatTime(run.segment_start)}{run.end_timestamp!=null?` → ${formatTime(run.end_timestamp)}`:''} · {run.run_id===state.run_id?'当前统计段':run.status==='completed'?'分析完成':'已保存'}</p></div><div className="run-links"><button className="text-button" onClick={()=>setReportId(run.run_id)}>阅读报告 / 对照</button><button className="text-button" onClick={()=>setAnnotationId(run.run_id)}>人工评测</button>{files.map(file=>file.kind==='lane_statistics'&&!run.available?.lane_statistics?<span key={file.kind} className="hint">未保存车道趋势</span>:<a key={file.kind} href={`/api/export/${run.run_id}/${file.kind}`} download>{file.name}<Download size={12}/></a>)}</div></article>)}<div className="button-row"><button className="button" disabled={loading||page===0} onClick={()=>setPage(page-1)}>上一页</button><span className="hint">第 {page+1} 页</span><button className="button" disabled={loading||(page+1)*10>=total} onClick={()=>setPage(page+1)}>下一页</button></div></div>}
  </div>
 {annotationId&&<AnnotationDialog runId={annotationId} onClose={()=>setAnnotationId(null)}/>}
 {reportId&&<ReportDialog runId={reportId} onClose={()=>setReportId(null)}/>}
 </section>;
}
