import {useEffect,useRef,useState} from 'react';
import {Check,CornerUpLeft,MousePointer2,Trash2} from 'lucide-react';
import type {Scene,Calibration,Point,Settings} from '../types';
import {calibrationDimensions,calibrationEdgeLengths,resolveTravelEdge,travelEdgeLabel,travelSourceLabel} from '../utils/calibrationGeometry';
import BirdseyePreview from './BirdseyePreview';

export type DrawMode='calibration'|'counting'|'lane'|null;
interface Props{scene:Scene;setScene:(s:Scene)=>void;calibration:Calibration|null;setCalibration:(c:Calibration|null)=>void;mode:DrawMode;setMode:(m:DrawMode)=>void;pending:Point[];setPending:(p:Point[])=>void;finish:()=>void;onSave:()=>void;onClose:()=>void;focusTarget:{section:'road'|'settings';request:number};suggestedCountingLine:Point[]|null;settings:Settings;onSettings:(s:Settings)=>void;busy:boolean;roadDirty:boolean}

function CornerOrderDiagram(){
 return <svg className="corner-diagram" viewBox="0 0 220 120" role="img" aria-label="角点顺序：P1 左上、P2 右上、P3 右下、P4 左下">
  <polygon points="18,18 202,30 186,104 30,94" className="corner-shape"/>
  <path d="M 18 18 L 202 30" className="corner-edge strong"/><path d="M 202 30 L 186 104" className="corner-edge"/>
  <path d="M 186 104 L 30 94" className="corner-edge"/><path d="M 30 94 L 18 18" className="corner-edge"/>
  {[['P1',18,18],['P2',202,30],['P3',186,104],['P4',30,94]].map(([name,x,y])=><g key={String(name)}>
   <circle cx={Number(x)} cy={Number(y)} r="4.5"/><text x={Number(x)+(String(name)==='P1'||String(name)==='P4'?-24:7)} y={Number(y)+(String(name)==='P1'||String(name)==='P2'?-8:15)}>{name}</text>
  </g>)}
  <text x="110" y="13" className="corner-label">边 1→2 · 上边缘 / 通常为道路宽度</text>
  <text x="196" y="72" className="corner-label" transform="rotate(90 196 72)">边 2→3 · 右边缘 / 通常沿行车方向</text>
 </svg>;
}

