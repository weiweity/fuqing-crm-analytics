/**
 * T25 (D44) — one leave coordinator for every entry point.
 *
 * Every leaving entry (library asset switch, return-to-conversation, the DSH
 * global panel, a session switch, closing the cockpit) submits the same intent
 * transaction. These tests drive the transaction directly, with injected
 * dependencies, so each of the three choices and every failure branch is
 * covered without a browser.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createLeaveCoordinator, LEAVE_CHOICES } from './leave-coordinator.mjs';
import { librarySnapshot as snap, libraryPreview as draft } from '../../../test/helpers/library-board-fixtures.mjs';

/** A coordinator wired to recording fakes; `state` is mutated by the test. */
function harness(overrides = {}) {
  let state = { preview: null, layoutDraft: null, confirmationUncertain: false, editContext: null, saved: null };
  const log = [];
  let epoch = 0;
  const coordinator = createLeaveCoordinator({
    snapshot: () => state,
    beginEpoch: kind => { log.push(`epoch:${kind}`); return { epoch: ++epoch, kind, signal: new AbortController().signal, abort() {} }; },
    save: async () => { log.push('save'); return overrides.save ?? { ok: true }; },
    discard: async () => { log.push('discard'); return overrides.discard ?? { ok: true }; },
    navigate: async intent => { log.push(`navigate:${intent.kind}`); if (overrides.navigate) return overrides.navigate(intent); },
  });
  return { coordinator, log, set: next => { state = { ...state, ...next }; }, get: () => state };
}

test('the three choices are exactly the approved ones', () => {
  assert.deepEqual([...LEAVE_CHOICES], ['save_and_leave', 'discard', 'stay']);
});

test('a clean page — including a fresh selection — navigates immediately without prompting', async () => {
  const h = harness();
  h.set({ editContext: { edit_context_id: 'edit_ctx', block_id: 'note' } });
  assert.equal(await h.coordinator.request({ kind: 'library', id: 'board_other' }), 'navigated');
  assert.deepEqual(h.log, ['epoch:library', 'navigate:library'], 'a clean selection does not save, discard or prompt');
  assert.equal(h.coordinator.getSnapshot().status, 'idle');
});

test('real unsaved work prompts with the reasons that triggered it', async () => {
  const h = harness();
  h.set({ preview: draft() });
  assert.equal(await h.coordinator.request({ kind: 'panel', id: null }), 'prompt');
  const state = h.coordinator.getSnapshot();
  assert.equal(state.status, 'prompting');
  assert.deepEqual(state.reasons, ['pending_patch_preview']);
  assert.deepEqual(h.log, ['epoch:panel'], 'prompting performs no save, discard or navigation');
});

test('save_and_leave navigates once, and only after a matching receipt', async () => {
  const h = harness();
  h.set({ preview: draft() });
  await h.coordinator.request({ kind: 'conversation' });
  assert.equal(await h.coordinator.choose('save_and_leave'), 'navigated');
  assert.deepEqual(h.log, ['epoch:conversation', 'save', 'navigate:conversation']);
  assert.equal(h.coordinator.getSnapshot().status, 'idle');
});

test('a failed, conflicting or unknown save stays on the page with the draft', async () => {
  for (const reason of ['uncertain', 'conflict', 'version_mismatch', 'forbidden']) {
    const h = harness({ save: { ok: false, reason } });
    h.set({ preview: draft() });
    await h.coordinator.request({ kind: 'close' });
    assert.equal(await h.coordinator.choose('save_and_leave'), 'stayed', `${reason} must not navigate`);
    assert.equal(h.log.includes('navigate:close'), false, `${reason} must not navigate`);
    assert.equal(h.coordinator.getSnapshot().status, 'prompting', `${reason} keeps the prompt recoverable`);
    assert.match(h.coordinator.getSnapshot().message, /保留草稿|留在当前页/);
  }
});

test('discard drops the draft then navigates once', async () => {
  const h = harness();
  h.set({ preview: draft() });
  await h.coordinator.request({ kind: 'library', id: 'board_other' });
  assert.equal(await h.coordinator.choose('discard'), 'navigated');
  assert.deepEqual(h.log, ['epoch:library', 'discard', 'navigate:library']);
});

