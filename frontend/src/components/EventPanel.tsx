import {useState} from 'react';
import EvidenceDialog from './EvidenceDialog';
import {AlertTriangle,ClipboardCheck} from 'lucide-react';
import type {TrafficEvent} from '../types';
import {formatTime} from '../api';
export default function EventPanel({events,calibrated}:{events:TrafficEvent[];calibrated:boolean}){
 const [selected,setSelected]=useState<TrafficEvent|null>(null);
 return <section id="events" className="panel events-panel" tabIndex={-1} aria-labelledby="events-title"><div className="panel-title"><span id="events-title">事件记录 <em>{events.length}</em></span><small>轨迹规则报警</small></div><div className="event-list">{events.length?events.map((e,i)=><div className="event" key={`${e.timestamp}-${e.vehicle_id}-${i}`}><AlertTriangle size={16}/><div><strong>{e.label}</strong><p>车辆 #{e.vehicle_id} · {e.lane||'未划分车道'}</p></div><time>{formatTime(e.timestamp)}</time>{e.event_id&&e.run_id?<button className="text-button" onClick={()=>setSelected(e)}>证据 / 复核</button>:<small className="hint">证据不可用</small>}</div>):<div className="empty-event"><ClipboardCheck size={28}/><span>{calibrated?'暂无已触发异常事件':'完成标定后启用异常规则'}</span><small>报警来自视频时间与轨迹规则</small></div>}</div>{selected?.event_id&&selected.run_id&&<EvidenceDialog runId={selected.run_id} eventId={selected.event_id} onClose={()=>setSelected(null)}/>}</section>
}
