/**
 * T28 (D47) — navigation epoch under controllable latency.
 *
 * The existing suite only proved that a whole-plugin `dispose()` aborts a
 * pending read. This one keeps the client alive and gates individual responses,
 * so a slow `get`/`list`/`preview` settles *after* a newer navigation intent has
 * taken ownership. The assertion is that the late result changes nothing: not
 * the page, not the list, not the message.
 *
 * The intent is submitted through the same public seam the leave coordinator
 * uses (`beginNavigation`), because that is the race the plugin's own busy gate
 * cannot serialize: the host may switch panel while a read is in flight.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createLibraryBoardClient } from '../library-board-client.mjs';
import { createNavigationEpoch, isEpochDiscarded, isSupersededRead, SupersededRead } from './navigation-epoch.mjs';
import { librarySnapshot as snap, libraryPreview as draft, ok, failed, listOf } from '../../../test/helpers/library-board-fixtures.mjs';

/** A hand-operated gate: `open()` releases the pending response. */
function gate() {
  let release;
  const opened = new Promise(resolve => { release = resolve; });
  return { release: () => release(), opened };
}
/** Let queued microtasks run so a read is genuinely in flight. */
const tick = () => new Promise(resolve => setImmediate(resolve));

function client(t, dispatch) {
  const calls = [];
  const instance = createLibraryBoardClient(async (channel, operation, payload, signal) => {
    assert.equal(channel, '/shine-mage-board');
    calls.push({ operation, payload, signal });
    return dispatch(operation, payload, signal);
  });
  t.after(() => instance.dispose());
  return { instance, calls, state: instance.getSnapshot };
}

test('the frozen fixture is the source of truth for what an intent discards', () => {
  assert.deepEqual(['get', 'list', 'preview'].filter(isEpochDiscarded), ['get', 'list', 'preview']);
  // A save receipt is evidence, not a page read: never discarded as one.
  for (const operation of ['confirm', 'cancel', 'cancel_edit']) {
    assert.equal(isEpochDiscarded(operation), false, `${operation} must survive a navigation`);
  }
});

test('a slow get cannot overwrite the page after a newer intent took ownership', async t => {
  const first = snap({ boardId: 'board_first' }), second = snap({ boardId: 'board_second' });
  const slow = gate();
  const { instance, state } = client(t, operation => {
    if (operation !== 'get') throw new Error(`unexpected ${operation}`);
    return slow.opened.then(() => ok(first));
  });
  const pending = instance.openBoard('board_first');
  await tick();
  // The host switches panel while the read is still in flight.
  const ticket = instance.beginNavigation('panel');
  assert.equal(ticket.signal.aborted, false);
  slow.release();
  await pending;
  assert.equal(state().saved, null, 'the superseded page must not be committed');
  assert.equal(state().message, '', 'a superseded read is not reported as an error');
  assert.equal(instance.navigationEpoch(), ticket.epoch);
});

test('a superseded read is dropped even when it fails, so no stale error lands', async t => {
  const slow = gate();
  const { instance, state } = client(t, operation => {
    if (operation !== 'get') throw new Error(`unexpected ${operation}`);
    return slow.opened.then(() => failed('TRANSPORT_ERROR'));
  });
  const pending = instance.openBoard('board_first');
  await tick();
  instance.beginNavigation('panel');
  slow.release();
  await pending;
  assert.equal(state().saved, null);
  assert.equal(state().message, '', 'the stale failure must not be shown against the new page');
});

test('a slow list cannot resurrect the previous listing', async t => {
  const saved = snap({ boardId: 'board_live' });
  const slow = gate();
  const { instance, state } = client(t, operation => {
    if (operation !== 'list') throw new Error(`unexpected ${operation}`);
    return slow.opened.then(() => ok(listOf(saved)));
  });
  const listing = instance.refresh();
  await tick();
  instance.beginNavigation('panel');
  slow.release();
  await listing;
  assert.deepEqual(state().boards, [], 'a late listing must not be committed over the newer intent');
});

test('a slow preview cannot reopen a draft over the newer page', async t => {
  const pending = draft(snap({ boardId: 'board_live', version: 2, content: '迟到的草稿' }));
  const slow = gate();
  const { instance, state } = client(t, operation => {
    if (operation !== 'preview') throw new Error(`unexpected ${operation}`);
    return slow.opened.then(() => ok(pending));
  });
  const opening = instance.openPreview(pending.preview_id);
  await tick();
  instance.beginNavigation('panel');
  slow.release();
  await opening;
  assert.equal(state().preview, null, 'a late draft must not reopen');
  assert.equal(state().message, '');
});

