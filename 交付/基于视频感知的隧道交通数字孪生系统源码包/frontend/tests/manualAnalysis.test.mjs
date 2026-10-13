import assert from 'node:assert/strict';
import {test} from 'node:test';
import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
const result=await build({entryPoints:[fileURLToPath(new URL('../src/utils/manualAnalysis.ts',import.meta.url))],bundle:true,write:false,format:'esm',platform:'node'});
const {containRect,parseSeconds,parseVehicleId,changeAnnotation,validateAnnotation,importAnnotation,categoryValue,PausedSampleGate,recordCrossing,recordEvent,readAnnotationImport,annotationDraftKey,encodeLocalDraft,decodeLocalDraft}=await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
const context={available:true,run_id:'20260101-000000-abcdef',video_identity:'a'.repeat(24),run_fingerprint:'b'.repeat(64),dimensions:[200,400],interval:[1,10]};
const doc=()=>({schema_version:2,run_id:context.run_id,video_identity:context.video_identity,run_fingerprint:context.run_fingerprint,dimensions:[200,400],interval:[1,10],annotator:'人工测试',note:'',revision:1,created_at:null,updated_at:null,crossings:[],events:[],speeds:[],speed_state:'unreviewed',reviewed_sections:['crossings'],verified:true,completeness_confirmed:true});
test('overlay letterboxing preserves original pixel ratio and fits wide, tall, narrow displays',()=>{
 for(const [sw,sh,w,h] of [[1920,1080,700,390],[1080,1920,700,390],[1080,1920,286,310],[3840,2160,286,310]]){
  const fit=containRect(sw,sh,w,h);
  assert.ok(fit.x>=0&&fit.y>=0&&fit.x+fit.width<=w+1e-8&&fit.y+fit.height<=h+1e-8);
  assert.ok(Math.abs(fit.width/fit.height-sw/sh)<1e-8);
  const pixel=[sw/2,sh/2];assert.ok(Math.abs(fit.x+pixel[0]*fit.scale-w/2)<1e-8);assert.ok(Math.abs(fit.y+pixel[1]*fit.scale-h/2)<1e-8);
 }
});
test('finite parsing rejects booleans, blank values, infinities and fractional/zero IDs',()=>{
 assert.equal(parseSeconds('1.25'),1.25);assert.equal(parseVehicleId('2'),2);assert.equal(parseVehicleId(''),null);
 for(const value of [true,false,{},[],null,'',Infinity,'NaN',-1])assert.throws(()=>parseSeconds(value));
 for(const value of [true,false,{},[],0,-1,1.5,'bad'])assert.throws(()=>parseVehicleId(value));
});
test('edits revoke completeness while keeping manually supplied missed events independent',()=>{
 const original=doc(),changed=changeAnnotation(original,{events:[{timestamp:3,event:'WRONG WAY',vehicle_id:null,physical_vehicle_note:'完全漏检白车'}]});
 assert.equal(changed.verified,false);assert.equal(changed.completeness_confirmed,false);assert.equal(original.verified,true);
 assert.equal(validateAnnotation(changed,context).events[0].vehicle_id,null);
 changed.events[0].physical_vehicle_note='';assert.throws(()=>validateAnnotation(changed,context));
});
test('JSON import validates bindings, strict unknown fields and source facts before replacing draft; reconfirmation is required',()=>{
 const valid=importAnnotation(JSON.stringify(doc()),context,5);assert.equal(valid.revision,5);assert.equal(valid.verified,false);
 for(const changes of [{run_id:'another'},{video_identity:'z'},{run_fingerprint:'changed'},{dimensions:[1,1]},{interval:[0,10]},{interval:[1,true]},{verified:'true'},{revision:true},{unrecognized:'field'},{source_video:{width:200,height:400,fps:true}},{source_video:{width:200,height:400,fps:10,unknown:'x'}},{events:[{timestamp:2,event:'WRONG WAY',vehicle_id:1,physical_vehicle_note:'',unknown:1}]}])assert.throws(()=>importAnnotation(JSON.stringify({...doc(),...changes}),context,1));
 assert.equal(doc().verified,true); // no replacement occurred in a throwing import.
});
test('unknown categories and mathematically undefined precision/recall render differently from zero',()=>{
 assert.equal(categoryValue(false,null),'未评测');assert.equal(categoryValue(true,null),'不可定义');assert.equal(categoryValue(true,0),'0');assert.equal(categoryValue(true,.5,true),'50.0%');
});
test('a delayed paused observation lookup is retired by first seek/play even before any samples arrive',async()=>{
 const gate=new PausedSampleGate();gate.update(1,true);const first=gate.next();
 let resolve;const delayed=new Promise(r=>{resolve=r;});
 const commits=[];const response=delayed.then(value=>{if(gate.current(first))commits.push(value);});
 gate.update(2,true);resolve({sample_timestamp:1});await response;assert.deepEqual(commits,[]);
 const next=gate.next();assert.equal(gate.current(next),true);gate.update(2,false);assert.equal(gate.current(next),false);
});

