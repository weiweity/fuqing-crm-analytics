import test from 'node:test';
import assert from 'node:assert/strict';
import {
  addIntentKey, assetRequest, dashboardContainsAnalysis, decodeAssetError, decodeHttpAnalysisList,
  decodeHttpDashboard, formatCard, probeAssetHttp,
} from '../src/asset-http.mjs';

function jsonResponse(status, payload, headers = {}) {
  return {
    status,
    json: async () => payload,
    headers: { get: name => headers[String(name).toLowerCase()] ?? null },
  };
}

async function withFetch(impl, fn) {
  const previous = globalThis.fetch;
  globalThis.fetch = impl;
  try { return await fn(); }
  finally { globalThis.fetch = previous; }
}

test('asset error envelope never treats 500-class payloads as success', () => {
  assert.deepEqual(decodeAssetError({ error: { code: 'UNPROCESSABLE', message: '保存分析缺少合法冻结 SNAPSHOT。' } }),
    { code: 'UNPROCESSABLE', message: '保存分析缺少合法冻结 SNAPSHOT。' });
  assert.equal(decodeAssetError({ facts: { observation_days: 30 } }).code, 'UNAVAILABLE');
});

test('HTTP dashboard decoder requires CONNECTED and keeps UNAVAILABLE cards without facts', () => {
  assert.equal(decodeHttpDashboard({ http_api: 'NOT_CONNECTED', dashboard_id: 'dashboard_1', cards: [] }), null);
  const board = decodeHttpDashboard({
    schema_version: 'analytics-cockpit/v1', http_api: 'CONNECTED', dashboard_id: 'dashboard_1',
    cards: [{ card_id: 'card_1', source_status: 'UNAVAILABLE', error: { code: 'X', message: '板块来源不可用。' }, layout: { x: 0, y: 0, w: 6, h: 4 } }],
  });
  assert.equal(board.dashboard_id, 'dashboard_1');
  const card = formatCard(board.cards[0]);
  assert.equal(card.kind, 'error');
  assert.equal(card.totals, undefined);
});

test('analysis list decoder reads items envelope', () => {
  const item = { analysis_id: 'analysis_1', title: '30 日', version: 1, http_api: 'CONNECTED' };
  assert.deepEqual(
    decodeHttpAnalysisList({ schema_version: 'analytics-saved-analysis/v1', items: [item] }),
    [item],
  );
  assert.deepEqual(decodeHttpAnalysisList({ http_api: 'CONNECTED', items: [{ analysis_id: 'analysis_1', title: '30 日' }] }), []);
  assert.equal(decodeHttpAnalysisList([{ analysis_id: 'analysis_1' }]), null);
});

test('add intent key includes board version so a later add is a new idempotency digest', () => {
  const first = addIntentKey('analysis_1', 1, 1);
  const retry = addIntentKey('analysis_1', 1, 1);
  const nextBoard = addIntentKey('analysis_1', 1, 2);
  assert.equal(first, 'add-analysis_1-v1-b1');
  assert.equal(retry, first);
  assert.notEqual(nextBoard, first);
  assert.equal(addIntentKey('analysis_1', 1, 0), null);
});

test('dashboardContainsAnalysis reads analysis_ref without treating UNAVAILABLE facts as success', () => {
  const payload = {
    cards: [
      { analysis_ref: { analysis_id: 'analysis_1', version: 1 }, source_status: 'OK' },
      { analysis_ref: null, source_status: 'UNAVAILABLE' },
    ],
  };
  assert.equal(dashboardContainsAnalysis(payload, 'analysis_1', 1), true);
  assert.equal(dashboardContainsAnalysis(payload, 'analysis_1', 2), false);
  assert.equal(dashboardContainsAnalysis({ cards: null }, 'analysis_1', 1), false);
  assert.equal(dashboardContainsAnalysis(payload, 1, 1), false);
});

