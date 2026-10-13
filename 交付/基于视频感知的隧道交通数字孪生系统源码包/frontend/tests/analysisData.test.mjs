import assert from 'node:assert/strict';
import {test} from 'node:test';
import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
const result=await build({entryPoints:[fileURLToPath(new URL('../src/utils/analysisData.ts',import.meta.url))],bundle:true,write:false,format:'esm',platform:'node'});
const {laneWindowRows,laneSeries,evidenceClip,LoadVersion}=await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
test('lane chart selects one window and lane and keeps null speeds and predicted counts distinct',()=>{
 const rows=[{lane:'A',window_seconds:10,timestamp:1,average_speed:null,window_flow:2,observed_count:0,predicted_count:3},{lane:'A',window_seconds:30,timestamp:1,average_speed:20,window_flow:5},{lane:'B',window_seconds:10,timestamp:1,average_speed:40,window_flow:1},{lane:'A',window_seconds:10,timestamp:2,average_speed:10,window_flow:3,observed_count:1,predicted_count:2}];
 assert.equal(laneWindowRows(rows,10).length,3);
 assert.deepEqual(laneSeries(rows,'A',10),[{timestamp:1,flow:2,speed:null,observed:0,predicted:3},{timestamp:2,flow:3,speed:10,observed:1,predicted:2}]);
});
test('evidence playback bounds cover before/after event and recording edges',()=>{
 assert.deepEqual(evidenceClip(2,20),{start:0,end:7});
 assert.deepEqual(evidenceClip(18,20),{start:13,end:20});
 assert.deepEqual(evidenceClip(10),{start:5,end:15});
});
test('late report/comparison/evidence responses and saves cannot replace a newer dialog target',()=>{
 const gate=new LoadVersion(),first=gate.next(),second=gate.next();
 assert.equal(gate.current(first),false);assert.equal(gate.current(second),true);
 gate.cancel();assert.equal(gate.current(second),false);
 const reopened=gate.next();assert.equal(gate.current(reopened),true);
});
