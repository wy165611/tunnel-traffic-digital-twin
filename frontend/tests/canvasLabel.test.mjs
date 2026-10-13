import assert from 'node:assert/strict';
import {test} from 'node:test';
import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
const result=await build({entryPoints:[fileURLToPath(new URL('../src/utils/canvasLabel.ts',import.meta.url))],bundle:true,write:false,format:'esm',platform:'node'});
const {placeCanvasLabel}=await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));

test('nearby vehicle labels occupy separate rows and remain within narrow canvas bounds',()=>{
 const occupied=[],bounds={width:240,height:360};
 for(const [x,y] of [[100,100],[103,102],[99,101],[150,105],[228,-12],[230,355]]){
  const label=placeCanvasLabel(x,y,90,20,bounds,occupied);
  assert.ok(label.x>=0&&label.y>=0);
  assert.ok(label.x+label.width<=bounds.width&&label.y+label.height<=bounds.height);
  for(const other of occupied.slice(0,-1))assert.ok(label.x>=other.x+other.width||other.x>=label.x+label.width||label.y>=other.y+other.height||other.y>=label.y+label.height);
 }
});

test('a crowded canvas returns a bounded fallback without moving vehicle geometry',()=>{
 const occupied=[{x:0,y:0,width:100,height:50}];
 assert.deepEqual(placeCanvasLabel(200,-10,90,20,{width:100,height:50},occupied),{x:10,y:0,width:90,height:20});
});
