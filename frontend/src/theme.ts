// CSS is the source of truth for DOM, ECharts and video/twin overlays.
export function readVisualTheme(){
 const css=getComputedStyle(document.documentElement);
 const token=(name:string)=>css.getPropertyValue(`--${name}`).trim();
 return {
  bg:token('bg'),surface:token('surface'),raised:token('surface-raised'),hover:token('surface-hover'),
  border:token('border'),borderStrong:token('border-strong'),text:token('text'),muted:token('muted'),subtle:token('subtle'),
  accent:token('accent'),success:token('success'),warning:token('warning'),danger:token('danger'),
  font:token('font-sans'),mono:token('mono'),
  series:[1,2,3,4].map(i=>token(`series-${i}`)),
  vehicles:Object.fromEntries(['car','truck','bus','motorcycle'].map(type=>[type,token(`vehicle-${type}`)])),
 };
}
export function chartTooltip(theme:ReturnType<typeof readVisualTheme>){
 return {backgroundColor:theme.raised,borderColor:theme.borderStrong,textStyle:{color:theme.text,fontFamily:theme.font,fontSize:12},confine:true};
}
