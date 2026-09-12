import test from 'node:test';
import assert from 'node:assert/strict';
import {
  cancelPatch, confirmPatch, createCanvasState, previousHistoryVersion, rollbackPrevious, rollbackTo,
  selectBlock, setAsk, setTab, stageTitlePatch, visibleBlocks,
} from './canvas-state.mjs';
import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from './fixture.mjs';

function boot() {
  const got = createCanvasState(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  assert.equal(got.ok, true);
  return got.value;
}

test('board tab includes LINK; links tab only LINK; browser is empty', () => {
  const state = boot();
  assert.equal(visibleBlocks(state).some((b) => b.kind === 'LINK'), true);
  const links = setTab(state, 'links');
  assert.equal(links.ok, true);
  assert.ok(visibleBlocks(links.value).every((b) => b.kind === 'LINK'));
  const browser = setTab(state, 'browser');
  assert.equal(visibleBlocks(browser.value).length, 0);
});

test('confirmPatch writes title then rollback restores v1', () => {
  let state = boot();
  state = selectBlock(state, 'b3').value;
  state = setAsk(state, '本月渠道占比').value;
  state = stageTitlePatch(state).value;
  const confirmed = confirmPatch(state);
  assert.equal(confirmed.ok, true);
  assert.equal(confirmed.value.spec.version, 2);
  const titled = confirmed.value.spec.blocks.find((b) => b.block_id === 'b3');
  assert.equal(titled.title, '本月渠道占比');
  const rolled = rollbackTo(confirmed.value, 1);
  assert.equal(rolled.ok, true);
  const original = rolled.value.spec.blocks.find((b) => b.block_id === 'b3');
  assert.equal(original.title, '两期连线');
  assert.equal(rolled.value.spec.version, 1);
});

test('rollbackPrevious restores the last history version not v1', () => {
  let state = boot();
  state = selectBlock(state, 'b3').value;
  state = setAsk(state, '本月渠道占比').value;
  state = confirmPatch(stageTitlePatch(state).value).value;
  state = selectBlock(state, 'b3').value;
  state = setAsk(state, '渠道结构新标题').value;
  state = confirmPatch(stageTitlePatch(state).value).value;
  assert.equal(state.spec.version, 3);
  assert.equal(previousHistoryVersion(state), 2);
  const rolled = rollbackPrevious(state);
  assert.equal(rolled.ok, true);
  assert.equal(rolled.value.spec.version, 2);
  assert.equal(rolled.value.spec.blocks.find((b) => b.block_id === 'b3').title, '本月渠道占比');
  const again = rollbackPrevious(rolled.value);
  assert.equal(again.value.spec.version, 1);
  assert.equal(again.value.spec.blocks.find((b) => b.block_id === 'b3').title, '两期连线');
});

test('confirmPatch without pending is refused', () => {
  const got = confirmPatch(boot());
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'CANVAS_NO_PENDING');
});

test('cancelPatch drops pending without bumping version', () => {
  let state = boot();
  state = selectBlock(state, 'b3').value;
  state = setAsk(state, '本月渠道占比').value;
  const staged = stageTitlePatch(state);
  const cancelled = cancelPatch(staged.value);
  assert.equal(cancelled.ok, true);
  assert.equal(cancelled.value.pending_patch, null);
  assert.equal(cancelled.value.spec.version, 1);
});

test('stageTitlePatch refuses empty ask', () => {
  let state = boot();
  state = selectBlock(state, 'b1').value;
  const got = stageTitlePatch(state);
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'PATCH_TITLE');
});

test('illegal tab, missing block, invalid spec, and empty rollback are refused', () => {
  const invalid = createCanvasState({ board_id: 'x', version: 1, blocks: [{ block_id: 'z', kind: 'PIE' }] });
  assert.equal(invalid.ok, false);
  assert.equal(invalid.error.code, 'SPEC_KIND');
  const state = boot();
  assert.equal(setTab(state, 'sql').error.code, 'CANVAS_TAB');
  assert.equal(selectBlock(state, 'nope').error.code, 'CANVAS_SELECT');
  assert.equal(rollbackTo(state, 9).error.code, 'ROLLBACK_MISSING');
  assert.equal(rollbackTo(state, 0).error.code, 'ROLLBACK_VERSION');
  assert.equal(rollbackPrevious(state).error.code, 'ROLLBACK_MISSING');
  assert.equal(previousHistoryVersion(state), null);
  assert.equal(setAsk(state, /** @type {any} */ (1)).value.ask, '');
});