test('assetRequest is same-origin, never sends bearer, and keeps parse failures as null payload', async () => {
  const seen = [];
  await withFetch(async (path, options) => {
    seen.push({ path, options });
    return jsonResponse(200, 'not-an-object', { etag: '3' });
  }, async () => {
    const parsed = await assetRequest('/b0/analyses', { method: 'POST', body: { title: '30 日' }, key: 'save-1', etag: 2 });
    assert.equal(parsed.status, 200);
    assert.equal(parsed.payload, 'not-an-object');
    assert.equal(parsed.etag, '3');
  });
  assert.equal(seen.length, 1);
  assert.equal(seen[0].path, '/b0/analyses');
  assert.equal(seen[0].options.credentials, 'same-origin');
  assert.equal(seen[0].options.cache, 'no-store');
  assert.equal(seen[0].options.redirect, 'error');
  assert.equal(seen[0].options.headers['content-type'], 'application/json');
  assert.equal(seen[0].options.headers['idempotency-key'], 'save-1');
  assert.equal(seen[0].options.headers['if-match'], '2');
  assert.equal(seen[0].options.headers.authorization, undefined);
  await withFetch(async (_path, options) => {
    assert.equal(options.headers['if-match'], undefined);
    assert.equal(options.headers['content-type'], undefined);
    assert.equal(options.body, undefined);
    return { status: 204, json: async () => { throw new SyntaxError('empty'); }, headers: { get: () => null } };
  }, async () => {
    const row = await assetRequest('/b0/assets', { etag: null });
    assert.equal(row.payload, null);
    assert.equal(row.etag, null);
  });
});

test('probeAssetHttp requires CONNECTED cockpit and fails closed on transport errors', async () => {
  await withFetch(async () => jsonResponse(200, { http_api: 'CONNECTED', cockpit: true }), async () => {
    assert.equal(await probeAssetHttp(), true);
  });
  await withFetch(async () => jsonResponse(200, { http_api: 'CONNECTED', analyses: true }), async () => {
    assert.equal(await probeAssetHttp(), false);
  });
  await withFetch(async () => jsonResponse(503, { http_api: 'CONNECTED', cockpit: true }), async () => {
    assert.equal(await probeAssetHttp(), false);
  });
  await withFetch(async () => { throw new Error('offline'); }, async () => {
    assert.equal(await probeAssetHttp(), false);
  });
});

test('formatCard ok path joins channels and keeps a default title without facts leakage on null cards', () => {
  const card = formatCard({
    card_id: 'card_1',
    source_status: 'OK',
    analysis_ref: { analysis_id: 'analysis_1', version: 1 },
    layout: { x: 1, y: 2, w: 4, h: 3 },
    display_overrides: { title: '自定义标题' },
    snapshot: { resolved_filters: { channel_ids: ['A', 'B'] }, as_of: '2026-08-31', run_id: 'run_1' },
    facts: { observation_days: 30, totals: { channel_mature_cohort_count: 2, channel_repeat_count: 1 } },
    limitations: ['synthetic'],
  });
  assert.equal(card.kind, 'ok');
  assert.equal(card.title, '自定义标题');
  assert.equal(card.channels, 'A+B');
  assert.equal(card.days, 30);
  assert.equal(card.run_id, 'run_1');
  const untitled = formatCard({ card_id: 'card_2', source_status: 'OK', layout: { x: 0, y: 0, w: 6, h: 4 }, snapshot: {}, facts: {} });
  assert.equal(untitled.title, '固定历史快照');
  assert.equal(untitled.channels, '');
  const missing = formatCard(null);
  assert.equal(missing.kind, 'error');
  assert.equal(missing.card_id, '');
  assert.deepEqual(missing.layout, { x: 0, y: 0, w: 6, h: 4 });
  assert.equal(missing.message, '该板块来源不可用。');
  for (const card of [
    { card_id: 'card_3', facts: { observation_days: 30, totals: { channel_mature_cohort_count: 9 } } },
    { card_id: 'card_4', source_status: 'PINNED', facts: { observation_days: 30 } },
  ]) {
    const view = formatCard(card);
    assert.equal(view.kind, 'error');
    assert.equal(view.totals, undefined);
    assert.equal(view.days, undefined);
  }
});

test('decode helpers fail closed on empty codes, truncated messages, and incomplete dashboards', () => {
  assert.deepEqual(decodeAssetError({ error: { code: '', message: '' } }), { code: 'UNAVAILABLE', message: '资产请求失败。' });
  const long = 'x'.repeat(201);
  assert.equal(decodeAssetError({ error: { code: 'UNPROCESSABLE', message: long } }).message.length, 200);
  assert.equal(decodeHttpDashboard({ http_api: 'CONNECTED', schema_version: 'analytics-cockpit/v1', cards: [] }), null);
  assert.equal(decodeHttpDashboard({ http_api: 'CONNECTED', schema_version: 'analytics-cockpit/v1', dashboard_id: 'dashboard_1' }), null);
  assert.equal(addIntentKey('', 1, 1), null);
  assert.equal(addIntentKey('analysis_1', 1.5, 1), null);
  assert.equal(decodeHttpAnalysisList({ http_api: 'NOT_CONNECTED', items: [] }), null);
});
