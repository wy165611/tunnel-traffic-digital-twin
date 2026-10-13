import type {LaneRow} from '../types';
export function laneWindowRows(rows:LaneRow[],window:number){return rows.filter(row=>row.window_seconds===window);}
export function laneSeries(rows:LaneRow[],lane:string,window:number){return laneWindowRows(rows,window).filter(row=>row.lane===lane).map(row=>({timestamp:row.timestamp,flow:row.window_flow,speed:row.average_speed,observed:row.observed_count,predicted:row.predicted_count}));}
export function evidenceClip(timestamp:number,duration?:number){return {start:Math.max(0,timestamp-5),end:Math.min(duration??Infinity,timestamp+5)};}
export class LoadVersion{private version=0;next(){return ++this.version;}current(version:number){return this.version===version;}cancel(){this.version++;}}
