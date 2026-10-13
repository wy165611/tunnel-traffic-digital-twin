import {Car,Route,Gauge,AlertTriangle} from 'lucide-react';
import type {Metrics} from '../types';
import {formatSpeed} from '../api';
export default function Dashboard({metrics,calibrated,counting}:{metrics:Metrics|null|undefined;calibrated:boolean;counting:boolean}){
 const stats=[{label:'当前车辆',value:metrics?.vehicle_count??0,unit:'辆',detail:`累计识别 ${metrics?.total_vehicles??0} 辆`,icon:Car,color:'mint'},{label:'累计过线流量',value:counting?(metrics?.total_flow??0):'—',unit:'辆',detail:counting?`${(metrics?.flow_per_min??0).toFixed(1)} 辆/分钟${metrics?.flow_estimated?' · 估计':''}`:'请绘制虚拟计数线',icon:Route,color:'neutral'},{label:'平均速度',value:formatSpeed(metrics?.average_speed),unit:calibrated?'km/h':'',detail:calibrated?`范围 ${formatSpeed(metrics?.min_speed)} – ${formatSpeed(metrics?.max_speed)}`:'未标定 · 不显示真实车速',icon:Gauge,color:'neutral'},{label:'异常事件',value:metrics?.event_count??0,unit:'次',detail:calibrated?'停车 / 急减速 / 逆行':'等待道路尺度标定',icon:AlertTriangle,color:(metrics?.event_count??0)>0?'rose':'neutral'}];
 return <section className="dashboard" aria-label="交通核心指标">{stats.map(({label,value,unit,detail,icon:Icon,color})=><div className="stat-card" key={label}><div className="stat-top"><span>{label}</span><Icon size={18} className={color}/></div><div className="stat-value">{value}<small>{unit}</small></div><p>{detail}</p></div>)}</section>
}
