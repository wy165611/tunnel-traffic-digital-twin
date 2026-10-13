export async function api<T>(path:string, body?:unknown):Promise<T> {
  const res=await fetch('/api'+path,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await res.json();
  if(!res.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
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
