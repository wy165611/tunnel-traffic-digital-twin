import assert from 'node:assert/strict';
import {test} from 'node:test';
import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';

const bundle = await build({
  entryPoints: [fileURLToPath(new URL('../src/utils/canvasShape.ts', import.meta.url))],
  bundle: true,
  write: false,
  format: 'esm',
  platform: 'node',
});
const {roundedRectPath} = await import(`data:text/javascript,${encodeURIComponent(bundle.outputFiles[0].text)}`);

test('roundedRectPath uses roundRect when the browser supports it', () => {
  const calls = [];
  const ctx = {
    roundRect: (...args) => calls.push(['roundRect', ...args]),
    rect: (...args) => calls.push(['rect', ...args]),
  };
  roundedRectPath(ctx, 1, 2, 3, 4, 5);
  assert.deepEqual(calls, [['roundRect', 1, 2, 3, 4, 5]]);
});

test('roundedRectPath falls back to rect on older canvas implementations', () => {
  const calls = [];
  const ctx = {rect: (...args) => calls.push(args)};
  roundedRectPath(ctx, 1, 2, 3, 4, 5);
  assert.deepEqual(calls, [[1, 2, 3, 4]]);
});