test('the recording handlers retain exact noninteger start/end PTS within inclusive interval',()=>{
 const bounds=[1/30,121/30],target={...context,interval:bounds},initial={...doc(),interval:bounds};
 for(const seconds of bounds){
  const crossing=recordCrossing(initial,target,seconds,'白车');assert.equal(crossing.crossings[0].timestamp,seconds);assert.equal(crossing.verified,false);
  const event=recordEvent(initial,target,seconds,'WRONG WAY','','漏检白车');assert.equal(event.events[0].timestamp,seconds);assert.equal(validateAnnotation(event,target).events[0].vehicle_id,null);
 }
 assert.throws(()=>recordCrossing(initial,target,bounds[0]-.0001,''));
 assert.throws(()=>recordEvent(initial,target,bounds[1]+.0001,'WRONG WAY','1',''));
});
test('local reload recovery preserves incomplete inputs without auto merging server revisions or verification',()=>{
 const storage=new Map(),base=doc(),edited=changeAnnotation(base,{interval:['',10],crossings:[{timestamp:'',physical_vehicle_note:'正在填写'}],events:[{timestamp:'-',event:'WRONG WAY',vehicle_id:'-',physical_vehicle_note:''}]});
 const inputs={crossNote:'尚未记录的车',eventType:'WRONG WAY',vehicleId:'-',physicalNote:'暂未填完'};
 const key=annotationDraftKey(context);storage.set(key,encodeLocalDraft(edited,inputs));
 const server={...base,revision:4,note:'其他窗口新保存',updated_at:'2026-10-02'};
 const restored=decodeLocalDraft(storage.get(key),server,context);
 assert.equal(restored.document.interval[0],'');assert.equal(restored.document.events[0].vehicle_id,'-');assert.equal(restored.inputs.crossNote,inputs.crossNote);
 assert.equal(restored.document.revision,1);assert.equal(server.revision,4);assert.equal(server.note,'其他窗口新保存');assert.equal(restored.document.verified,false);
 assert.throws(()=>validateAnnotation(restored.document,context)); // Restore accepts an unfinished edit; Save does not.
 assert.notEqual(annotationDraftKey({...context,run_fingerprint:'different'}),key);
 assert.notEqual(annotationDraftKey({...context,run_id:'other'}),key);
 assert.throws(()=>decodeLocalDraft(storage.get(key),base,{...context,video_identity:'other'}));
 for(const invalid of ['{bad',JSON.stringify({document:{...edited,dimensions:[1,1]},inputs,saved_at:'today'}),JSON.stringify({document:{...edited,crossings:[{timestamp:true,physical_vehicle_note:''}]},inputs,saved_at:'today'})])assert.throws(()=>decodeLocalDraft(invalid,base,context));
 storage.delete(key);assert.equal(storage.has(key),false); // successful Save or explicit Discard removes only this binding.
});
test('delayed JSON file reads cannot overwrite a later import, edit, save or target teardown',async()=>{
 // Use the same production gate as AnnotationDialog, including cancellation on edit/unmount.
 const built=await build({entryPoints:[fileURLToPath(new URL('../src/utils/analysisData.ts',import.meta.url))],bundle:true,write:false,format:'esm',platform:'node'});
 const {LoadVersion}=await import('data:text/javascript;base64,'+Buffer.from(built.outputFiles[0].text).toString('base64'));
 const gate=new LoadVersion();let resolveA;const a={size:100,text:()=>new Promise(r=>{resolveA=r;})};
 const first=readAnnotationImport(a,context,1,gate,gate.next());
 const second=await readAnnotationImport({size:100,text:async()=>JSON.stringify({...doc(),note:'B'})},context,1,gate,gate.next());
 resolveA(JSON.stringify({...doc(),note:'A'}));assert.equal(await first,null);assert.equal(second.note,'B');
 for(const reason of ['edit','save','unmount']){
  let resolve;const pending=readAnnotationImport({size:100,text:()=>new Promise(r=>{resolve=r;})},context,1,gate,gate.next());
  if(reason==='save')gate.next();else gate.cancel();
  resolve('{stale malformed JSON');assert.equal(await pending,null); // Even obsolete parse errors cannot disturb the new editor.
 }
 assert.equal((await readAnnotationImport({size:100,text:async()=>JSON.stringify(doc())},context,7,gate,gate.next())).revision,7);
});
