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
const {formatTime, parseApiResponse} = await import(`data:text/javascript,${encodeURIComponent(bundle.outputFiles[0].text)}`);

test('formatTime keeps minutes under an hour and adds hours for long recordings', () => {
  assert.equal(formatTime(90), '01:30.0');
  assert.equal(formatTime(3600), '01:00:00.0');
  assert.equal(formatTime(3661.4), '01:01:01.4');
});

test('parseApiResponse reports plain-text server errors without a JSON parse failure', async () => {
  const response = new Response('Internal Server Error', {status: 500, statusText: 'Internal Server Error'});
  await assert.rejects(parseApiResponse(response), /Internal Server Error/);
});

test('parseApiResponse formats FastAPI validation error arrays', async () => {
  const response = new Response(JSON.stringify({detail: [
    {loc: ['body', 'confidence'], msg: 'Input should be less than or equal to 0.95', type: 'less_than_equal'},
  ]}), {status: 422, headers: {'Content-Type': 'application/json'}});
  await assert.rejects(parseApiResponse(response), /confidence: Input should be less than or equal to 0.95/);
});

test('parseApiResponse does not leak HTML error pages', async () => {
  const response = new Response('<html><body>Bad Gateway</body></html>', {
    status: 502, statusText: 'Bad Gateway', headers: {'Content-Type': 'text/html'},
  });
  await assert.rejects(parseApiResponse(response), /^Error: Bad Gateway$/);
});

test('parseApiResponse returns parsed success payloads', async () => {
  const response = new Response(JSON.stringify({ok: true}), {status: 200, headers: {'Content-Type': 'application/json'}});
  assert.deepEqual(await parseApiResponse(response), {ok: true});
});