test('a read issued after the newer intent commits normally', async t => {
  const slow = gate(), other = snap({ boardId: 'board_other' });
  let first = true;
  const { instance, state } = client(t, operation => {
    if (operation !== 'get') throw new Error(`unexpected ${operation}`);
    if (first) { first = false; return slow.opened.then(() => ok(snap({ boardId: 'board_first' }))); }
    return ok(other);
  });
  const stale = instance.openBoard('board_first');
  await tick();
  instance.beginNavigation('panel');
  slow.release();
  await stale;
  // The stale read is gone, so the busy gate is free for the new intent.
  assert.equal(state().busy, false);
  await instance.openBoard('board_other');
  assert.deepEqual(state().saved, other, 'the new intent reads and commits its own result');
});

test('leaving and returning keeps the current version, and a draft still blocks a switch', async t => {
  const boardA = snap({ boardId: 'board_a' }), boardB = snap({ boardId: 'board_b' });
  const pending = draft(snap({ boardId: 'board_a', version: 2, content: '待确认' }));
  let phase = 'a';
  const { instance, state, calls } = client(t, operation => {
    if (operation === 'get') return ok(phase === 'a' ? boardA : boardB);
    if (operation === 'list') return ok(listOf(phase === 'a' ? boardA : boardB));
    if (operation === 'preview') return ok(pending);
    if (operation === 'cancel') return ok({ preview_id: pending.preview_id, status: 'CANCELLED' });
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openBoard('board_a');
  await instance.openPreview(pending.preview_id);
  assert.equal(instance.hasUnsavedChanges(), true);
  // With a draft open, a plain switch is a barrier — it does not silently drop it.
  await instance.openBoard('board_b');
  assert.equal(state().incoming?.id, 'board_b');
  assert.equal(calls.filter(call => call.operation === 'get').length, 1, 'the barrier issues no read');
  instance.keepDraft();
  assert.deepEqual(state().preview, pending);
  assert.equal(instance.hasUnsavedChanges(), true);
  // Discarding is the explicit way through; then the round trip reads fresh.
  phase = 'b';
  await instance.openBoard('board_b');
  await instance.discardAndNavigate();
  assert.deepEqual(state().saved, boardB);
  phase = 'a';
  await instance.openBoard('board_a');
  assert.equal(state().saved.spec.board_id, 'board_a', 'returning reads the current head, not a cached older one');
});

test('a late save receipt is matched by idempotency key, never discarded as a stale read', async t => {
  const saved = snap({ boardId: 'board_a' }), applied = snap({ boardId: 'board_a', version: 2, content: '已保存' });
  const pending = draft(applied), slow = gate();
  const { instance, calls, state } = client(t, operation => {
    if (operation === 'preview') return ok(pending);
    if (operation === 'confirm') return slow.opened.then(() => ok(applied));
    if (operation === 'get') return ok(applied);
    if (operation === 'list') return ok(listOf(applied));
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openPreview(pending.preview_id);
  const saving = instance.saveForLeave();
  await tick();
  // A navigation intent arrives while the write is still in flight.
  instance.beginNavigation('panel');
  slow.release();
  const receipt = await saving;
  assert.deepEqual(receipt, { ok: true }, 'the write is not cancelled by the navigation');
  assert.deepEqual(calls.filter(call => call.operation === 'confirm').map(call => call.payload.key),
    ['board-confirm:preview_test'], 'the save keeps its original idempotency key');
  assert.deepEqual(state().saved, applied);
  assert.equal(state().preview, null);
  // The write's signal is the plugin lifetime only: an intent cannot abort it.
  assert.equal(calls.find(call => call.operation === 'confirm').signal.aborted, false);
});

test('a read carries a cancellable signal, and the next intent aborts it', async t => {
  const slow = gate();
  const { instance, calls } = client(t, operation => {
    if (operation !== 'get') throw new Error(`unexpected ${operation}`);
    return slow.opened.then(() => ok(snap()));
  });
  const pending = instance.openBoard('board_test');
  await tick();
  const read = calls.find(call => call.operation === 'get');
  assert.equal(read.signal.aborted, false);
  instance.beginNavigation('panel');
  assert.equal(read.signal.aborted, true, 'the superseded read is cancelled, not left dangling');
  slow.release();
  await pending;
});

test('the epoch advances per intent and a superseded read is recognisable', () => {
  const epoch = createNavigationEpoch();
  const first = epoch.begin('board');
  assert.equal(epoch.isCurrent(first.epoch), true);
  const second = epoch.begin('panel');
  assert.equal(epoch.isCurrent(first.epoch), false, 'a newer intent owns the page');
  assert.equal(epoch.isCurrent(second.epoch), true);
  assert.equal(first.signal.aborted, true, 'the superseded read signal is aborted');
  assert.equal(isSupersededRead(first.signal.reason), true);
  assert.equal(first.signal.reason instanceof SupersededRead, true);
  epoch.dispose();
  assert.equal(epoch.isCurrent(second.epoch), false);
});
