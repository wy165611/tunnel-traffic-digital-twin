export function roundedRectPath(ctx:CanvasRenderingContext2D,x:number,y:number,width:number,height:number,radius:number){
  if(typeof ctx.roundRect==='function'){ctx.roundRect(x,y,width,height,radius);return;}
  ctx.rect(x,y,width,height);
}