export default function CalibrationPanel(p:Props){
 const [settings,setSettings]=useState(p.settings);
 const [step,setStep]=useState<1|2|3>(1);
 const settingsDirty=JSON.stringify(settings)!==JSON.stringify(p.settings);
 const panel=useRef<HTMLElement>(null);
 useEffect(()=>{if(p.focusTarget.section==='road')setStep(1);},[p.focusTarget.section,p.focusTarget.request]);
 useEffect(()=>{const frame=requestAnimationFrame(()=>{const target=panel.current?.querySelector<HTMLElement>(p.focusTarget.section==='settings'?'#analysis-settings':'#road-calibration');target?.focus({preventScroll:true});target?.scrollIntoView({block:p.focusTarget.section==='settings'?'start':'nearest',behavior:'instant'});});return()=>cancelAnimationFrame(frame);},[p.focusTarget.section,p.focusTarget.request,step]);
 const number=(name:keyof Settings,label:string,min:number,max:number,step:number,disabled=false)=> <label className="field" key={name}>{label}<input type="number" value={settings[name] as number} min={min} max={max} step={step} disabled={disabled} onChange={e=>setSettings({...settings,[name]:Number(e.target.value)})}/></label>;
 const toggle=(name:keyof Settings,label:string,disabled=false)=> <label className="check-field" key={name}><input type="checkbox" checked={disabled?false:settings[name] as boolean} disabled={disabled} onChange={e=>setSettings({...settings,[name]:e.target.checked})}/><span>{label}</span></label>;
 const begin=(mode:DrawMode)=>{p.setPending([]);p.setMode(mode);};
 const edges=p.calibration?calibrationEdgeLengths(p.calibration):null;
 const detection=p.calibration&&edges&&edges.edge12>=.1&&edges.edge23>=.1?resolveTravelEdge(p.calibration,p.scene):null;
 const dimensions=p.calibration&&detection?calibrationDimensions(p.calibration,p.scene):null;
 const manual=p.calibration?.travel_edge_mode==='manual';
 const calibrated=!!p.calibration;
 const edgesComplete=!!edges&&edges.edge12>=.1&&edges.edge23>=.1;
 const setEdge=(edge:'1-2'|'2-3',value:number)=>{if(!p.calibration||!edges)return;p.setCalibration({...p.calibration,edge_1_2_m:edge==='1-2'?value:edges.edge12,edge_2_3_m:edge==='2-3'?value:edges.edge23});};
 const meters=(value:number)=>Number.isFinite(value)&&value>0?value.toFixed(1):'—';
 const steps=[['1','选择角点'],['2','实测边长'],['3','鸟瞰确认']] as const;
 return <aside ref={panel} className="calibration-panel panel"><div className="panel-title"><span>道路标定与规则</span><button disabled={p.busy} onClick={p.onClose} className="text-button">{p.roadDirty||settingsDirty?'关闭并放弃未保存更改':'关闭'}</button></div><div className="calibration-body"><fieldset disabled={p.busy} className="editor-fields">
  <div className="instruction"><MousePointer2 size={18}/><span>暂停画面后绘制。坐标自动换算为原视频像素，标定与车道按视频保存。</span></div>
  <div className="wizard-steps" role="tablist" aria-label="标定向导步骤">{steps.map(([index,label])=><button key={index} role="tab" aria-selected={step===Number(index)} className={step===Number(index)?'wizard-step active':'wizard-step'} onClick={()=>setStep(Number(index) as 1|2|3)} disabled={Number(index)>1&&!p.calibration?.points}>{index} / {label}</button>)}</div>
  {step===1&&<>
   <h4 id="road-calibration" tabIndex={-1}>01 / 选择 4 个道路角点</h4>
   <p className="hint">按画面坐标顺时针依次点击：<strong>P1 左上 → P2 右上 → P3 右下 → P4 左下</strong>。P1→P2 是上边缘（通常横跨道路宽度），P2→P3 是右边缘（通常沿行车方向）。顺序错误或自交会在保存时被拒绝。</p>
   <CornerOrderDiagram/>
   <button className={p.mode==='calibration'?'button primary':'button'} onClick={()=>begin('calibration')}>绘制 4 个标定点 {p.mode==='calibration'?`(${p.pending.length}/4)`:''}</button>
   <p className="hint">{p.calibration?.points?'已记录 4 个角点。':'尚未记录角点；点击画面依次落下 P1–P4。'}</p>
   <button className="button full" disabled={!p.calibration?.points} onClick={()=>setStep(2)}>下一步：填写两条实测边 →</button>
  </>}
  {step===2&&<>
   <h4>02 / 填写两条边的实测长度</h4>
   <p className="hint">填米，不是像素。边 1→2 = P1 到 P2 的实际距离，通常为画面中道路的上边缘（横跨道路）；边 2→3 = P2 到 P3 的实际距离，通常为画面中道路的右边缘（沿行车方向）。</p>
   {p.calibration?<div className="field-grid"><label className="field">边 1→2 实测长度 / m（P1→P2）<input type="number" min="0.1" step="0.1" value={edges?.edge12||''} placeholder="上边缘实际距离" onChange={e=>setEdge('1-2',Number(e.target.value))}/></label><label className="field">边 2→3 实测长度 / m（P2→P3）<input type="number" min="0.1" step="0.1" value={edges?.edge23||''} placeholder="右边缘实际距离" onChange={e=>setEdge('2-3',Number(e.target.value))}/></label></div>:<p className="hint">请先在步骤 01 完成角点绘制。</p>}
   <p className="hint">系统把较长的一对边识别为沿行车方向；两条边接近相等时参考车道/计数线走向。自动结果不符合实际时可手动交换。世界坐标 +Y 始终沿行车方向。</p>
   {detection&&dimensions?<div className="travel-detection"><p role="status">沿行车方向：<strong>{travelEdgeLabel(detection.edge)}</strong>（{manual?'手动指定':`自动检测 · ${travelSourceLabel(detection.source)}`}）</p><p className="hint">道路宽 {meters(dimensions.width)} m · 沿路长 {meters(dimensions.length)} m。</p><div className="button-row">{manual?<button className="text-button" onClick={()=>p.setCalibration({...p.calibration!,travel_edge_mode:'auto',travel_edge:undefined,travel_edge_source:undefined})}>恢复自动检测</button>:<button className="text-button" disabled={!p.calibration} onClick={()=>p.calibration&&p.setCalibration({...p.calibration,travel_edge:detection.edge==='1-2'?'2-3':'1-2',travel_edge_mode:'manual',travel_edge_source:'manual'})}>交换为{travelEdgeLabel(detection.edge==='1-2'?'2-3':'1-2')}</button>}</div></div>:<p className="hint">填写两条边的实测长度后自动判断行车方向。</p>}
   <div className="button-row"><button className="button" onClick={()=>setStep(1)}>← 上一步</button><button className="button primary" disabled={!edgesComplete} onClick={()=>setStep(3)}>下一步：鸟瞰预览 →</button></div>
   <button className="text-button danger" onClick={()=>p.setCalibration(null)}>清除尺度标定</button>
  </>}
  {step===3&&<>
   <h4>03 / 鸟瞰预览确认</h4>
   <p className="hint">下面按填写的实测尺度把画面还原为道路俯视图。确认车道、计数线与行车方向的位置正确后再保存。</p>
   <BirdseyePreview calibration={p.calibration} scene={p.scene}/>
   <div className="button-row"><button className="button" onClick={()=>setStep(2)}>← 上一步</button><button className="button primary" disabled={p.busy||p.mode!==null||!p.calibration} onClick={p.onSave}><Check size={15}/>保存道路配置</button></div>
   <p className="hint">保存仅提交道路草稿；应用分析参数只提交参数。面板保持打开，另一组未保存内容会保留。每次提交重建统计段，旧 CSV 会保留。</p>
  </>}
  <h4>04 / 流量计数线</h4><p className="hint">导入后按画面宽高自动生成：横屏放竖线，竖屏放横线，方形画面默认放横线。双向车辆穿线均计数，同一 ID 仅计一次。道路走向与画面方向不同或镜头倾斜时，请手动调整。</p><p className="hint">当前：{p.scene.counting_line?(p.scene.counting_line_mode==='auto'?'自动计数线':'手动计数线'):'过线计数已关闭'}</p><div className="button-row"><button className={p.mode==='counting'?'button primary':'button'} onClick={()=>begin('counting')}>绘制计数线</button><button className="icon-button" title="清除计数线" onClick={()=>{p.setScene({...p.scene,counting_line:null,counting_line_mode:'disabled'});if(p.mode==='counting'){p.setMode(null);p.setPending([]);}}}><Trash2 size={15}/></button></div><button className="button full" disabled={!p.suggestedCountingLine} onClick={()=>{p.setScene({...p.scene,counting_line:p.suggestedCountingLine,counting_line_mode:'auto'});p.setMode(null);p.setPending([]);}}>恢复自动计数线</button>
  <h4>05 / 车道及合法方向</h4><p className="hint">依次点击车道边界角点，至少 3 点，再点击“完成多边形”。双向道路需要分别设置方向；标定后 +Y / −Y 始终沿自动检测的行车轴。勾选“实线”表示该车道禁止变道，会写入摄像头模板并按机位生效。</p><label className="field">本机位限速 / km/h（留空沿用分析参数超速阈值）<input type="number" min="5" max="200" step="1" value={p.scene.speed_limit_kmh??''} onChange={e=>p.setScene({...p.scene,speed_limit_kmh:e.target.value===''?null:Number(e.target.value)})}/></label><div className="button-row"><button className={p.mode==='lane'?'button primary':'button'} onClick={()=>begin('lane')}>绘制新车道</button>{p.mode==='lane'&&<button className="button" disabled={p.pending.length<3} onClick={p.finish}><Check size={14}/>完成</button>}</div>
  {p.scene.lanes.map((lane,i)=><div className="lane-editor" key={i}><input aria-label="车道名称" value={lane.name} onChange={e=>p.setScene({...p.scene,lanes:p.scene.lanes.map((l,j)=>j===i?{...l,name:e.target.value}:l)})}/><label className="lane-solid"><input type="checkbox" checked={lane.solid_line!==false} onChange={e=>p.setScene({...p.scene,lanes:p.scene.lanes.map((l,j)=>j===i?{...l,solid_line:e.target.checked}:l)})}/>实线</label><select aria-label={`${lane.name}方向`} value={lane.direction[1]===0?(lane.direction[0]>0?'right':'left'):(lane.direction[1]>0?'down':'up')} onChange={e=>{const dir:Record<string,Point>={up:[0,-1],down:[0,1],left:[-1,0],right:[1,0]};p.setScene({...p.scene,lanes:p.scene.lanes.map((l,j)=>j===i?{...l,direction:dir[e.target.value]}:l)});}}><option value="down">↓ +Y</option><option value="up">↑ −Y</option><option value="right">→ +X</option><option value="left">← −X</option></select><button className="icon-button" title="删除车道" onClick={()=>p.setScene({...p.scene,lanes:p.scene.lanes.filter((_,j)=>i!==j)})}><Trash2 size={13}/></button></div>)}
  {p.pending.length>0&&<button className="text-button" onClick={()=>p.setPending(p.pending.slice(0,-1))}><CornerUpLeft size={13}/>撤回最后一点</button>}
  <h4 id="analysis-settings" tabIndex={-1}>06 / 分析参数</h4>{!calibrated&&<div className="calibration-gate" role="status"><strong>未完成道路尺度标定</strong><p>测速（超速 / 低速）、跟车时距、排队米数、密度与服务水平作为一组停用，不会生成虚构数值。完成步骤 01–03 并保存后自动启用；闯入与变道报警不依赖尺度标定。</p></div>}
  <label className="field">预训练模型<select value={settings.model} onChange={e=>setSettings({...settings,model:e.target.value})}><option value="visdrone_yolo11n">航拍车辆 · VisDrone YOLO11n</option><option value="coco_yolo11n">通用道路 · COCO YOLO11n</option><option value="ssdlite320_mobilenet_v3_large">COCO SSD MobileNetV3</option></select></label><div className="field-grid">{number('confidence','检测置信度',.1,.95,.05)}{number('detection_interval','检测间隔 / 帧',1,10,1)}{number('smoothing_frames','速度平滑 / 检测点',5,30,1)}{number('stop_speed','停车阈值 / km/h',0,20,.5)}{number('stop_seconds','停车持续 / s',.5,60,.5)}{number('hard_braking_acceleration','急减速 / m/s²',-20,-.5,.5)}{number('wrong_way_seconds','逆行持续 / s',.5,30,.5)}{number('speeding_kmh','超速阈值 / km/h',1,300,1,!calibrated)}{number('slow_speed_kmh','低速阈值 / km/h',1,200,1,!calibrated)}{number('lane_change_seconds','违规变道确认 / s',.5,30,.5)}{number('tailgating_headway_seconds','跟车时距阈值 / s',.2,10,.1,!calibrated)}{number('queue_speed_kmh','排队速度阈值 / km/h',0,50,1,!calibrated)}{number('low_light_clahe_clip','低照度 CLAHE 对比度',1,10,.1)}{number('low_light_gamma','低照度 Gamma（>1 提亮）',.5,3,.1)}</div>
  <div className="settings-toggles">{toggle('speeding_enabled','启用超速报警（需速度标定）',!calibrated)}{toggle('slow_speed_enabled','启用低速报警（需速度标定）',!calibrated)}{toggle('lane_change_enabled','启用违规变道报警（实线禁变道）')}{toggle('tailgating_enabled','启用跟车过近报警（需速度标定）',!calibrated)}{toggle('intrusion_enabled','启用行人 / 非机动车闯入报警')}{toggle('occupancy_enabled','启用虚拟线圈时间占有率（每车道自动生成）')}{toggle('low_light_enabled','启用隧道低照度增强（CLAHE + Gamma，默认关闭）')}</div>
  <p className="hint">未完成道路尺度标定时，超速、低速、跟车过近、排队米数与密度/服务水平保持静默，不生成虚构速度。{settings.intrusion_supported?'当前模型支持 person / bicycle 类别。':'当前模型不支持 person / bicycle 类别，闯入报警不会触发。'}低照度增强会提高处理耗时，关闭后恢复原始帧。</p>
  <label className="field">未划分车道的合法方向<select value={settings.legal_direction[1]>0?'down':settings.legal_direction[1]<0?'up':settings.legal_direction[0]>0?'right':'left'} onChange={e=>{const d:Record<string,Point>={up:[0,-1],down:[0,1],left:[-1,0],right:[1,0]};setSettings({...settings,legal_direction:d[e.target.value]});}}><option value="down">{p.calibration?'↓ +Y · 行车轴正向':'↓ +Y'}</option><option value="up">{p.calibration?'↑ −Y · 行车轴反向':'↑ −Y'}</option><option value="right">→ +X</option><option value="left">← −X</option></select></label><p className="hint">标定后 +Y / −Y 为自动检测的行车轴，选择实际允许的正反方向；+X / −X 为横穿道路方向。默认合法方向为规范化单位向量，并随检测到的行车轴保持一致。</p>
  <button className="button full" disabled={p.busy} onClick={()=>p.onSettings(settings)}>应用分析参数{settingsDirty?' · 未保存':''}</button>
 </fieldset></div></aside>;
}
