import type {AnnotationContext,AnnotationDocument,ManualEvent,Scene} from '../types';
export function containRect(sourceWidth:number,sourceHeight:number,width:number,height:number){
 if(![sourceWidth,sourceHeight,width,height].every(v=>Number.isFinite(v)&&v>0))return {x:0,y:0,width:0,height:0,scale:0};
 const scale=Math.min(width/sourceWidth,height/sourceHeight);
 return {x:(width-sourceWidth*scale)/2,y:(height-sourceHeight*scale)/2,width:sourceWidth*scale,height:sourceHeight*scale,scale};
}
export function parseSeconds(value:number|string,label='时间'){if(!['number','string'].includes(typeof value))throw new Error(`${label}须为数字`);if(typeof value==='string'&&!value.trim())throw new Error(`${label}不能为空`);const n=Number(value);if(!Number.isFinite(n)||n<0)throw new Error(`${label}须为有限非负秒数`);return n;}
export function parseVehicleId(value:number|string|null){if(value===null||value==='')return null;if(!['number','string'].includes(typeof value))throw new Error('系统车辆ID须为数字');const n=Number(value);if(!Number.isSafeInteger(n)||n<=0)throw new Error('系统车辆 ID 须为正整数，未映射可留空');return n;}
export function changeAnnotation(document:AnnotationDocument,changes:Partial<AnnotationDocument>):AnnotationDocument{return {...document,...changes,verified:false,completeness_confirmed:false};}
export function validateAnnotation(document:AnnotationDocument,context:AnnotationContext):AnnotationDocument{
 const keys=['schema_version','run_id','video_identity','run_fingerprint','dimensions','source_video','interval','annotator','note','revision','created_at','updated_at','crossings','events','speeds','speed_state','reviewed_sections','verified','completeness_confirmed'];
 if(Object.keys(document).some(k=>!keys.includes(k)))throw new Error('人工文档包含未知字段');
 if(!Number.isSafeInteger(document.revision)||document.revision<0||typeof document.verified!=='boolean'||typeof document.completeness_confirmed!=='boolean')throw new Error('文档版本与核验声明类型无效');
 for(const date of [document.created_at,document.updated_at])if(date!==null&&(typeof date!=='string'||date.length>50))throw new Error('记录时间字段无效');
 if(!Array.isArray(document.dimensions)||document.dimensions.length!==2||!document.dimensions.every(v=>Number.isSafeInteger(v)&&v>0))throw new Error('记录尺寸无效');
 if(document.source_video!=null){const video=document.source_video,allowed=['width','height','fps','frames','duration','orientation','display_width','display_height','duration_estimated','live','timing_source'];if(typeof video!=='object'||Array.isArray(video)||Object.keys(video).some(k=>!allowed.includes(k)))throw new Error('来源视频事实结构无效');for(const key of ['width','height','fps'])if(typeof video[key]!=='number'||!Number.isFinite(video[key])||Number(video[key])<=0)throw new Error('来源视频事实数值无效');for(const key of ['width','height','frames','display_width','display_height'])if(video[key]!=null&&(!Number.isSafeInteger(video[key])||Number(video[key])<(key==='frames'?0:1)))throw new Error('来源尺寸或帧数无效');for(const key of ['duration'])if(video[key]!=null&&(typeof video[key]!=='number'||!Number.isFinite(video[key])||Number(video[key])<0))throw new Error('来源时长无效');if(video.width!==document.dimensions[0]||video.height!==document.dimensions[1])throw new Error('来源事实与文档尺寸不一致');for(const key of ['duration_estimated','live'])if(video[key]!=null&&typeof video[key]!=='boolean')throw new Error('来源布尔事实无效');if(video.orientation!=null&&!['landscape','portrait','square'].includes(String(video.orientation)))throw new Error('来源方向无效');if(video.timing_source!=null&&video.timing_source!=='decoder_pts')throw new Error('来源时间依据无效');}
 if(!context.available)throw new Error('此统计段缺少标注所需元数据');
 for(const key of ['run_id','video_identity','run_fingerprint','dimensions'] as const)if(JSON.stringify(document[key])!==JSON.stringify(context[key]))throw new Error(`${key} 与当前统计段不一致`);
 if(document.schema_version!==2||document.speed_state!=='unreviewed'||!Array.isArray(document.speeds)||document.speeds.length)throw new Error('只支持速度未核验的 schema2 文档');
 if(!Array.isArray(document.interval)||document.interval.length!==2)throw new Error('核验区间须有起止时间');
 const start=parseSeconds(document.interval[0],'区间起点'),end=parseSeconds(document.interval[1],'区间终点');
 if(end<=start||!context.interval||start<context.interval[0]||end>context.interval[1])throw new Error('核验区间须完整位于导出范围，终点晚于起点');
 if(typeof document.annotator!=='string'||document.annotator.length>100||typeof document.note!=='string'||document.note.length>1000)throw new Error('姓名最多100字，备注最多1000字');
 if(!Array.isArray(document.reviewed_sections)||new Set(document.reviewed_sections).size!==document.reviewed_sections.length||document.reviewed_sections.some(s=>!['crossings','events'].includes(s)))throw new Error('完整核验类别只能为过线或事件');
 const crossing=(row:{timestamp:number|string;physical_vehicle_note:string},event=false)=>{if(!row||typeof row!=='object'||Object.keys(row).some(key=>!(event?['timestamp','physical_vehicle_note','event','vehicle_id']:['timestamp','physical_vehicle_note']).includes(key)))throw new Error('人工条目包含未知字段');const t=parseSeconds(row.timestamp);if(t<start||t>end)throw new Error('人工条目超出核验区间');if(typeof row.physical_vehicle_note!=='string'||row.physical_vehicle_note.length>200)throw new Error('物理车辆说明最多200字');return {timestamp:t,physical_vehicle_note:row.physical_vehicle_note};};
 if(!Array.isArray(document.crossings)||!Array.isArray(document.events)||document.crossings.length>1000||document.events.length>1000)throw new Error('每类最多1000条，不会截断');
 const crossings=document.crossings.map(row=>crossing(row)),events=document.events.map((row:ManualEvent)=>{const value=crossing(row,true),id=parseVehicleId(row.vehicle_id);if(!['ABNORMAL STOP','HARD BRAKING','WRONG WAY'].includes(row.event))throw new Error('事件类型无效');if(id===null&&!value.physical_vehicle_note.trim())throw new Error('未映射系统 ID 时须填写物理车辆说明，计入漏报');return {...value,event:row.event,vehicle_id:id};});
 if(document.verified&&(!document.annotator.trim()||!document.reviewed_sections.length||!document.completeness_confirmed))throw new Error('核验需要姓名、完整类别与明确完整性声明');
 return {...document,interval:[start,end],crossings,events};
}
export function importAnnotation(text:string,context:AnnotationContext,revision:number){let value:AnnotationDocument;try{value=JSON.parse(text);}catch{throw new Error('JSON无法解析');}if(!value||typeof value!=='object')throw new Error('JSON文档无效');const valid=validateAnnotation(value,context);return {...valid,revision,verified:false,completeness_confirmed:false};}
export const eventLabels:Record<ManualEvent['event'],string>={'ABNORMAL STOP':'异常停车','HARD BRAKING':'急减速','WRONG WAY':'逆行'};
export function categoryValue(available:boolean,value:number|null,percentage=false){return !available?'未评测':value==null?'不可定义':percentage?`${(value*100).toFixed(1)}%`:String(value);}
export function sceneLabelPoint(points:Scene['lanes'][number]['points']){return points.reduce((p,next)=>[p[0]+next[0]/points.length,p[1]+next[1]/points.length],[0,0]);}

