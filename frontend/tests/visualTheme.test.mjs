import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';

const root=readFileSync(new URL('../src/styles.css',import.meta.url),'utf8').split('}')[0];
const tokens=Object.fromEntries([...root.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6});/gi)].map(([,name,value])=>[name,value]));
const luminance=hex=>{
  const rgb=hex.slice(1).match(/../g).map(n=>parseInt(n,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
  return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
};
const contrast=(foreground,background)=>{
  assert.ok(tokens[foreground],`Missing ${foreground}`);assert.ok(tokens[background],`Missing ${background}`);
  const values=[luminance(tokens[foreground]),luminance(tokens[background])].sort((a,b)=>b-a);
  return(values[0]+.05)/(values[1]+.05);
};

test('warm theme keeps small text and semantic states readable across all dashboard surfaces',()=>{
  for(const fg of ['text','muted','subtle','accent','success','warning','danger'])
    for(const bg of ['bg','surface','surface-raised','surface-hover'])
      assert.ok(contrast(fg,bg)>=4.5,`${fg} on ${bg} must meet AA for small text`);
  for(const bg of ['primary','primary-pressed'])assert.ok(contrast('on-primary',bg)>=4.5);
  assert.ok(contrast('on-primary-hover','primary-hover')>=4.5);
});

test('chart lines, vehicle categories and control boundaries remain distinguishable from their surfaces',()=>{
  for(const fg of ['series-1','series-2','series-3','series-4','vehicle-car','vehicle-truck','vehicle-bus','vehicle-motorcycle'])
    for(const bg of ['bg','surface','surface-raised'])assert.ok(contrast(fg,bg)>=3);
  for(const bg of ['bg','surface','surface-raised','surface-hover'])assert.ok(contrast('border-strong',bg)>=3);
});
