import assert from 'node:assert/strict';
import {test} from 'node:test';
import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';

const bundle = await build({
  entryPoints: [fileURLToPath(new URL('../src/api.ts', import.meta.url))],
  bundle: true,
  write: false,
  format: 'esm',
  platform: 'node',
});
const {formatTime} = await import(`data:text/javascript,${encodeURIComponent(bundle.outputFiles[0].text)}`);

test('formatTime keeps minutes under an hour and adds hours for long recordings', () => {
  assert.equal(formatTime(90), '01:30.0');
  assert.equal(formatTime(3600), '01:00:00.0');
  assert.equal(formatTime(3661.4), '01:01:01.4');
});
