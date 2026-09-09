/** A9 browser/model/capacity: stay NOT_RUN. Do not stub a pass. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const a9Root = join(here, '../../../..');
const evidence = join(
  a9Root,
  'docs/hackathon/parallel-competition-2026-09-09/evidence/A9/fixtures/t01_t17_matrix.json',
);

function cases() {
  return JSON.parse(readFileSync(evidence, 'utf8')).cases;
}

test('T13 real model is NOT_RUN and stub is forbidden', () => {
  const row = cases().find((item) => item.id === 'T13');
  assert.equal(row.requires_real_model, true);
  assert.ok(!process.env.A9_REAL_MODEL);
  const stub = join(a9Root, 'dsh-plugins/analytics-workbench/src/competition-acceptance-runtime.mjs');
  assert.equal(existsSync(stub), false, 'stub runtime must not exist to fake T13');
});

test('T15 browser+model UAT is NOT_RUN', () => {
  const row = cases().find((item) => item.id === 'T15');
  assert.equal(row.requires_browser, true);
  assert.equal(row.requires_real_model, true);
  assert.ok(!process.env.A9_BROWSER_UAT);
});

test('T16 capacity is NOT_RUN and must not start a load run', () => {
  const row = cases().find((item) => item.id === 'T16');
  assert.equal(row.requires_capacity, true);
  assert.ok(!process.env.A9_RUN_CAPACITY);
});

test('T17 native/browser matrix is NOT_RUN without independent DSH', () => {
  const row = cases().find((item) => item.id === 'T17');
  assert.equal(row.requires_browser, true);
  assert.ok(!process.env.A9_INDEPENDENT_DSH);
  for (const key of ['PORT', 'UVICORN_PORT', 'VITE_PORT', 'DSH_PORT']) {
    const value = process.env[key];
    if (value) {
      assert.ok(!['8000', '5173', '4327'].includes(String(value)), `${key}=${value}`);
    }
  }
});