test('a discard whose receipt is missing keeps the draft and stays', async () => {
  const h = harness({ discard: { ok: false, message: '未取得取消回执，保留当前草稿。' } });
  h.set({ preview: draft() });
  await h.coordinator.request({ kind: 'library', id: 'board_other' });
  assert.equal(await h.coordinator.choose('discard'), 'stayed');
  assert.equal(h.log.includes('navigate:library'), false);
  assert.equal(h.coordinator.getSnapshot().status, 'prompting');
  assert.match(h.coordinator.getSnapshot().message, /保留当前草稿/);
});

test('stay performs neither save nor discard and does not navigate', async () => {
  const h = harness();
  h.set({ preview: draft() });
  await h.coordinator.request({ kind: 'session', sessionId: 's2' });
  assert.equal(await h.coordinator.choose('stay'), 'stayed');
  assert.deepEqual(h.log, ['epoch:session'], 'stay is a pure local decision');
  assert.equal(h.coordinator.getSnapshot().status, 'idle');
});

test('Esc / the visible cancel (stay) matches the stay choice', async () => {
  const h = harness();
  h.set({ layoutDraft: snap() });
  await h.coordinator.request({ kind: 'panel', id: null });
  assert.equal(h.coordinator.getSnapshot().status, 'prompting');
  h.coordinator.stay();
  assert.equal(h.coordinator.getSnapshot().status, 'idle');
  assert.equal(h.coordinator.getSnapshot().intent, null);
  assert.equal(h.log.includes('navigate:panel'), false);
});

test('a repeat click while an intent is in flight never queues a second navigation', async () => {
  let release;
  const saving = new Promise(resolve => { release = resolve; });
  const h = harness({ save: undefined });
  h.set({ preview: draft() });
  const coordinator = createLeaveCoordinator({
    snapshot: () => h.get(),
    beginEpoch: kind => ({ epoch: 1, kind, signal: new AbortController().signal, abort() {} }),
    save: async () => { h.log.push('save'); await saving; return { ok: true }; },
    discard: async () => ({ ok: true }),
    navigate: async intent => { h.log.push(`navigate:${intent.kind}`); },
  });
  await coordinator.request({ kind: 'library', id: 'board_a' });
  const first = coordinator.choose('save_and_leave');
  // Three impatient clicks while the save is still running.
  assert.equal(await coordinator.request({ kind: 'library', id: 'board_b' }), 'busy');
  assert.equal(await coordinator.choose('discard'), 'stayed');
  assert.equal(await coordinator.choose('save_and_leave'), 'stayed');
  release();
  assert.equal(await first, 'navigated');
  assert.deepEqual(h.log.filter(entry => entry.startsWith('navigate:')), ['navigate:library'],
    'the original navigation happens exactly once');
  coordinator.dispose();
});

test('the original navigation is performed at most once even if resolution runs twice', async () => {
  const h = harness();
  h.set({ preview: draft() });
  await h.coordinator.request({ kind: 'library', id: 'board_a' });
  const [first, second] = await Promise.all([h.coordinator.choose('discard'), h.coordinator.choose('discard')]);
  assert.equal([first, second].filter(result => result === 'navigated').length, 1);
  assert.equal(h.log.filter(entry => entry === 'navigate:library').length, 1);
});

test('a host that refuses the navigation stays, with the draft still on the page', async () => {
  const h = harness({ navigate: () => { throw new Error('宿主拒绝了这次导航。'); } });
  h.set({ preview: draft() });
  await h.coordinator.request({ kind: 'close' });
  assert.equal(await h.coordinator.choose('discard'), 'stayed');
  assert.equal(h.coordinator.getSnapshot().status, 'prompting');
  assert.match(h.coordinator.getSnapshot().message, /宿主拒绝/);
  assert.equal(h.log.includes('navigate:close'), true, 'the navigation was attempted once and failed');
});

test('every entry point uses the same transaction', async () => {
  for (const entry of ['library', 'conversation', 'panel', 'session', 'close']) {
    const h = harness();
    h.set({ preview: draft() });
    assert.equal(await h.coordinator.request({ kind: entry }), 'prompt', `${entry} must prompt on a real draft`);
    assert.equal(await h.coordinator.choose('stay'), 'stayed');
    const clean = harness();
    assert.equal(await clean.coordinator.request({ kind: entry }), 'navigated', `${entry} must pass through when clean`);
    assert.deepEqual(clean.log, [`epoch:${entry}`, `navigate:${entry}`]);
  }
});

test('a disposed coordinator performs nothing', async () => {
  const h = harness();
  h.coordinator.dispose();
  assert.equal(await h.coordinator.request({ kind: 'close' }), 'stayed');
  assert.deepEqual(h.log, []);
});
