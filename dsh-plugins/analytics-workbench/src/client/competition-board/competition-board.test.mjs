import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import {
  BOARD_CONFLICT, BOARD_EMPTY, BOARD_FORBIDDEN, BOARD_PARTIAL, BOARD_SUCCESS,
  C0_CONTRACT_HASH, RESULT_EMPTY, RESULT_SUCCESS,
} from './c0-fixtures.mjs';
import {
  canEndorse, conditionChips, decodeCompetitionBoardSpec, decodeCompetitionError, decodeCompetitionPatchRequest,
  decodeCompetitionResultRef, formatResultRowCount, looksLikeIllegalScript, toEndorsedResultRef,
} from './decode.mjs';
import { applyLayoutAction, clampLayout, matchLayoutKeyboard } from './layout.mjs';
import {
  beginInflight, endInflight, getInflight, getPatchTarget, getUiSelection, resetInflightForTests, setUiSelection,
} from './selection.mjs';
import { createFixtureBoardTransport } from './transport.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../../../../../');
const fixtures = join(repo, 'docs/hackathon/parallel-competition-2026-09-09/contracts/fixtures');

async function json(rel) {
  return JSON.parse(await readFile(join(fixtures, rel), 'utf8'));
}

test('embedded board/result fixtures match frozen C0 JSON', async () => {
  assert.deepEqual(BOARD_SUCCESS, await json('board/success.json'));
  assert.deepEqual(BOARD_EMPTY, await json('board/empty.json'));
  assert.deepEqual(BOARD_PARTIAL, await json('board/partial_success.json'));
  assert.deepEqual(BOARD_CONFLICT, await json('board/conflict_409.json'));
  assert.deepEqual(BOARD_FORBIDDEN, await json('board/permission_denied.json'));
  assert.deepEqual(RESULT_SUCCESS, await json('result/success.json'));
  assert.deepEqual(RESULT_EMPTY, await json('result/empty.json'));
  const manifest = JSON.parse(await readFile(join(repo, 'docs/hackathon/parallel-competition-2026-09-09/contracts/C0-MANIFEST.json'), 'utf8'));
  assert.equal(manifest.contract_hash, C0_CONTRACT_HASH);
});

test('C0 board decode rejects PUBLIC visibility and accepts empty boards', () => {
  assert.equal(decodeCompetitionBoardSpec(BOARD_SUCCESS.board)?.board_id, 'dash_c0_board_a');
  assert.equal(decodeCompetitionBoardSpec(BOARD_EMPTY)?.block_ids.length, 0);
  const bad = { ...BOARD_SUCCESS.board, visibility: 'PUBLIC' };
  assert.equal(decodeCompetitionBoardSpec(bad), null);
  assert.equal(canEndorse(RESULT_SUCCESS), true);
  assert.equal(canEndorse(RESULT_EMPTY), false);
  assert.equal(toEndorsedResultRef(RESULT_EMPTY), null);
  assert.equal(toEndorsedResultRef(RESULT_SUCCESS)?.completeness, 'COMPLETE');
});

test('illegal HTML/JS patches are rejected before transport', () => {
  assert.equal(looksLikeIllegalScript({ html: '<script>bad()</script>' }), true);
  assert.equal(decodeCompetitionPatchRequest({
    ...BOARD_SUCCESS.patch,
    display_op: { op: 'display', card_id: 'card_c0_block_1', display_overrides: { title: '<script>x</script>' } },
  }), null);
  assert.ok(decodeCompetitionPatchRequest(BOARD_SUCCESS.patch));
  assert.equal(decodeCompetitionPatchRequest({ ...BOARD_SUCCESS.patch, intent: 'FILTER_CHANGE' }), null);
});

test('UI selection does not rewrite in-flight patch target', () => {
  resetInflightForTests();
  setUiSelection({ board_id: 'dash_a', block_id: 'card_a', base_version: 4 });
  beginInflight({ board_id: 'dash_a', block_id: 'card_a', base_version: 4, attempt_id: 'attempt_1' });
  setUiSelection({ board_id: 'dash_a', block_id: 'card_b', base_version: 4 });
  assert.equal(getUiSelection().block_id, 'card_b');
  assert.equal(getPatchTarget().block_id, 'card_a');
  assert.equal(getInflight('attempt_1').block_id, 'card_a');
  endInflight('attempt_1');
  assert.equal(getPatchTarget().block_id, 'card_b');
  resetInflightForTests();
});

test('layout clamp and keyboard substitutes match overlay bounds', () => {
  assert.deepEqual(clampLayout({ x: 0, y: 0, w: 6, h: 4 }, { x: -2, w: 99 }), { x: 0, y: 0, w: 12, h: 4 });
  assert.equal(matchLayoutKeyboard({ key: 'ArrowLeft', altKey: true, shiftKey: false }), 'left');
  assert.equal(matchLayoutKeyboard({ key: 'ArrowRight', altKey: true, shiftKey: true }), 'wider');
  assert.equal(matchLayoutKeyboard({ key: 'ArrowLeft', altKey: false, shiftKey: false }), null);
  const moved = applyLayoutAction({ x: 2, y: 0, w: 6, h: 4 }, 'left');
  assert.equal(moved.x, 1);
});

