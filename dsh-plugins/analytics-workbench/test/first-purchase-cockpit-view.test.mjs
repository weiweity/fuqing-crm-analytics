import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { COPY, HTTP_API, buildCockpitView } from '../src/first-purchase-cockpit-model.mjs';

const dashboard = {
  schema_version: 'analytics-first-purchase-cockpit/v1',
  dashboard_id: 'dashboard_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  version: 2,
  title: '我的首购驾驶舱',
  owner_id: 'alice',
  visibility: 'PRIVATE',
  cards: [{
    card_id: 'card_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    plugin_ref: { type: 'TABLE', version: 'analytics-visual-table/v1' },
    analysis_ref: { analysis_id: 'analysis_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', version: 1 },
    data_mode: 'SNAPSHOT',
    layout: { x: 0, y: 0, w: 6, h: 4 },
    display_overrides: {},
    filter_mapping: {},
    local_filters: {},
    snapshot: {
      run_id: 'run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      evidence_digest: 'c'.repeat(64),
      resolved_filters: { observation_days: 30, filter_hash: 'b'.repeat(64) },
      data_snapshot_ref: 'synthetic-first-purchase-v1',
      as_of: '2026-08-31T16:00:00.000000+00:00',
    },
    facts: {
      observation_days: 30,
      cohort_mature_count: 9,
      products: [{ finished_conversion_ratio: 0.6, empty_reason: null }],
    },
    filter_hash: 'b'.repeat(64),
    limitations: ['synthetic'],
    effective_spec_hash: 'd'.repeat(64),
    freshness: 'PINNED',
    source_status: 'OK',
  }],
  global_filters: { schema_version: 'analytics-first-purchase-cockpit-filters/v1', channel_ids: [] },
  created_at: '2026-09-08T00:00:00.000000+00:00',
  preview: false,
  persisted: true,
  affected_card_ids: [],
  finite_mock: true,
  http_api: HTTP_API,
};

test('builds first-purchase cockpit board from SNAPSHOT cards', () => {
  const view = buildCockpitView({ dashboard });
  assert.equal(view.kind, 'board');
  assert.equal(view.cards[0].kind, 'ok');
  assert.match(view.cards[0].totals, /正装转化/);
  assert.equal(view.http, COPY.http);
});

test('view source exports FirstPurchaseCockpitView and stays NOT_CONNECTED', () => {
  const path = fileURLToPath(new URL('../src/first-purchase-cockpit-view.tsx', import.meta.url));
  const src = readFileSync(path, 'utf8');
  assert.match(src, /export function FirstPurchaseCockpitView/);
  assert.match(src, /data-testid="analytics-first-purchase-cockpit-view"/);
  assert.match(src, /data-http="NOT_CONNECTED"/);
});
