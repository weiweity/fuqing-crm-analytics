import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { brandAssets } from './brand-assets.mjs';
import { BOARD_SAMPLE, BOARD_SAMPLE_PATH, resolveBoardSample, boardSampleHtml } from './board-sample.mjs';
const root = fileURLToPath(new URL('../..', import.meta.url));

test('original logo and cropped favicon match the approved bytes', async () => {
  const assets = await brandAssets(root);
  assert.deepEqual([...assets.keys()], ['/b0/brand/logo.png', '/favicon.svg']);
  const logo = assets.get('/b0/brand/logo.png').bytes;
  assert.equal(logo.readUInt32BE(16), 249); assert.equal(logo.readUInt32BE(20), 45);
  assert.ok(assets.get('/favicon.svg').bytes.toString().includes(logo.toString('base64')));
});
test('complete condition envelope survives transport with empty, false and null preserved', () => {
  const roundtrip = JSON.parse(JSON.stringify(resolveBoardSample(BOARD_SAMPLE_PATH)));
  assert.deepEqual(roundtrip, BOARD_SAMPLE);
  roundtrip.filters.observation_days = 30;
  assert.equal(resolveBoardSample(BOARD_SAMPLE_PATH).filters.observation_days, 90);
  assert.deepEqual(BOARD_SAMPLE.filters.product_ids, []);
  assert.equal(BOARD_SAMPLE.filters.exclude_low_price, false);
  assert.equal(BOARD_SAMPLE.facts, null);
});
test('sample reference rejects old filters, snapshots, duplicated refs and arbitrary return URLs', () => {
  for (const path of ['/audience?channel=a', '/b0/board-sample', BOARD_SAMPLE_PATH + '&channel=old',
    BOARD_SAMPLE_PATH + '&ref=other', BOARD_SAMPLE_PATH + '&return=https://example.com',
    BOARD_SAMPLE_PATH.replace('b0-condition', '%62%30-condition'), '/b0/board-sample?ref=other']) {
    assert.equal(resolveBoardSample(path), null, path);
  }
});
test('isolated specimen has no executable script, old router or dynamic destination', async () => {
  const html = boardSampleHtml();
  assert.doesNotMatch(html, /<script|localStorage|sessionStorage|<iframe|onclick=/i);
  assert.ok(html.includes('href="/"')); assert.ok(html.includes('NOT_EXECUTED'));
  // Document the actual old seam; this does not claim the old app was fixed.
  const app = await readFile(resolve(root, 'frontend-vue3/src/App.vue'), 'utf8');
  assert.match(app, /useFilterSync\(\)/);
  const legacy = await readFile(resolve(root, 'frontend-vue3/src/composables/useFilterSync.ts'), 'utf8');
  assert.match(legacy, /router\.replace\(\{\s*query:\s*\{/);
});
