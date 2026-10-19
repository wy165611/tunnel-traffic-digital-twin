import assert from 'node:assert/strict';
import {test} from 'node:test';
import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';

const bundle = await build({
  entryPoints: [fileURLToPath(new URL('../src/utils/eventAlerts.ts', import.meta.url))],
  bundle: true,
  write: false,
  format: 'esm',
  platform: 'node',
});
const {eventKey, unseenEvents, readSoundPreference, writeSoundPreference, cooldownEvents, cooldownKey} = await import(
  `data:text/javascript,${encodeURIComponent(bundle.outputFiles[0].text)}`);

const event = (patch = {}) => ({timestamp: 1, vehicle_id: 7, event: 'SPEEDING', label: '超速', lane: 'A', speed: 90, ...patch});

test('event keys prefer evidence ids and otherwise stay stable', () => {
  assert.equal(eventKey(event({event_id: 'a'.repeat(32)})), 'a'.repeat(32));
  assert.equal(eventKey(event()), ':1:7:SPEEDING');
  assert.equal(eventKey(event({run_id: 'run'})), 'run:1:7:SPEEDING');
});

test('unseen events only include ids not already acknowledged', () => {
  const seen = new Set([eventKey(event({event_id: 'one'}))]);
  const result = unseenEvents(seen, [event({event_id: 'two'}), event({event_id: 'one'})]);
  assert.deepEqual(result.map(item => item.event_id), ['two']);
});

test('sound preference defaults on and persists both states', () => {
  const values = new Map();
  const storage = {getItem: key => values.has(key) ? values.get(key) : null, setItem: (key, value) => values.set(key, value)};
  assert.equal(readSoundPreference(storage), true);
  writeSoundPreference(false, storage);
  assert.equal(readSoundPreference(storage), false);
  writeSoundPreference(true, storage);
  assert.equal(readSoundPreference(storage), true);
  const broken = {getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); }};
  assert.equal(readSoundPreference(broken), true);
  assert.doesNotThrow(() => writeSoundPreference(false, broken));
});

test('alert cooldown suppresses the same vehicle and event within the window', () => {
  const seen = new Map();
  assert.equal(cooldownKey(event()), '7:SPEEDING');
  const first = cooldownEvents([event({timestamp: 100})], seen, 10);
  assert.equal(first.length, 1);
  assert.equal(cooldownEvents([event({timestamp: 105})], seen, 10).length, 0);
  assert.equal(cooldownEvents([event({timestamp: 105, vehicle_id: 8})], seen, 10).length, 1);
  assert.equal(cooldownEvents([event({timestamp: 105, event: 'WRONG WAY'})], seen, 10).length, 1);
  assert.equal(cooldownEvents([event({timestamp: 111})], seen, 10).length, 1);
  assert.equal(cooldownEvents([event({timestamp: 111})], seen, 0).length, 1);
});
