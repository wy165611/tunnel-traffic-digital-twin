import {useEffect,useRef} from 'react';
import * as echarts from 'echarts/core';
import {LineChart} from 'echarts/charts';
import {GridComponent,LegendComponent,TooltipComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {readVisualTheme,chartTooltip} from '../theme';
echarts.use([LineChart,GridComponent,LegendComponent,TooltipComponent,CanvasRenderer]);
export default function AnalysisChart({series,label}:{series:{name:string;data:[number,number|null][];speed?:boolean;dashed?:boolean}[];label:string}){
 const ref=useRef<HTMLDivElement>(null),chart=useRef<echarts.ECharts|null>(null);
 useEffect(()=>{chart.current=echarts.init(ref.current!);const observer=new ResizeObserver(()=>chart.current?.resize());observer.observe(ref.current!);return()=>{observer.disconnect();chart.current?.dispose();};},[]);
 useEffect(()=>{const theme=readVisualTheme();chart.current?.setOption({animation:false,color:theme.series,textStyle:{fontFamily:theme.font},tooltip:{trigger:'axis',...chartTooltip(theme)},legend:{type:'scroll',top:12,left:16,right:16,textStyle:{color:theme.muted,fontSize:12}},grid:{left:44,right:48,top:64,bottom:36},xAxis:{type:'value',axisLabel:{color:theme.subtle,fontSize:12,formatter:'{value}s'}},yAxis:[{type:'value',min:0,axisLabel:{color:theme.subtle,fontSize:12},splitLine:{lineStyle:{color:theme.border}}},{type:'value',min:0,name:'km/h',axisLabel:{color:theme.subtle,fontSize:12},splitLine:{show:false},nameTextStyle:{color:theme.subtle}}],series:series.map(s=>({name:s.name,type:'line',symbol:'none',connectNulls:false,yAxisIndex:s.speed?1:0,lineStyle:{type:s.dashed?'dashed':'solid'},data:s.data}))},true);},[series]);
 return <div ref={ref} className="analysis-chart" role="img" aria-label={label}/>;
}
