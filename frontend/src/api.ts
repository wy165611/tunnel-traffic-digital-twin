function detailText(value:unknown):string|null{
  if(typeof value==='string'&&value.trim())return value.trim();
  if(!Array.isArray(value))return null;
  const messages=value.map(item=>{
    if(typeof item==='string')return item;
    if(!item||typeof item!=='object')return null;
    const record=item as Record<string,unknown>;
    const message=typeof record.msg==='string'?record.msg:'';
    if(!message)return null;
    const location=Array.isArray(record.loc)?record.loc.filter(part=>part!=='body'&&part!=='query'&&part!=='path').join('.'):'';
    return location?`${location}: ${message}`:message;
  }).filter((message):message is string=>!!message);
  return messages.length?messages.join('；'):null;
}

export async function parseApiResponse<T>(res:Response):Promise<T>{
  const text=await res.text();
  let data:unknown=null,parsed=true;
  if(text.trim()){
    try{data=JSON.parse(text);}catch{parsed=false;}
  }
  if(!res.ok){
    const body=data&&typeof data==='object'?data as {detail?:unknown;message?:unknown}:null;
    const detail=detailText(body?.detail)||detailText(body?.message);
    const contentType=res.headers.get('content-type')||'';
    const fallback=parsed||contentType.includes('html')?null:text.trim().slice(0,300);
    throw new Error(detail||fallback||res.statusText||`请求失败（HTTP ${res.status}）`);
  }
  if(!parsed)throw new Error(`服务响应无法解析（HTTP ${res.status}）`);
  return data as T;
}

export async function api<T>(path:string, body?:unknown):Promise<T> {
  const res=await fetch('/api'+path,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return parseApiResponse<T>(res);
}
export const formatSpeed=(v:number|null|undefined)=>v==null?'—':v.toFixed(1);
export const formatTime=(v:number=0)=>{
  const hours=Math.floor(v/3600);
  const minutes=Math.floor((v%3600)/60);
  const seconds=Math.floor(v%60);
  const tenths=Math.floor((v%1)*10);
  const body=`${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}.${tenths}`;
  return hours>0?`${hours.toString().padStart(2,'0')}:${body}`:body;
};
export const typeNames:Record<string,string>={car:'轿车',truck:'货车',bus:'客车',motorcycle:'摩托车'};
