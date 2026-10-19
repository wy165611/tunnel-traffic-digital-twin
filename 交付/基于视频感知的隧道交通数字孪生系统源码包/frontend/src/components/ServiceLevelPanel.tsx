import type {Metrics} from '../types';
import {formatSpeed} from '../api';

export default function ServiceLevelPanel({metrics,calibrated,enabled}:{metrics:Metrics|null|undefined;calibrated:boolean;enabled:boolean}){
 const lanes=metrics?.lanes||[];
 return <section className="panel service-level-panel" aria-labelledby="service-level-title">
  <div className="panel-title"><span id="service-level-title">虚拟线圈与服务水平</span><small>{enabled?'时间占有率已启用':'时间占有率未启用'} · 服务水平 <b>{metrics?.level_of_service||'—'}</b>{metrics?.service_level_label?` ${metrics.service_level_label}`:''}</small></div>
  {!lanes.length?<p className="hint analysis-padding">绘制车道后，每车道会自动生成虚拟线圈；未标定时仅显示图像估计的排队车辆数。</p>:<div className="table-scroll"><table><thead><tr><th>车道</th><th>时间占有率</th><th>流量 / 辆每小时</th><th>密度 / 辆每公里每车道</th><th>观测均速</th><th>排队</th><th>拥堵</th><th>服务水平</th></tr></thead><tbody>{lanes.map(lane=><tr key={lane.name}><td>{lane.name}</td><td>{lane.occupancy==null?'—':`${lane.occupancy.toFixed(1)}%`}</td><td>{lane.flow_per_hour==null?'—':lane.flow_per_hour.toFixed(0)}</td><td>{lane.density==null?'未标定':lane.density.toFixed(1)}</td><td>{lane.average_speed==null?'未标定':`${formatSpeed(lane.average_speed)} km/h`}</td><td>{lane.queue_vehicles==null?'—':`${lane.queue_vehicles} 辆${lane.queue_estimated?'（图像估计）':''}`}{lane.queue_length_m!=null?` / ${lane.queue_length_m.toFixed(1)} m`:''}</td><td>{lane.congestion_label||'—'}</td><td>{lane.level_of_service||'未标定'}{lane.service_level_label?` · ${lane.service_level_label}`:''}</td></tr>)}</tbody></table></div>}
  <p className="hint analysis-padding">时间占有率为虚拟线圈被车辆覆盖的累计视频时间比例；服务水平按密度 A–F 分级并结合观测速度降级。{calibrated?'':'当前未完成道路尺度标定：密度、服务水平与排队长度不可用，排队车辆数为图像速度估计，不代表真实速度。'}</p>
 </section>;
}
