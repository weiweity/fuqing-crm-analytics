import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizePagePackage } from './package-normalize.mjs';
import { sha256Hex, utf8Bytes } from './bytes.mjs';
import {
  INTERACTIVE_CHART_PACKAGE, LEAK_ATTEMPT_PACKAGE, MAGAZINE_PACKAGE, SAVED_COMPLEX_PACKAGE,
} from '../runtime/fixtures.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const fixturePath = resolve(here, '../../../../../docs/hackathon/free-html-cockpit/fixtures/frozen-contract-v0.json');

test('frozen unbound sample and three complex pages round-trip without dropping CSS/JS/SVG/Canvas', async () => {
  const frozen = JSON.parse(await readFile(fixturePath, 'utf8'));
  const base = await normalizePagePackage(frozen.asset.package);
  assert.equal(base.ok, true, JSON.stringify(base.error));
  assert.match(base.value.html, /data-shine-node="n_title"/);
  assert.match(base.value.html, /canvas/);
  assert.ok(base.value.js.includes('getContext'));

  for (const sample of [SAVED_COMPLEX_PACKAGE, MAGAZINE_PACKAGE, INTERACTIVE_CHART_PACKAGE]) {
    const got = await normalizePagePackage(sample);
    assert.equal(got.ok, true, JSON.stringify(got.error));
    assert.equal(got.value.css.includes(sample.css.trim()) || got.value.css.includes('grid') || got.value.css.length > 0, true);
    assert.ok(got.value.js.length > 0);
    assert.ok(got.value.node_map.length >= 1);
  }
  assert.match((await normalizePagePackage(SAVED_COMPLEX_PACKAGE)).value.html, /<svg/);
  assert.match((await normalizePagePackage(INTERACTIVE_CHART_PACKAGE)).value.js, /getContext/);
});

test('rejects oversized packages, hash mismatch, and static outbound URLs', async () => {
  const huge = await normalizePagePackage({ html: 'x'.repeat(500_000), css: '', js: '', resources: [], node_map: [] });
  assert.equal(huge.ok, false);
  assert.equal(huge.error.code, 'PACKAGE_TOO_LARGE');

  const leak = await normalizePagePackage(LEAK_ATTEMPT_PACKAGE);
  assert.equal(leak.ok, false);
  assert.equal(leak.error.code, 'INVALID_PAGE');
  assert.ok(leak.error.urls?.some((url) => url.includes('example.com')));

  const bytes = utf8Bytes('logo');
  const digest = await sha256Hex(bytes);
  const mismatch = await normalizePagePackage({
    html: '<p data-shine-node="n_x">x</p>',
    css: '',
    js: '',
    resources: [{ resource_id: 'logo_1', type: 'image', sha256: 'ab'.repeat(32), content_base64: Buffer.from(bytes).toString('base64') }],
    node_map: [],
  });
  assert.equal(mismatch.ok, false);
  assert.equal(mismatch.error.code, 'RESOURCE_HASH_MISMATCH');

  const listed = await normalizePagePackage({
    html: '<img data-shine-node="n_img" src="resource:logo_1" alt="">',
    css: '',
    js: '',
    resources: [{ resource_id: 'logo_1', type: 'image', sha256: digest, bytes }],
    node_map: [{ node_id: 'n_img', kind: 'static_element', selector: "[data-shine-node='n_img']" }],
  });
  assert.equal(listed.ok, true, JSON.stringify(listed.error));
});

test('does not use BoardSpec kinds as a generation whitelist', async () => {
  const got = await normalizePagePackage({
    html: '<metric-card class="METRIC" data-shine-node="n_free"><canvas data-shine-region="r_x"></canvas></metric-card>',
    css: 'metric-card{display:block}',
    js: 'customElements.get("metric-card")',
    resources: [],
    node_map: [],
  });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  assert.match(got.value.html, /metric-card/);
  assert.equal(got.value.node_map.some((row) => row.node_id === 'n_free'), true);
});

test('full document head link and script src are rejected, resource: links are kept', async () => {
  const linked = await normalizePagePackage({
    html: '<!doctype html><html><head><link rel="stylesheet" href="https://css.example/a.css"></head><body><p>ok</p></body></html>',
    css: '',
    js: '',
    resources: [],
    node_map: [],
  });
  assert.equal(linked.ok, false);
  assert.equal(linked.error.code, 'INVALID_PAGE');

  const sourced = await normalizePagePackage({
    html: '<!doctype html><html><body><script src="https://js.example/a.js"><\/script><p>ok</p></body></html>',
    css: '',
    js: '',
    resources: [],
    node_map: [],
  });
  assert.equal(sourced.ok, false);
  assert.equal(sourced.error.code, 'INVALID_PAGE');

  const bytes = utf8Bytes('p{color:red}');
  const digest = await sha256Hex(bytes);
  const kept = await normalizePagePackage({
    html: '<!doctype html><html><head><link rel="stylesheet" href="resource:style_1"></head><body><p data-shine-node="n_x">ok</p></body></html>',
    css: '',
    js: '',
    resources: [{ resource_id: 'style_1', type: 'style', sha256: digest, bytes }],
    node_map: [],
  });
  assert.equal(kept.ok, true, JSON.stringify(kept.error));
  assert.match(kept.value.html, /resource:style_1/);
  assert.match(kept.value.html, /data-shine-node="n_x"/);

  const badB64 = await normalizePagePackage({
    html: '<p>x</p>',
    css: '',
    js: '',
    resources: [{ resource_id: 'logo_1', type: 'image', sha256: 'ab'.repeat(32), content_base64: '@@@' }],
    node_map: [],
  });
  assert.equal(badB64.ok, false);
  assert.equal(badB64.error.code, 'INVALID_PAGE');
});

test('failed normalize does not mutate the input object', async () => {
  const raw = { html: '<p>x</p>', css: '', js: "fetch('https://example.com/')", resources: [], node_map: [] };
  const snapshot = JSON.stringify(raw);
  const got = await normalizePagePackage(raw);
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'INVALID_PAGE');
  assert.equal(JSON.stringify(raw), snapshot);
});
