import {useCallback,useEffect,useRef,useState} from 'react';

export type SectionId='overview'|'perception'|'analysis'|'events'|'details'|'exports';
const mainSections:SectionId[]=['overview','perception','analysis','details','exports'];

export function useSectionNavigation(enabled:boolean){
 const [active,setActive]=useState<SectionId>('overview');
 const requested=useRef<{id:SectionId;time:number}|null>(null);
 const navigate=useCallback((id:SectionId)=>{
  const target=document.getElementById(id);if(!target)return;
  requested.current={id,time:performance.now()};setActive(id);
  if(location.hash!==`#${id}`)history.pushState(null,'',`#${id}`);
  target.focus({preventScroll:true});
  target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
 },[]);
 useEffect(()=>{
  if(!enabled)return;
  let frame=0;
  const update=()=>{
   frame=0;
   const pending=requested.current;
   if(pending){
    const rect=document.getElementById(pending.id)?.getBoundingClientRect();
    // Keep explicit event/export jumps selected even when their parent shares a row.
    if(rect&&((rect.top<innerHeight&&rect.bottom>24)||performance.now()-pending.time<1000)){setActive(pending.id);return;}
    requested.current=null;
   }
   let current:SectionId='overview';
   for(const id of mainSections){
    const rect=document.getElementById(id)?.getBoundingClientRect();
    if(rect&&rect.top<=Math.min(120,innerHeight*.2))current=id;
   }
   if(scrollY>0&&scrollY+innerHeight>=document.documentElement.scrollHeight-4)current='exports';
   setActive(current);
  };
  const schedule=()=>{if(!frame)frame=requestAnimationFrame(update);};
  const manual=()=>{requested.current=null;schedule();};
  const keys=(e:KeyboardEvent)=>{
   const element=e.target as HTMLElement;
   if(element.closest('input,select,textarea,[contenteditable="true"]'))return;
   if(['ArrowDown','ArrowUp','PageDown','PageUp','Home','End',' '].includes(e.key))manual();
  };
  const restore=()=>{
   const id=location.hash.slice(1) as SectionId;
   if([...mainSections,'events'].includes(id)&&document.getElementById(id)){
    requested.current={id,time:performance.now()};setActive(id);
    document.getElementById(id)!.scrollIntoView({behavior:'instant',block:'start'});
   }else manual();
  };
  window.addEventListener('scroll',schedule,{passive:true});
  window.addEventListener('resize',manual);
  window.addEventListener('wheel',manual,{passive:true});
  window.addEventListener('touchmove',manual,{passive:true});
  window.addEventListener('keydown',keys);
  window.addEventListener('popstate',restore);
  window.addEventListener('hashchange',restore);
  const observer=new ResizeObserver(schedule);
  const content=document.getElementById('main-content');if(content)observer.observe(content);
  restore();
  return()=>{
   cancelAnimationFrame(frame);observer.disconnect();
   window.removeEventListener('scroll',schedule);window.removeEventListener('resize',manual);
   window.removeEventListener('wheel',manual);window.removeEventListener('touchmove',manual);
   window.removeEventListener('keydown',keys);window.removeEventListener('popstate',restore);window.removeEventListener('hashchange',restore);
  };
 },[enabled]);
 return {active,navigate};
}
