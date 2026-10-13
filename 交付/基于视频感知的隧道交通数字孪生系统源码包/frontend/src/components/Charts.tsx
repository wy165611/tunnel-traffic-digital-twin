import {useEffect,useRef} from 'react';
import * as echarts from 'echarts/core';
import {LineChart,PieChart} from 'echarts/charts';
import {GridComponent,LegendComponent,TooltipComponent,GraphicComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import type {HistoryPoint} from '../types';
import {typeNames} from '../api';
import {readVisualTheme,chartTooltip} from '../theme';
echarts.use([LineChart,PieChart,GridComponent,LegendComponent,TooltipComponent,GraphicComponent,CanvasRenderer]);

export default function Charts({history,types}:{history:HistoryPoint[];types:Record<string,number>}){
 const total=Object.values(types).reduce((a,b)=>a+b,0);
 const line=useRef<HTMLDivElement>(null),pie=useRef<HTMLDivElement>(null), lc=useRef<echarts.ECharts|null>(null),pc=useRef<echarts.ECharts|null>(null);
 useEffect(()=>{lc.current=echarts.init(line.current!);pc.current=echarts.init(pie.current!);const obs=new ResizeObserver(()=>{lc.current?.resize();pc.current?.resize();});obs.observe(line.current!);obs.observe(pie.current!);return()=>{obs.disconnect();lc.current?.dispose();pc.current?.dispose();};},[]);
 useEffect(()=>{
  const theme=readVisualTheme();
  lc.current?.setOption({animation:false,color:theme.series,textStyle:{fontFamily:theme.font},tooltip:{trigger:'axis',...chartTooltip(theme)},legend:{data:['累计流量','平均速度','当前车辆'],textStyle:{color:theme.muted,fontSize:12},top:12,left:16,right:16,itemWidth:12,itemHeight:7,itemGap:14},grid:{left:40,right:44,top:64,bottom:36},xAxis:{type:'value',axisLabel:{color:theme.subtle,fontSize:11,formatter:'{value}s'},splitLine:{show:false}},yAxis:[{type:'value',min:0,axisLabel:{color:theme.subtle,fontSize:11},splitLine:{lineStyle:{color:theme.border,type:'dashed'}}},{type:'value',min:0,axisLabel:{color:theme.subtle,fontSize:11,formatter:'{value}'},splitLine:{show:false},name:'km/h',nameTextStyle:{color:theme.subtle,fontSize:11}}],series:[{name:'累计流量',type:'line',smooth:true,symbol:'none',data:history.map(h=>[h.timestamp,h.flow]),areaStyle:{opacity:.06}},{name:'平均速度',type:'line',smooth:true,symbol:'none',yAxisIndex:1,data:history.map(h=>[h.timestamp,h.average_speed])},{name:'当前车辆',type:'line',step:'end',symbol:'none',data:history.map(h=>[h.timestamp,h.vehicle_count])}]});
 },[history]);
 useEffect(()=>{
  const theme=readVisualTheme();
  pc.current?.setOption({animation:false,tooltip:{trigger:'item',...chartTooltip(theme)},legend:{bottom:16,itemWidth:8,itemHeight:8,itemGap:12,textStyle:{color:theme.muted,fontSize:12}},series:[{type:'pie',radius:['45%','65%'],center:['50%','42%'],label:{show:false},itemStyle:{borderColor:theme.surface,borderRadius:4,borderWidth:3},data:Object.entries(types).map(([name,value])=>({name:typeNames[name]||name,value,itemStyle:{color:theme.vehicles[name]||theme.accent}}))}],graphic:[{type:'text',left:'center',top:'34%',style:{text:total?String(total):'—',fill:theme.text,fontSize:30,fontFamily:theme.mono}}]});
 },[types,total]);
 return <><section className="panel chart-panel"><div className="panel-title"><span>交通运行趋势</span><small>视频时间轴</small></div><div className="chart-wrap"><div ref={line} className="chart" role="img" aria-label={`交通运行趋势，包含 ${history.length} 个时间采样点`}/>{!history.length&&<div className="chart-empty"><span>开始分析后显示交通趋势</span></div>}</div></section><section className="panel chart-panel"><div className="panel-title"><span>当前车辆构成</span><small>实时分类</small></div><div className="chart-wrap"><div ref={pie} className="chart" role="img" aria-label={`当前车辆构成：${Object.entries(types).map(([type,count])=>`${typeNames[type]||type} ${count} 辆`).join("，")||'暂无车辆'}`}/>{!total&&<div className="chart-empty"><span>暂无已确认车辆</span></div>}</div></section></>
}
