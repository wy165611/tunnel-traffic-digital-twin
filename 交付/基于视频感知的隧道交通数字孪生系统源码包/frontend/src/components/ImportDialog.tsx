import {useEffect,useRef,type ReactNode} from 'react';

export default function ImportDialog({children,onClose,busy,labelledBy='import-title',wide=false,returnFocus}:{children:ReactNode;onClose:()=>void;busy:boolean;labelledBy?:string;wide?:boolean;returnFocus?:HTMLElement|null}){
 const dialog=useRef<HTMLDivElement>(null),close=useRef(onClose),locked=useRef(busy);
 close.current=onClose;locked.current=busy;
 useEffect(()=>{
  const previous=returnFocus||document.activeElement as HTMLElement|null;
  const oldOverflow=document.body.style.overflow;
  document.body.style.overflow='hidden';
  const focusable=()=>Array.from(dialog.current!.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), video[controls], a[href], [tabindex="0"]')).filter(el=>el.getClientRects().length>0);
  (focusable()[0]||dialog.current)?.focus();
  const key=(e:KeyboardEvent)=>{
   if(e.key==='Escape'&&!locked.current){e.preventDefault();close.current();}
   if(e.key==='Tab'){
    const elements=focusable(),first=elements[0],last=elements.at(-1);
    if(!first){e.preventDefault();dialog.current?.focus();return;}
    if(e.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current||!dialog.current?.contains(document.activeElement))){e.preventDefault();last?.focus();}
    else if(!e.shiftKey&&(document.activeElement===last||!dialog.current?.contains(document.activeElement))){e.preventDefault();first.focus();}
   }
  };
  document.addEventListener('keydown',key);
  return()=>{
   document.body.style.overflow=oldOverflow;document.removeEventListener('keydown',key);
   // Restore after React removes background inert, otherwise browsers reject focus.
   requestAnimationFrame(()=>{if(previous?.isConnected)previous.focus({preventScroll:true});});
  };
 },[]);
 useEffect(()=>{
  // Disabling the focused control during a request can move focus to body.
  if(!busy&&dialog.current&&!dialog.current.contains(document.activeElement))
   (dialog.current.querySelector<HTMLElement>('button:not(:disabled)')||dialog.current).focus({preventScroll:true});
 },[busy]);
 return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget&&!busy)onClose();}}><div ref={dialog} className={'modal panel '+(wide?'analysis-modal':'')} role="dialog" aria-modal="true" aria-labelledby={labelledBy} tabIndex={-1}>{children}</div></div>;
}
