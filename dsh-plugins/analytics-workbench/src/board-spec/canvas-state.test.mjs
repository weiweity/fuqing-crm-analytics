import test from 'node:test';
import assert from 'node:assert/strict';
import {
  cancelPatch, confirmPatch, createCanvasState, rollbackTo, selectBlock, setAsk, setTab, stageTitlePatch,
  visibleBlocks,
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
