import test from 'node:test';
import assert from 'node:assert/strict';
import {
  addIntentKey, dashboardContainsAnalysis, decodeAssetError, decodeHttpAnalysisList, decodeHttpDashboard, formatCard,
} from '../src/asset-http.mjs';

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
});