export class PausedSampleGate {
 private version=0;private seconds=0;private paused=true;
 update(seconds:number,paused:boolean){const changed=Math.abs(seconds-this.seconds)>.000001||paused!==this.paused;this.seconds=seconds;this.paused=paused;if(changed)this.version++;return changed;}
 next(){return ++this.version;}
 current(version:number){return this.version===version&&this.paused;}
 cancel(){this.version++;}
}

// Handlers preserve decoder PTS; rounding is only a display concern.
export function recordCrossing(document:AnnotationDocument,context:AnnotationContext,time:number,note:string){
 const next=changeAnnotation(document,{crossings:[...document.crossings,{timestamp:parseSeconds(time),physical_vehicle_note:note}]});validateAnnotation(next,context);return next;
}
export function recordEvent(document:AnnotationDocument,context:AnnotationContext,time:number,event:ManualEvent['event'],vehicleId:string,physicalNote:string){
 const next=changeAnnotation(document,{events:[...document.events,{timestamp:parseSeconds(time),event,vehicle_id:vehicleId||null,physical_vehicle_note:physicalNote}]});validateAnnotation(next,context);return next;
}
interface VersionGate {current(token:number):boolean}
export async function readAnnotationImport(file:Pick<File,'size'|'text'>,context:AnnotationContext,revision:number,gate:VersionGate,token:number){
 if(file.size>1024*1024)throw new Error('人工 JSON 最大1MB');
 const text=await file.text();if(!gate.current(token))return null;
 return importAnnotation(text,context,revision);
}
export interface DraftInputs {crossNote:string;eventType:ManualEvent['event'];vehicleId:string;physicalNote:string}
export interface LocalAnnotationDraft {document:AnnotationDocument;inputs:DraftInputs;saved_at:string}
export function annotationDraftKey(context:AnnotationContext){return `twin.annotation-draft.v2:${JSON.stringify([context.run_id,context.video_identity,context.run_fingerprint,context.dimensions])}`;}
export function encodeLocalDraft(document:AnnotationDocument,inputs:DraftInputs){return JSON.stringify({document:changeAnnotation(document,{}),inputs,saved_at:new Date().toISOString()});}
export function decodeLocalDraft(text:string,base:AnnotationDocument,context:AnnotationContext):LocalAnnotationDraft{
 if(text.length>2*1024*1024)throw new Error('本地草稿过大');
 const value=JSON.parse(text);if(!value||typeof value!=='object'||Object.keys(value).some(k=>!['document','inputs','saved_at'].includes(k)))throw new Error('本地草稿格式无效');
 const draft=value.document as AnnotationDocument,inputs=value.inputs as DraftInputs;
 if(!draft||!inputs||typeof value.saved_at!=='string'||value.saved_at.length>50)throw new Error('本地草稿格式无效');
 for(const key of ['schema_version','run_id','video_identity','run_fingerprint','dimensions','source_video','created_at','updated_at','speed_state','speeds'] as const){if(JSON.stringify(draft[key])!==JSON.stringify(base[key])){
  // Dates/source facts may have advanced with a new server revision. Never import them from cache.
  if(!['source_video','created_at','updated_at'].includes(key))throw new Error('本地草稿与当前运行绑定不一致');
 }}
 if(Object.keys(inputs).some(k=>!['crossNote','eventType','vehicleId','physicalNote'].includes(k))||!Object.hasOwn(eventLabels,inputs.eventType))throw new Error('待录入内容无效');
 for(const key of ['crossNote','physicalNote','vehicleId'] as const)if(typeof inputs[key]!=='string'||inputs[key].length>(key==='vehicleId'?50:200))throw new Error('待录入内容无效');
 const editable=(v:unknown)=>typeof v==='number'?Number.isFinite(v):typeof v==='string'&&v.length<=50;
 if(!Array.isArray(draft.interval)||draft.interval.length!==2||!draft.interval.every(editable)||!Array.isArray(draft.crossings)||!Array.isArray(draft.events))throw new Error('本地编辑字段无效');
 for(const row of [...draft.crossings,...draft.events])if(!row||!editable(row.timestamp))throw new Error('本地条目时间无效');
 for(const row of draft.events)if(row.vehicle_id!==null&&!editable(row.vehicle_id))throw new Error('本地条目ID无效');
 // Structural validation permits unfinished numeric input. The returned draft keeps it exactly;
 // normal Save/Export still validates actual values, bounds and unmapped notes.
 const candidate={...draft,source_video:base.source_video,created_at:base.created_at,updated_at:base.updated_at,verified:false,completeness_confirmed:false};
 validateAnnotation({...candidate,interval:context.interval!,crossings:draft.crossings.map(row=>({...row,timestamp:context.interval![0]})),events:draft.events.map(row=>({...row,timestamp:context.interval![0],vehicle_id:1}))},context);
 return {document:candidate,inputs,saved_at:value.saved_at};
}
