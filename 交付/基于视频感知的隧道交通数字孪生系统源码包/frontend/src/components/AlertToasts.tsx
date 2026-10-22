import {useEffect} from 'react';
import {BellRing,X} from 'lucide-react';
import type {TrafficEvent} from '../types';
import {eventKey} from '../utils/eventAlerts';
import {eventNames, formatTime} from '../api';

export default function AlertToasts({alerts,onDismiss}:{alerts:TrafficEvent[];onDismiss:(key:string)=>void}){
 useEffect(()=>{
  if(!alerts.length)return;
  const timers=alerts.map(event=>setTimeout(()=>onDismiss(eventKey(event)),8000));
  return()=>timers.forEach(clearTimeout);
 },[alerts]);
 return <div className="alert-toasts" role="status" aria-live="assertive" aria-label="新事件提示">
  {alerts.map(event=><div className="alert-toast" key={eventKey(event)}><BellRing size={18}/><div><strong>{event.label||eventNames[event.event]||event.event}</strong><p>车辆 #{event.vehicle_id} · {event.lane||'未划分车道'} · {formatTime(event.timestamp)}</p></div><button className="icon-button" title="关闭事件提示" onClick={()=>onDismiss(eventKey(event))}><X size={15}/></button></div>)}
 </div>;
}
