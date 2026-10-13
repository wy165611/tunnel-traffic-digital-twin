export interface LabelRect {x:number;y:number;width:number;height:number}
const clamp=(value:number,max:number)=>Math.max(0,Math.min(value,Math.max(0,max)));
const intersects=(a:LabelRect,b:LabelRect)=>a.x<b.x+b.width+3&&a.x+a.width+3>b.x&&a.y<b.y+b.height+3&&a.y+a.height+3>b.y;

/** Keep labels inside the canvas and reserve nearby free rows before drawing. */
export function placeCanvasLabel(x:number,y:number,width:number,height:number,bounds:{width:number;height:number},occupied:LabelRect[]):LabelRect {
 const base={x:clamp(x,bounds.width-width),y:clamp(y,bounds.height-height),width,height};
 for(let step=0;step<=Math.ceil(bounds.height/(height+4));step++){
  for(const direction of step?[1,-1]:[0]){
   const candidate={...base,y:clamp(base.y+step*direction*(height+4),bounds.height-height)};
   if(!occupied.some(rect=>intersects(candidate,rect))){occupied.push(candidate);return candidate;}
  }
 }
 occupied.push(base);return base;
}
