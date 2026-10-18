import {useState} from 'react';
import type {LaneRow} from '../types';
import {formatSpeed} from '../api';
import {laneSeries,laneWindowRows} from '../utils/analysisData';
import AnalysisChart from './AnalysisChart';
export default function LaneTrends({rows,configured=true,historical=false}:{rows:LaneRow[];configured?:boolean;historical?:boolean}){
 const [window,setWindow]=useState(30),[selected,setSelected]=useState('');
 const names=[...new Set(rows.map(r=>r.lane))],lane=names.includes(selected)?selected:(names[0]||'');
 const latest=new Map<string,LaneRow>();for(const row of laneWindowRows(rows,window))latest.set(row.lane,row);
 const points=laneSeries(rows,lane,window);
 return <section className="panel lane-trends"><div className="panel-title"><span>{historical?'历史车道趋势':'车道窗口与趋势'}</span><select aria-label="车道统计窗口" value={window} onChange={e=>setWindow(Number(e.target.value))}>{[10,30,60].map(t=><option key={t} value={t}>{t} 秒窗口</option>)}</select></div>
 {!configured&&<p className="hint analysis-padding">在“道路标定”绘制车道后启用分车道统计；未分配车辆单列为“未划分”。</p>}
 {!rows.length?<p className="hint analysis-padding">{historical?'此统计段未保存车道趋势（旧数据可能没有此文件）。':'开始分析后显示观测数量与窗口过线数。'}</p>:<><div className="table-scroll"><table><thead><tr><th>车道</th><th>观测 / 预测</th><th>窗口过线</th><th>覆盖</th><th>观测均速</th><th>累计过线</th></tr></thead><tbody>{[...latest.values()].map(r=><tr key={r.lane}><td>{r.lane}</td><td>{r.observed_count} / {r.predicted_count}</td><td>{r.window_flow}</td><td>{r.covered_seconds==null?'—':`${r.covered_seconds.toFixed(1)}s${r.complete?' · 完整':' · 不完整'}`}</td><td>{r.average_speed==null?'不可用':`${formatSpeed(r.average_speed)} km/h`}</td><td>{r.cumulative_flow}</td></tr>)}</tbody></table></div><label className="field analysis-padding">趋势车道<select value={lane} onChange={e=>setSelected(e.target.value)}>{names.map(n=><option key={n}>{n}</option>)}</select></label><AnalysisChart label={`${lane} 的 ${window} 秒窗口趋势；预测车辆不参与窗口流量或速度`} series={[{name:'窗口过线',data:points.map(p=>[p.timestamp,p.flow])},{name:'观测均速',speed:true,data:points.map(p=>[p.timestamp,p.speed])},{name:'观测数量',data:points.map(p=>[p.timestamp,p.observed])},{name:'预测数量',dashed:true,data:points.map(p=>[p.timestamp,p.predicted])}]}/></>}
 <p className="hint analysis-padding">窗口为 (t−窗口, t]，使用视频时间；短窗口显示实际覆盖，不外推为完整分钟。预测位置不参与速度与过线统计。时间占有率未启用。</p></section>;
}
