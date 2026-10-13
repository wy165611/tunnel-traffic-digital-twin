import assert from 'node:assert/strict';
import {test} from 'node:test';
import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
import {readFileSync} from 'node:fs';
const load = async (entry, plugins=[]) => {
  const result=await build({entryPoints:[fileURLToPath(new URL(entry,import.meta.url))],bundle:true,write:false,format:'esm',platform:'node',plugins});
  return import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
};
const {SnapshotGate,FrameDecoder,appendDrawPoint}=await load('../src/utils/snapshotState.ts');
const snapshot=(revision,changes={})=>({session_id:'server-a',video_token:'video-a',scene_revision:0,revision,status:'paused',error:null,rate:1,video_id:'a.mp4',video:{width:100,height:100,display_width:100,display_height:100},scene:{lanes:[],counting_line:null},calibration:null,settings:{},frame:revision,image:`frame-${revision}`,history:[],vehicles:[],...changes});

test('late GET/POST snapshots cannot roll back a newer websocket frame',()=>{
  const gate=new SnapshotGate();gate.accept(snapshot(4),'websocket');
  const current=gate.accept(snapshot(2),'http');assert.equal(current.frame,4);
  assert.equal(gate.accept(snapshot(4),'http'),current);
});

test('server restart accepts a new epoch and rejects the previous epoch thereafter',()=>{
  const gate=new SnapshotGate();gate.accept(snapshot(20),'websocket');
  assert.equal(gate.accept(snapshot(0,{session_id:'server-b'}),'websocket').revision,0);
  assert.equal(gate.accept(snapshot(21),'http').session_id,'server-b');
  assert.equal(gate.accept(snapshot(22),'websocket').session_id,'server-b');
  assert.equal(gate.accept(snapshot(1,{session_id:'server-b'}),'websocket').revision,1);
});

test('identical history and type data keep their references between frames',()=>{
  const gate=new SnapshotGate();
  const first=gate.accept(snapshot(1,{history:[{timestamp:1,flow:2}],metrics:{vehicle_types:{car:3}}}),'websocket');
  const next=gate.accept(snapshot(2,{history:[{timestamp:1,flow:2}],metrics:{vehicle_types:{car:3}}}),'websocket');
  assert.equal(next.history,first.history);assert.equal(next.scene,first.scene);
  assert.equal(next.metrics.vehicle_types,first.metrics.vehicle_types);
});

test('decoded image and its originating snapshot are committed as one pair',()=>{
  const images=[],commits=[];
  const decoder=new FrameDecoder(frame=>commits.push(frame),()=>assert.fail('unexpected decode error'),()=>{const image={};images.push(image);return image;});
  decoder.update(snapshot(1));images[0].onload();
  decoder.update(snapshot(2));assert.equal(commits.length,1);assert.equal(commits[0].snapshot.frame,1);
  images[1].onload();assert.equal(commits[1].snapshot.frame,2);assert.equal(commits[1].image.src,'frame-2');
});

test('out-of-order decoding and an unmounted decoder cannot commit stale frames',()=>{
  const images=[],commits=[];
  const decoder=new FrameDecoder(frame=>commits.push(frame),undefined,()=>{const image={};images.push(image);return image;});
  decoder.update(snapshot(1));decoder.update(snapshot(2));images[0].onload();assert.equal(commits.length,0);
  images[1].onload();assert.equal(commits[0].snapshot.frame,2);
  decoder.update(snapshot(3));decoder.cancel();images[2].onload();assert.equal(commits.length,1);
});

test('repeated terminal click does not append a zero-length polygon edge',()=>{
  const points=[[0,0],[100,0],[100,100]];
  assert.equal(appendDrawPoint(points,[100,100]),points);
  assert.deepEqual(appendDrawPoint(points,[0,100]),[...points,[0,100]]);
});

const hookPlugin={name:'controlled-react-hooks',setup(build){
  build.onResolve({filter:/^(react|react\/jsx-runtime|lucide-react)$/},args=>({path:args.path,namespace:'test-hooks'}));
  build.onLoad({filter:/.*/,namespace:'test-hooks'},args=>({contents:args.path==='react'?
    'export const useRef=v=>{const h=globalThis.__canvasHooks;return h.refs[h.index++]??=( {current:v} );};export const useLayoutEffect=f=>globalThis.__canvasHooks.effects.push(f);':
    args.path==='react/jsx-runtime'?'export const jsx=(type,props)=>{if(type==="canvas")props.ref.current=globalThis.__canvasHooks.canvas;return {type,props};};export const jsxs=jsx;':
    'export const FileVideo=()=>null;'}));
}};
const {default:VideoView}=await load('../src/components/VideoView.tsx',[hookPlugin]);

test('VideoView redraws editing overlays using the already decoded frame, then commits the new frame',t=>{
  // Supply the CSS token boundary used by the browser without mocking frame drawing.
  const tokens=Object.fromEntries([...readFileSync(new URL('../src/styles.css',import.meta.url),'utf8').matchAll(/--([\w-]+):\s*([^;]+);/g)].map(([,name,value])=>[`--${name}`,value]));
  const previousDocument=globalThis.document,previousStyle=globalThis.getComputedStyle;
  globalThis.document={documentElement:{}};
  globalThis.getComputedStyle=()=>({getPropertyValue:name=>tokens[name]??''});
  t.after(()=>{
    if(previousDocument===undefined)delete globalThis.document;else globalThis.document=previousDocument;
    if(previousStyle===undefined)delete globalThis.getComputedStyle;else globalThis.getComputedStyle=previousStyle;
    delete globalThis.__canvasHooks;
  });
  const traces=[],refs=[];
  const context=new Proxy({measureText:()=>({width:20}),drawImage:image=>traces.push(['image',image.src]),strokeRect:x=>traces.push(['box',x])},{get:(target,key)=>target[key]??(()=>{})});
  const canvas={width:100,height:100,clientHeight:100,getContext:()=>context};
  const render=frame=>{
    globalThis.__canvasHooks={refs,index:0,effects:[],canvas};
    VideoView({state:frame.snapshot,image:frame.image,editing:false,scene:frame.snapshot.scene,calibration:null,pending:[],onPoint:()=>{},onFinish:()=>{}});
    for(const effect of globalThis.__canvasHooks.effects)effect();
  };
  const images=[];let displayed;
  const decoder=new FrameDecoder(frame=>{displayed=frame;render(frame);},undefined,()=>{const image={};images.push(image);return image;});
  const withVehicle=id=>snapshot(id,{vehicles:[{box:[id,0,id+5,5],trajectory:[],status:'NORMAL',type:'car',speed:null,id}]});
  decoder.update(withVehicle(1));images[0].onload();
  decoder.update(withVehicle(2));render(displayed);
  assert.deepEqual(traces.slice(-2),[['image','frame-1'],['box',1]]);
  images[1].onload();assert.deepEqual(traces.slice(-2),[['image','frame-2'],['box',2]]);
  delete globalThis.__canvasHooks;
});
