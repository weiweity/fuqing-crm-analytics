import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  AI_INTENTS, COCKPIT_KEYBOARD, COPY, HTTP_API, buildCockpitView, decodeCockpit,
  decodeCockpitCard, isB0BusinessFixture, matchCockpitKeyboard, renderCockpitHtml,
} from '../src/cockpit-model.mjs';

const analysisId = 'analysis_' + 'a'.repeat(32);
const counts = {
  channel_mature_cohort_count: 2,
  channel_immature_count: 0,
  channel_repeat_count: 1,
  channel_cross_channel_count: 0,
  channel_repeat_ratio: 0.5,
  channel_cross_channel_ratio: 0,
  channel_window_net_paid_minor: 100,
  channel_empty_reason: null,
};
const resolved = {
  schema_version: 'analytics-channel-followup/v1',
  query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1',
  metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1',
  data_version: 'synthetic-channel-followup-data/v1',
  hash_version: 'channel-followup-filter-hash/v1',
  cohort_window_kind: 'FIXED',
  resolved_cohort_start: '2026-05-31T16:00:00.000000+00:00',
  resolved_cohort_end: '2026-08-31T16:00:00.000000+00:00',
  observation_days: 30,
  data_snapshot_ref: 'synthetic-channel-followup-v1',
  as_of: '2026-08-31T16:00:00.000000+00:00',
  timezone: 'Asia/Shanghai',
  channel_ids: ['A'],
  cohort_ref: null,
  product_ids: [],
  exclude_low_price: false,
  comparison: null,
  permission_scope: 'scope_1',
  data_digest: 'a'.repeat(64),
  filter_hash: 'b'.repeat(64),
};
const card = {
  card_id: 'card_' + 'a'.repeat(32),
  plugin_ref: { type: 'TABLE', version: 'analytics-visual-table/v1' },
  analysis_ref: { analysis_id: analysisId, version: 1 },
  data_mode: 'SNAPSHOT',
  layout: { x: 0, y: 0, w: 6, h: 4 },
  display_overrides: {},
  filter_mapping: {},
  local_filters: {},
  snapshot: {
    run_id: 'run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    evidence_digest: 'c'.repeat(64),
    resolved_filters: resolved,
    data_snapshot_ref: 'synthetic-channel-followup-v1',
    as_of: resolved.as_of,
  },
  facts: {
    display_name: '首次观察到的渠道 / N日二单率',
    currency: 'CNY', amount_unit: 'minor', amount_precision: 'integer_fen',
    observation_days: 30,
    channels: [{ channel_id: 'A', ...counts }],
    totals: counts,
  },
  filter_hash: resolved.filter_hash,
  limitations: ['finite mock: SNAPSHOT facts are displayed as supplied; not a live compute.'],
  effective_spec_hash: 'd'.repeat(64),
  freshness: 'PINNED',
};
const secondCard = {
  ...card,
  card_id: 'card_' + 'b'.repeat(32),
  layout: { x: 6, y: 0, w: 6, h: 4 },
};
const dashboard = {
  schema_version: 'analytics-cockpit/v1',
  dashboard_id: 'dashboard_' + 'a'.repeat(32),
  version: 2,
  title: '我的驾驶舱',
  owner_id: 'alice',
  visibility: 'PRIVATE',
  cards: [card, secondCard],
  global_filters: { schema_version: 'analytics-cockpit-filters/v1', channel_ids: [] },
  created_at: '2027-01-15T08:00:00.000000+00:00',
  preview: false,
  persisted: true,
  affected_card_ids: [],
  finite_mock: true,
  http_api: HTTP_API,
};
const b0 = {
  schema_version: 'analytics-b0/v1',
  customers: 100,
  repeat_customers: 25,
  repeat_rate: 0.25,
};

test('cockpit decodes SNAPSHOT facts without a session and does not recompute ratios', () => {
  const decoded = decodeCockpit(dashboard);
  assert.equal(decoded.cards[0].ok, true);
  assert.equal(decoded.cards[0].card.data_mode, 'SNAPSHOT');
  assert.equal(decoded.cards[0].card.snapshot.run_id, card.snapshot.run_id);
  const view = buildCockpitView({ dashboard, sessionId: null, modelAvailable: false });
  assert.equal(view.sessionRequired, false);
  assert.equal(view.modelRequired, false);
  assert.equal(view.httpConnected, false);
  assert.equal(view.kind, 'board');
  assert.match(view.cards[0].totals, /50%/);
  assert.doesNotMatch(view.cards[0].totals, /25%/);
  const html = renderCockpitHtml(view);
  assert.match(html, /历史快照/);
  assert.match(html, /无活动会话/);
  assert.match(html, /data-session=""/);
  assert.match(html, /data-model="0"/);
  assert.match(html, /data-http="NOT_CONNECTED"/);
  assert.match(html, /data-keyboard-add="Alt\+A"/);
  assert.match(html, /data-keyboard-copy="Alt\+D"/);
  assert.match(html, /data-keyboard-remove="Alt\+Backspace"/);
  assert.doesNotMatch(html, /25%/);
});