test('fixture transport covers endorse, partial batch, style preview, 409, 403', async () => {
  const success = createFixtureBoardTransport({ scenario: 'success' });
  const listed = await success.listEndorseableResults();
  assert.equal(listed.ok, true);
  assert.equal(listed.body[0].result_id, 'result_c0_gsv_20260831');
  const batch = await success.applyBatch(success.principal, BOARD_SUCCESS.batch, { 'Idempotency-Key': 'board-create-a' });
  assert.equal(batch.ok, true);
  assert.equal(batch.body.receipt.status, 'SUCCEEDED');
  const replay = await success.applyBatch(success.principal, BOARD_SUCCESS.batch, { 'Idempotency-Key': 'board-create-a' });
  assert.equal(replay.body.receipt.status, 'SUCCEEDED');
  const changed = { ...BOARD_SUCCESS.batch, operations: [{ ...BOARD_SUCCESS.batch.operations[0], title: 'other' }] };
  const conflictKey = await success.applyBatch(success.principal, changed, { 'Idempotency-Key': 'board-create-a' });
  assert.equal(conflictKey.status, 409);

  const preview = await success.previewPatch(success.principal, BOARD_SUCCESS.patch);
  assert.equal(preview.ok, true);
  assert.equal(preview.body.preview, true);
  const saved = await success.applyPatch(success.principal, BOARD_SUCCESS.patch, { 'If-Match': String(success.getSavedBoard().version) });
  assert.equal(saved.ok, true);
  assert.equal(saved.body.persisted, true);

  const partial = createFixtureBoardTransport({ scenario: 'partial_success' });
  const part = await partial.previewBatch(partial.principal, {
    ...BOARD_SUCCESS.batch, batch_id: 'batch_c0_multi', layout_mode: 'BATCH_MULTI_BOARD',
    operations: [
      BOARD_SUCCESS.batch.operations[0],
      { ...BOARD_SUCCESS.batch.operations[0], operation_id: 'op_c0_board_b', idempotency_key: 'board-create-b', title: 'B' },
    ],
  });
  assert.equal(part.body.receipt.status, 'PARTIAL');
  assert.equal(part.body.receipt.items[1].status, 'FAILED');

  const denied = createFixtureBoardTransport({ scenario: 'permission_denied' });
  assert.equal((await denied.loadBoard('dash_c0_board_a')).status, 403);
  const conflict = createFixtureBoardTransport({ scenario: 'conflict_409' });
  await conflict.previewPatch(conflict.principal, BOARD_SUCCESS.patch);
  const row = await conflict.applyPatch(conflict.principal, BOARD_SUCCESS.patch, { 'If-Match': '4' });
  assert.equal(row.status, 409);
  assert.equal(decodeCompetitionError(row.body).http_status, 409);
  assert.ok(conflict.getPendingPatch());
});

test('FILTER_CHANGE and empty result stay honest', async () => {
  const transport = createFixtureBoardTransport();
  const filter = await transport.previewPatch(transport.principal, {
    ...BOARD_SUCCESS.patch,
    intent: 'FILTER_CHANGE',
    display_op: null,
    filter_change: { op: 'filter_change', card_id: 'card_c0_block_1', local_filters: { channel_ids: ['A'] } },
  });
  assert.equal(filter.ok, false);
  assert.equal(filter.body.error.code, 'NOT_CONNECTED');
  assert.equal(decodeCompetitionResultRef(RESULT_EMPTY).empty_reason, 'NO_CURRENT_MONTH_DATA');
  assert.equal(RESULT_EMPTY.completeness, 'EMPTY');
});

test('formatResultRowCount never renders undefined; sparse confirm chips do not throw', () => {
  assert.equal(formatResultRowCount(RESULT_SUCCESS), '2');
  assert.equal(formatResultRowCount(RESULT_EMPTY), '—');
  assert.equal(formatResultRowCount({ completeness: 'COMPLETE', page: { total: 7 } }), '7');
  assert.equal(formatResultRowCount({ completeness: 'COMPLETE' }), '—');
  assert.equal(formatResultRowCount(null), '—');
  const sparse = {
    completeness: 'COMPLETE',
    resolved_condition: { metric_type: 'GSV', timezone: 'Asia/Shanghai' },
  };
  const chips = conditionChips(sparse);
  assert.equal(chips.find(row => row.id === 'cutoff').value, '—');
  assert.equal(chips.find(row => row.id === 'sample').value, '—');
  assert.equal(chips.find(row => row.id === 'current').value, '—');
  assert.ok(chips.every(row => row.value !== 'undefined' && !String(row.value).includes('undefined')));
});

test('board UI source covers endorsement, grid, scope chat, 409 and keyboard substitutes', async () => {
  const src = await readFile(join(here, 'BoardWorkbench.tsx'), 'utf8');
  for (const token of [
    'sm-endorsement', 'sm-confirm-summary', 'ONE_BOARD_MULTI_BLOCK', 'BATCH_MULTI_BOARD',
    'sm-board-grid', 'sm-scope-chat', '只改此板块', '切换为整板', 'sm-leave-restore',
    'pointerup', 'pointermove', 'STYLE_ONLY', 'FILTER_CHANGE', '版本冲突（409）',
    'ThemeProvider', 'LayoutSlot', 'ErrorState', 'EvidenceBlock', 'formatResultRowCount',
  ]) assert.match(src, new RegExp(token));
  assert.match(src, /window\.addEventListener\('pointerup', finish\)/);
  assert.doesNotMatch(src, /onPointerMove=\{/);
  assert.doesNotMatch(src, /from 'antd'|from "antd"/);
  assert.doesNotMatch(src, /react-grid-layout/);
  const mount = await readFile(join(here, 'mount.ts'), 'utf8');
  assert.match(mount, /export function mount/);
  assert.match(mount, /dispose/);
  assert.match(mount, /createRoot/);
});