test('one broken card is isolated from the other card', () => {
  const broken = { ...dashboard, cards: [card, { ...secondCard, extra: true, facts: { repeat_rate: 0.25 } }] };
  const decoded = decodeCockpit(broken);
  assert.equal(decoded.cards[0].ok, true);
  assert.equal(decoded.cards[1].ok, false);
  const html = renderCockpitHtml(buildCockpitView({ dashboard: broken }));
  assert.match(html, /data-card-id="card_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/);
  assert.match(html, /data-card-error="1"/);
  assert.match(html, /其他板块不受影响/);
  assert.match(html, /50%/);
  assert.doesNotMatch(html, /25%/);
});

test('finite mock AI preview highlights only the target card and does not persist', () => {
  const preview = {
    ...dashboard,
    preview: true,
    persisted: false,
    affected_card_ids: [card.card_id],
    cards: [{
      ...card,
      display_overrides: { title: AI_INTENTS['annotate-live'].display_overrides.title },
      local_filters: { channel_ids: ['A'] },
    }, secondCard],
  };
  const view = buildCockpitView({ dashboard: preview });
  assert.equal(view.preview, true);
  assert.equal(view.persisted, false);
  assert.equal(view.cards[0].affected, true);
  assert.equal(view.cards[1].affected, false);
  assert.equal(view.cards[0].title, '直播渠道快照');
  assert.equal(view.cards[1].title, COPY.snapshot);
  assert.match(view.cards[0].localFilterNote, /未重算/);
  const html = renderCockpitHtml(view);
  assert.match(html, /预览未保存/);
  assert.match(html, /data-affected="1"/);
  assert.match(html, /data-preview="1"/);
  assert.doesNotMatch(html, /disabled/);
});

test('keyboard bindings match add/copy/remove and are documented constants', () => {
  assert.equal(matchCockpitKeyboard({ key: 'a', altKey: true, shiftKey: false }), 'add');
  assert.equal(matchCockpitKeyboard({ key: 'd', altKey: true, shiftKey: false }), 'copy');
  assert.equal(matchCockpitKeyboard({ key: 'Backspace', altKey: true, shiftKey: false }), 'remove');
  assert.equal(matchCockpitKeyboard({ key: 'a', altKey: false, shiftKey: false }), null);
  assert.equal(COCKPIT_KEYBOARD.add.shortcut, 'Alt+A');
  assert.equal(COCKPIT_KEYBOARD.copy.shortcut, 'Alt+D');
  assert.equal(COCKPIT_KEYBOARD.remove.shortcut, 'Alt+Backspace');
});

test('B0 25% fixture and extra fields are rejected without poisoning other cards', () => {
  assert.equal(isB0BusinessFixture(b0), true);
  assert.equal(decodeCockpit(b0), null);
  assert.equal(decodeCockpitCard({ ...card, facts: { ...card.facts, repeat_rate: 0.25 } }), null);
  const html = renderCockpitHtml(buildCockpitView({ dashboard: b0 }));
  assert.match(html, /无法识别/);
  assert.doesNotMatch(html, /25%/);
});

test('empty cockpit and unauthorized views do not require a live session or model', () => {
  const empty = buildCockpitView({ list: [], sessionId: null, modelAvailable: false });
  assert.equal(empty.kind, 'empty');
  assert.match(renderCockpitHtml(empty), /从已保存分析添加/);
  const unauthorized = buildCockpitView({
    error: { status: 404, code: 'NOT_FOUND', message: '驾驶舱不存在或当前身份不可见。' },
    sessionId: null,
    modelAvailable: false,
  });
  assert.equal(unauthorized.kind, 'error');
  assert.equal(unauthorized.sessionRequired, false);
  assert.match(renderCockpitHtml(unauthorized), /驾驶舱不存在或当前身份不可见/);
  const conflict = buildCockpitView({ error: { status: 409, code: 'CONFLICT', message: '冲突' } });
  assert.match(renderCockpitHtml(conflict), /请读取当前驾驶舱后核对/);
});

test('view source is a sessionless renderer and does not compute business metrics', () => {
  const path = fileURLToPath(new URL('../src/cockpit-view.tsx', import.meta.url));
  const src = readFileSync(path, 'utf8');
  assert.match(src, /export function CockpitView/);
  assert.match(src, /data-testid="analytics-cockpit-view"/);
  assert.match(src, /buildCockpitView/);
  assert.match(src, /data-keyboard-add/);
  assert.match(src, /data-action="copy"/);
  assert.match(src, /data-action="remove"/);
  assert.match(src, /data-action="add"/);
  assert.doesNotMatch(src, /fetch\(|repeat_rate|analytics-run-b0|25%/);
  assert.doesNotMatch(src, /channel_repeat_count\s*\//);
  assert.match(src, /sessionId \?\? null/);
  assert.match(src, /modelAvailable === true/);
});
