import test from 'node:test';
import assert from 'node:assert/strict';
import { createLibraryBoardClient } from './library-board-client.mjs';
import { librarySnapshot as snap, libraryPreview as draft, ok, failed, listOf } from '../../test/helpers/library-board-fixtures.mjs';

function client(t, dispatch, options) {
  const calls = [];
  const instance = createLibraryBoardClient(async (channel, operation, payload, signal) => {
    assert.equal(channel, '/shine-mage-board'); assert.equal(signal.aborted, false);
    calls.push({ operation, payload }); return dispatch(operation, payload);
  }, options);
  t.after(() => instance.dispose());
  return { instance, calls, state: instance.getSnapshot };
}

test('preview is not a write; cancelling requires the matching receipt and leaves saved snapshot intact', async t => {
  const saved = snap(), pending = draft(snap({ version: 2, content: '新说明' }));
  let cancelReply = failed();
  const { instance, calls, state } = client(t, operation => {
    if (operation === 'get') return ok(saved);
    if (operation === 'preview') return ok(pending);
    if (operation === 'cancel') return cancelReply;
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openBoard(saved.spec.board_id); await instance.openPreview(pending.preview_id);
  assert.deepEqual(state().saved, saved); assert.deepEqual(state().preview, pending);
  assert.equal(calls.some(call => call.operation === 'confirm'), false);
  await instance.cancel(); assert.deepEqual(state().preview, pending);
  cancelReply = ok({ preview_id: 'wrong', status: 'CANCELLED' });
  await instance.cancel(); assert.deepEqual(state().preview, pending);
  cancelReply = ok({ preview_id: pending.preview_id, status: 'CANCELLED' });
  await instance.cancel(); assert.equal(state().preview, null); assert.deepEqual(state().saved, saved);
});

test('lost confirmation reply retains draft, explicit retry reuses key, refresh failure never undoes success', async t => {
  const pending = draft(); let confirmCalls = 0;
  const { instance, calls, state } = client(t, operation => {
    if (operation === 'preview') return ok(pending);
    if (operation === 'confirm') return ++confirmCalls === 1 ? failed() : ok(pending.snapshot);
    if (operation === 'get') return failed('REFRESH_FAILURE');
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openPreview(pending.preview_id); await instance.confirm();
  assert.equal(confirmCalls, 1); assert.equal(state().saved, null); assert.deepEqual(state().preview, pending);
  assert.equal(state().confirmationUncertain, true);
  await instance.confirm();
  assert.equal(confirmCalls, 2); assert.deepEqual(state().saved, pending.snapshot); assert.equal(state().preview, null);
  assert.match(state().message, /保存已确认.*刷新失败/);
  assert.equal(state().confirmationUncertain, false);
  assert.deepEqual(calls.filter(call => call.operation === 'confirm').map(call => call.payload.key), ['board-confirm:preview_test', 'board-confirm:preview_test']);
});

test('connection exceptions preserve saved content and unknown confirmation without exposing raw browser errors', async t => {
  const saved = snap(), pending = draft(snap({ version: 2 })); let disconnected = false;
  const { instance, state, calls } = client(t, operation => {
    if (disconnected) throw new TypeError('Failed to fetch');
    if (operation === 'get') return ok(saved);
    if (operation === 'preview') return ok(pending);
  });
  await instance.openBoard(saved.spec.board_id);
  disconnected = true; await instance.refresh();
  assert.match(state().message, /连接中断.*保留当前内容/);
  assert.deepEqual(state().saved, saved);
  disconnected = false; await instance.openPreview(pending.preview_id);
  disconnected = true; await instance.confirm();
  assert.match(state().message, /未收到保存回执.*保存结果待核对/);
  assert.equal(state().confirmationUncertain, true); assert.deepEqual(state().preview, pending);
  assert.deepEqual(state().saved, saved);
  assert.equal(calls.filter(call => call.operation === 'confirm').length, 1);
});

test('cancel conflict explains an applied draft, preserves recovery state, and does not relabel unrelated conflicts', async t => {
  const saved = snap(), pending = draft(snap({ version: 2 }));
  const conflict = { ok: false, error: { code: 'VERSION_CONFLICT', message: '看板版本已变化，请重新读取后预览；原版本未被覆盖。' } };
  const { instance, state, calls } = client(t, operation => {
    if (operation === 'get') return ok(saved);
    if (operation === 'preview') return ok(pending);
    return conflict;
  });
  await instance.openBoard(saved.spec.board_id); await instance.openPreview(pending.preview_id);
  await instance.confirm(); assert.equal(state().message, conflict.error.message);
  await instance.cancel(); await instance.cancel();
  assert.match(state().message, /草稿已保存.*不能通过取消撤销.*核对保存结果/);
  assert.doesNotMatch(state().message, /原版本未被覆盖/);
  assert.equal(state().confirmationUncertain, true); assert.deepEqual(state().preview, pending);
  assert.deepEqual(state().saved, saved);
  assert.deepEqual(calls.map(call => call.operation), ['get', 'preview', 'confirm', 'cancel', 'cancel']);
});

for (const existing of [false, true]) for (const failure of ['get', 'list']) {
  test(`confirmed ${existing ? 'existing' : 'new'} board is listed atomically when ${failure} refresh fails`, async t => {
    const old = snap(), other = snap({ boardId: 'other_board' });
    const next = snap({ version: existing ? 2 : 1 }); next.spec.title = '已确认的新标题';
    const pending = draft(next); let confirmed = false;
    const { instance, state } = client(t, operation => {
      if (confirmed && operation === failure) return failed('REFRESH_FAILED');
      if (operation === 'list') return ok({ items: [...listOf(other).items, ...(existing ? listOf(old).items : [])] });
      if (operation === 'get') return ok(confirmed ? next : old);
      if (operation === 'preview') return ok(pending);
      if (operation === 'confirm') { confirmed = true; return ok(next); }
      throw new Error(`unexpected ${operation}`);
    });
    await instance.refresh(); if (existing) await instance.openBoard(old.spec.board_id);
    await instance.openPreview(pending.preview_id);
    const updates = []; instance.subscribe(() => { if (state().saved?.spec.title === next.spec.title) updates.push(state()); });
    await instance.confirm();
    assert.deepEqual(state().saved, next); assert.match(state().message, /保存已确认.*刷新失败/);
    assert.ok(updates.length > 0);
    for (const update of updates) {
      assert.deepEqual(update.boards.find(row => row.board_id === next.spec.board_id), listOf(next).items[0]);
      assert.deepEqual(update.boards.find(row => row.board_id === other.spec.board_id), listOf(other).items[0]);
    }
  });
}

test('fresh reads update cached titles, stale lists cannot downgrade them, missing rows are not resurrected', async t => {
  const old = snap(), latest = snap({ version: 3 }); latest.spec.title = '服务端v3标题';
  let listing = listOf(old);
  const { instance, state } = client(t, operation => operation === 'list' ? ok(listing) : ok(latest));
  await instance.refresh(); await instance.openBoard(latest.spec.board_id);
  assert.deepEqual(state().boards, listOf(latest).items);
  instance.beginLayout(); // Refresh the list while leaving the local draft and stored snapshot unchanged.
  await instance.refresh(); assert.deepEqual(state().boards, listOf(latest).items);
  listing = { items: [] }; await instance.refresh();
  assert.deepEqual(state().boards, [], 'do not undo removal or authorization changes inferred from a successful listing');
  assert.deepEqual(state().saved, latest);
});

test('a newer list entry cannot be downgraded by an older board read', async t => {
  const latest = snap({ version: 4 }), stale = snap({ version: 3 });
  const { instance, state } = client(t, operation => ok(operation === 'list' ? listOf(latest) : stale));
  await instance.refresh(); await instance.openBoard(latest.spec.board_id);
  assert.equal(state().saved, null); assert.deepEqual(state().boards, listOf(latest).items);
  assert.match(state().message, /旧版本/);
});

test('unconfirmed, cancelled or unknown new-board previews do not appear in the saved list', async t => {
  const pending = draft();
  const { instance, state } = client(t, operation => {
    if (operation === 'list') return ok({ items: [] });
    if (operation === 'preview') return ok(pending);
    if (operation === 'confirm') return failed();
    if (operation === 'cancel') return ok({ preview_id: pending.preview_id, status: 'CANCELLED' });
  });
  await instance.refresh(); await instance.openPreview(pending.preview_id); assert.deepEqual(state().boards, []);
  await instance.confirm(); assert.deepEqual(state().boards, []);
  await instance.cancel(); assert.deepEqual(state().boards, []); assert.equal(state().saved, null);
});

test('unknown confirmation can be read back without another write; failed or pending inspection remains uncertain', async t => {
  const saved = snap(), pending = draft(snap({ version: 2, content: '已落盘的新内容' }));
  let phase = 'initial', readsFail = false, staleHead = false;
  const { instance, state, calls } = client(t, operation => {
    if (operation === 'get') return readsFail ? failed() : ok(phase === 'applied' && !staleHead ? pending.snapshot : saved);
    if (operation === 'list') return ok(listOf(pending.snapshot));
    if (operation === 'preview') return ok({ ...pending, status: phase === 'applied' ? 'APPLIED' : 'PENDING' });
    if (operation === 'confirm') { phase = 'applied'; return failed(); }
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openBoard(saved.spec.board_id); await instance.openPreview(pending.preview_id); await instance.confirm();
  assert.equal(state().confirmationUncertain, true);
  phase = 'pending'; await instance.inspectConfirmation();
  assert.equal(state().confirmationUncertain, true); assert.deepEqual(state().saved, saved);
  phase = 'applied'; readsFail = true; await instance.inspectConfirmation();
  assert.equal(state().confirmationUncertain, true); assert.deepEqual(state().preview, pending);
  readsFail = false; staleHead = true; await instance.inspectConfirmation();
  assert.equal(state().confirmationUncertain, true); assert.deepEqual(state().saved, saved);
  assert.match(state().message, /旧版本/);
  staleHead = false; await instance.inspectConfirmation();
  assert.equal(state().confirmationUncertain, false); assert.equal(state().preview, null);
  assert.deepEqual(state().saved, pending.snapshot); assert.match(state().message, /已核对.*保存/);
  assert.equal(calls.filter(call => call.operation === 'confirm').length, 1);
});

test('confirmation inspection refuses a different preview and handles verified cancellation without a write', async t => {
  const pending = draft(); let reply = ok(pending);
  const { instance, state, calls } = client(t, operation => operation === 'confirm' ? failed() : reply);
  await instance.openPreview(pending.preview_id); await instance.confirm();
  reply = ok({ ...pending, preview_id: 'different_preview', status: 'APPLIED' });
  await instance.inspectConfirmation();
  assert.equal(state().confirmationUncertain, true); assert.deepEqual(state().preview, pending);
  reply = ok({ ...pending, status: 'CANCELLED' }); await instance.inspectConfirmation();
  assert.equal(state().confirmationUncertain, false); assert.equal(state().preview, null);
  assert.equal(state().saved, null); assert.equal(calls.filter(call => call.operation === 'confirm').length, 1);
});

test('stale confirmation replay or read cannot replace a known newer head', async t => {
  const newer = snap({ version: 3, content: '另一标签页的新版本' }), pending = draft();
  let getCount = 0;
  const { instance, state } = client(t, operation => {
    if (operation === 'get') return ok(++getCount === 1 ? newer : pending.snapshot);
    if (operation === 'preview') return ok(pending);
    if (operation === 'confirm') return ok(pending.snapshot);
    if (operation === 'list') return ok(listOf(newer));
  });
  await instance.openBoard(newer.spec.board_id); await instance.openPreview(pending.preview_id); await instance.confirm();
  assert.deepEqual(state().saved, newer); assert.equal(state().preview, null);
  await instance.refresh(); assert.deepEqual(state().saved, newer); assert.match(state().message, /旧版本/);
});

test('switching with an unconfirmed draft has an explicit discard barrier, not silent replacement', async t => {
  const pending = draft(), other = snap({ boardId: 'board_other' });
  const { instance, calls, state } = client(t, operation => {
    if (operation === 'preview') return ok(pending);
    if (operation === 'get') return ok(other);
    if (operation === 'cancel') return ok({ preview_id: pending.preview_id, status: 'CANCELLED' });
  });
  await instance.openPreview(pending.preview_id); await instance.openBoard(other.spec.board_id);
  assert.deepEqual(state().incoming, { kind: 'board', id: other.spec.board_id });
  assert.equal(calls.length, 1);
  instance.keepDraft(); assert.equal(state().incoming, null); assert.deepEqual(state().preview, pending);
  await instance.openBoard(other.spec.board_id); await instance.discardAndNavigate();
  assert.deepEqual(calls.map(call => call.operation), ['preview', 'cancel', 'get']);
  assert.equal(state().preview, null); assert.deepEqual(state().saved, other);
});

test('rollback is a target-checked preview; malformed and expired responses preserve current state', async t => {
  const saved = snap({ version: 2 }), pending = draft(snap({ version: 3, content: '初版' }), { operation: 'ROLLBACK' });
  let response = ok({ ...pending, snapshot: snap({ boardId: 'wrong', version: 3 }) });
  const { instance, calls, state } = client(t, operation => operation === 'get' ? ok(saved) : response);
  await instance.openBoard(saved.spec.board_id); await instance.rollback(1);
  assert.equal(state().preview, null); assert.deepEqual(state().saved, saved);
  response = ok(pending); await instance.rollback(1);
  assert.deepEqual(state().preview, pending); assert.deepEqual(state().saved, saved);
  assert.equal(calls.some(call => call.operation === 'confirm'), false);
  // A separate client also refuses a response with an impossible draft version.
  const invalid = client(t, () => ok({ ...pending, base_version: 50 }));
  await invalid.instance.openPreview(pending.preview_id); assert.equal(invalid.state().preview, null);
  const expired = client(t, () => ok({ ...pending, expires_at_ms: 1 }));
  await expired.instance.openPreview(pending.preview_id); assert.equal(expired.state().preview, null);
  assert.match(expired.state().message, /过期/);
});

test('busy actions serialize and plugin disposal aborts pending reads without publishing late state', async t => {
  let release, signal;
  const instance = createLibraryBoardClient((_channel, _operation, _payload, incoming) => {
    signal = incoming; return new Promise(resolve => { release = resolve; });
  });
  t.after(() => instance.dispose());
  let updates = 0; instance.subscribe(() => updates++);
  const pending = instance.openBoard('board_test');
  await instance.openPreview('preview_test'); // No second request races the first.
  assert.equal(updates, 1); assert.equal(instance.getSnapshot().busy, true);
  instance.dispose(); assert.equal(signal.aborted, true);
  release(ok(snap())); await pending;
  assert.equal(updates, 1); assert.equal(instance.getSnapshot().saved, null);
});

test('reopening a saved snapshot requires no model call; failed refresh keeps the existing canvas', async t => {
  const saved = snap(); let offline = false;
  const { instance, calls, state } = client(t, operation => offline ? failed() : ok(operation === 'get' ? saved : listOf(saved)));
  await instance.refresh(); await instance.openBoard(saved.spec.board_id);
  offline = true; await instance.refresh();
  assert.deepEqual(state().saved, saved);
  assert.deepEqual(calls.map(call => call.operation), ['list', 'get', 'list']);
  const restarted = client(t, operation => ok(operation === 'get' ? saved : listOf(saved)));
  await restarted.instance.refresh(); await restarted.instance.openBoard(saved.spec.board_id);
  assert.deepEqual(restarted.state().saved, saved);
});

test('free layout edits are local; collision, failed preview and cancel preserve saved facts and neighbours', async t => {
  const saved = snap(), original = structuredClone(saved);
  const first = saved.spec.blocks[0];
  saved.spec.blocks.push({ ...structuredClone(first), block_id: 'neighbour', layout: { x: 6, y: 0, w: 6, h: 5 } });
  const source = structuredClone(saved); let previewFails = true;
  const { instance, state, calls } = client(t, (operation, payload) => {
    if (operation === 'get') return ok(source);
    if (operation === 'list') return ok(listOf(source));
    if (operation === 'layout_preview') {
      if (previewFails) return failed('LAYOUT_CONFLICT');
      const result = structuredClone(source); result.spec.version++;
      for (const update of payload.layouts) result.spec.blocks.find(item => item.block_id === update.block_id).layout = update.layout;
      return ok(draft(result, { operation: 'LAYOUT' }));
    }
    if (operation === 'cancel') return ok({ preview_id: payload.preview_id, status: 'CANCELLED' });
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openBoard(saved.spec.board_id); instance.beginLayout();
  instance.updateLayout(first.block_id, { x: 5, y: 0, w: 6, h: 5 });
  assert.deepEqual(state().layoutDraft, source); assert.match(state().message, /重叠/);
  instance.updateLayout(first.block_id, { x: 1, y: 6, w: 8, h: 7 });
  assert.deepEqual(state().saved, source); assert.equal(calls.length, 1);
  assert.deepEqual(state().layoutDraft.spec.blocks[1], source.spec.blocks[1]);
  assert.equal(state().layoutDraft.facts_by_result_id, state().saved.facts_by_result_id);
  await instance.refresh(); assert.deepEqual(calls.map(call => call.operation), ['get', 'list']);
  await instance.previewLayout(); assert.ok(state().layoutDraft); assert.equal(state().preview, null);
  previewFails = false; await instance.previewLayout();
  assert.equal(state().layoutDraft, null); assert.equal(state().preview.operation, 'LAYOUT');
  assert.deepEqual(state().saved, source);
  assert.deepEqual(calls.at(-1).payload.layouts, [{ block_id: first.block_id, layout: { x: 1, y: 6, w: 8, h: 7 } }]);
  assert.deepEqual(saved.spec.blocks[0], original.spec.blocks[0]);
  const previewId = state().preview.preview_id;
  await instance.cancel();
  assert.equal(state().preview, null);
  assert.deepEqual(state().layoutDraft.spec.blocks[0].layout, { x: 1, y: 6, w: 8, h: 7 });
  assert.equal(calls.at(-1).operation, 'cancel');
  assert.equal(calls.at(-1).payload.preview_id, previewId);
});

test('local layout cancel and draft switching barrier do not create server writes', async t => {
  const saved = snap(), other = snap({ boardId: 'other' });
  const { instance, state, calls } = client(t, (_operation, payload) => ok(payload.board_id === 'other' ? other : saved));
  await instance.openBoard(saved.spec.board_id); instance.beginLayout();
  await instance.previewLayout(); assert.match(state().message, /没有变化/); assert.equal(calls.length, 1);
  instance.updateLayout(saved.spec.blocks[0].block_id, { x: 0, y: 6, w: 6, h: 6 });
  await instance.openBoard('other'); assert.ok(state().incoming); assert.equal(calls.length, 1);
  instance.keepDraft(); assert.ok(state().layoutDraft);
  await instance.cancel(); assert.equal(state().layoutDraft, null); assert.deepEqual(state().saved, saved); assert.equal(calls.length, 1);
  instance.beginLayout(); await instance.openBoard('other'); await instance.discardAndNavigate();
  assert.deepEqual(state().saved, other); assert.equal(state().layoutDraft, null);
  assert.deepEqual(calls.map(call => call.operation), ['get', 'get']);
});

test('rollbackPrevious reuses loaded history and reports when none is earlier', async t => {
  const v1 = snap({ version: 1 });
  const none = client(t, operation => {
    if (operation === 'get') return ok(v1);
    if (operation === 'list') return ok(listOf(v1));
    if (operation === 'history') return ok([{ version: 1, operation: 'GENERATE', created_at_ms: 1 }]);
    throw new Error(`unexpected ${operation}`);
  });
  await none.instance.openBoard(v1.spec.board_id);
  await none.instance.loadHistory();
  await none.instance.rollbackPrevious();
  assert.match(none.state().message, /没有可回退的更早版本/);
  assert.equal(none.state().preview, null);
  assert.equal(none.calls.filter(call => call.operation === 'history').length, 1);
  assert.equal(none.calls.some(call => call.operation === 'rollback_preview'), false);

  const v2 = snap({ version: 2 });
  const reuse = client(t, (operation, payload) => {
    if (operation === 'get') return ok(v2);
    if (operation === 'list') return ok(listOf(v2));
    if (operation === 'history') return ok([
      { version: 1, operation: 'GENERATE', created_at_ms: 1 },
      { version: 2, operation: 'PATCH', created_at_ms: 2 },
    ]);
    if (operation === 'rollback_preview') {
      assert.equal(payload.to_version, 1);
      return ok(draft(snap({ version: 3 }), { operation: 'ROLLBACK', base_version: 2 }));
    }
    throw new Error(`unexpected ${operation}`);
  });
  await reuse.instance.openBoard(v2.spec.board_id);
  await reuse.instance.loadHistory();
  await reuse.instance.rollbackPrevious();
  assert.equal(reuse.state().preview.operation, 'ROLLBACK');
  assert.equal(reuse.calls.filter(call => call.operation === 'history').length, 1, 'loaded history is not fetched again');

  const blocked = client(t, operation => {
    if (operation === 'get') return ok(v2);
    if (operation === 'list') return ok(listOf(v2));
    throw new Error(`unexpected ${operation}`);
  });
  await blocked.instance.openBoard(v2.spec.board_id);
  blocked.instance.beginLayout();
  await blocked.instance.rollbackPrevious();
  assert.equal(blocked.state().preview, null, 'layout draft blocks rollbackPrevious');
  assert.equal(blocked.calls.some(call => call.operation === 'history' || call.operation === 'rollback_preview'), false);

  const bad = client(t, operation => {
    if (operation === 'get') return ok(v2);
    if (operation === 'list') return ok(listOf(v2));
    if (operation === 'history') return ok([{ version: 1 }]);
    throw new Error(`unexpected ${operation}`);
  });
  await bad.instance.openBoard(v2.spec.board_id);
  await bad.instance.rollbackPrevious();
  assert.match(bad.state().message, /版本历史响应不合法/);
  assert.equal(bad.state().preview, null);
});

test('rollbackPrevious loads history once then opens a ROLLBACK preview', async t => {
  const saved = snap({ version: 2 });
  const { instance, state, calls } = client(t, (operation, payload) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'list') return ok(listOf(saved));
    if (operation === 'history') return ok([{ version: 1, operation: 'GENERATE', created_at_ms: 1 }]);
    if (operation === 'rollback_preview') {
      assert.equal(payload.to_version, 1);
      return ok(draft(snap({ version: 3 }), { operation: 'ROLLBACK', base_version: 2 }));
    }
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openBoard(saved.spec.board_id);
  await instance.rollbackPrevious();
  assert.equal(state().preview.operation, 'ROLLBACK');
  assert.deepEqual(calls.map(call => call.operation), ['get', 'history', 'rollback_preview']);
  await instance.rollbackPrevious();
  assert.equal(state().preview.operation, 'ROLLBACK');
  assert.equal(calls.filter(call => call.operation === 'rollback_preview').length, 1, 'busy preview blocks a second rollback');
});

test('rollbackPrevious picks the immediate previous version regardless of history order', async t => {
  const v3 = snap({ version: 3 });
  const { instance, calls } = client(t, (operation, payload) => {
    if (operation === 'get') return ok(v3);
    if (operation === 'list') return ok(listOf(v3));
    if (operation === 'history') return ok([
      { version: 1, operation: 'GENERATE', created_at_ms: 1 },
      { version: 3, operation: 'PATCH', created_at_ms: 3 },
      { version: 2, operation: 'PATCH', created_at_ms: 2 },
    ]);
    if (operation === 'rollback_preview') {
      assert.equal(payload.to_version, 2);
      return ok(draft(snap({ version: 4 }), { operation: 'ROLLBACK', base_version: 3 }));
    }
    throw new Error(`unexpected ${operation}`);
  });
  await instance.openBoard(v3.spec.board_id);
  await instance.rollbackPrevious();
  assert.equal(calls.find(call => call.operation === 'rollback_preview').payload.to_version, 2);
});

test('selected edit is native-session bound, switching requires cancellation, and failed cancel retains the target', async t => {
  const saved = snap(), sent = [];
  saved.spec.blocks.push({ ...structuredClone(saved.spec.blocks[0]), block_id: 'other', layout: { x: 6, y: 0, w: 6, h: 5 } });
  let current = null, failCancel = true, serial = 0;
  const { instance, state, calls } = client(t, (operation, payload) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(current);
    if (operation === 'select_edit') {
      current = { schema_version: 'board-edit-context/v1', edit_context_id: 'edit_' + String(++serial).padStart(32, '0'),
        board_id: saved.spec.board_id, base_version: 1, block_id: payload.block_id, session_id: saved.spec.session_id,
        status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000,
        block: saved.spec.blocks.find(block => block.block_id === payload.block_id), facts_by_result_id: {} };
      return ok(current);
    }
    if (operation === 'cancel_edit') {
      if (failCancel) return failed();
      current = null; return ok({ edit_context_id: payload.edit_context_id, status: 'CANCELLED' });
    }
    throw new Error(operation);
  }, { editNative: async context => sent.push(context) });
  await instance.openBoard(saved.spec.board_id); await instance.beginEdit('note');
  assert.equal(state().editContext.block_id, 'note'); assert.equal(sent[0].session_id, 'native_session');
  assert.deepEqual(state().saved, saved); instance.beginLayout(); assert.equal(state().layoutDraft, null);
  await instance.beginEdit('other'); assert.equal(state().incoming.kind, 'edit');
  assert.equal(sent.length, 1); await instance.discardAndNavigate(); assert.equal(state().editContext.block_id, 'note');
  failCancel = false; await instance.discardAndNavigate();
  assert.equal(state().editContext.block_id, 'other'); assert.equal(sent.length, 2);
  assert.deepEqual(calls.filter(call => call.operation === 'select_edit').map(call => call.payload), [
    { board_id: saved.spec.board_id, base_version: 1, block_id: 'note' },
    { board_id: saved.spec.board_id, base_version: 1, block_id: 'other' },
  ]);
  await instance.cancel(); assert.equal(state().editContext, null); assert.deepEqual(state().saved, saved);
});

test('selectComponent does not send native messages; beginEdit still does; patch is local RPC', async t => {
  const saved = snap();
  const pending = draft(snap({ version: 2, content: '新说明' }), { operation: 'PATCH', base_version: 1, preview_id: 'preview_patch' });
  let current = null;
  const sent = [];
  const { instance, calls, state } = client(t, (operation, payload) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(current);
    if (operation === 'select_edit') {
      current = {
        schema_version: 'board-edit-context/v1',
        edit_context_id: 'edit_' + 'b'.repeat(32),
        board_id: saved.spec.board_id, base_version: 1, block_id: payload.block_id,
        session_id: saved.spec.session_id, status: 'OPEN', preview_id: null,
        expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {},
      };
      return ok(current);
    }
    if (operation === 'patch_preview') {
      assert.deepEqual(payload.changes, { title: '新标题' });
      return ok(pending);
    }
    throw new Error(operation);
  }, { editNative: async context => sent.push(context) });
  await instance.openBoard(saved.spec.board_id);
  await instance.selectComponent('note');
  assert.equal(state().editContext.block_id, 'note');
  assert.equal(sent.length, 0);
  assert.equal(instance.describeSelectedPatch().kind, 'TEXT');
  await instance.previewBlockPatch({ title: '新标题' });
  assert.equal(state().preview.operation, 'PATCH');
  await instance.resumeEdit();
  assert.equal(sent.length, 1);
  const native = client(t, (operation, payload) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(null);
    if (operation === 'select_edit') {
      return ok({
        schema_version: 'board-edit-context/v1',
        edit_context_id: 'edit_' + 'c'.repeat(32),
        board_id: saved.spec.board_id, base_version: 1, block_id: payload.block_id,
        session_id: saved.spec.session_id, status: 'OPEN', preview_id: null,
        expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {},
      });
    }
    throw new Error(operation);
  }, { editNative: async context => sent.push(context) });
  await native.instance.openBoard(saved.spec.board_id);
  await native.instance.beginEdit('note');
  assert.equal(sent.length, 2);
});

test('previewBlockPatch keeps an uncertain save receipt and does not start another PATCH', async t => {
  const saved = snap();
  const pending = draft(snap({ version: 2, content: '新说明' }), { operation: 'PATCH', base_version: 1, preview_id: 'preview_patch' });
  let current = null;
  const { instance, calls, state } = client(t, (operation, payload) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(current);
    if (operation === 'select_edit') {
      current = {
        schema_version: 'board-edit-context/v1',
        edit_context_id: 'edit_' + 'd'.repeat(32),
        board_id: saved.spec.board_id, base_version: 1, block_id: payload.block_id,
        session_id: saved.spec.session_id, status: 'OPEN', preview_id: null,
        expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {},
      };
      return ok(current);
    }
    if (operation === 'patch_preview') return ok(pending);
    if (operation === 'confirm') return failed();
    throw new Error(operation);
  });
  await instance.openBoard(saved.spec.board_id);
  await instance.selectComponent('note');
  await instance.previewBlockPatch({ title: '新标题' });
  await instance.confirm();
  assert.equal(state().confirmationUncertain, true);
  assert.equal(state().preview.preview_id, 'preview_patch');
  const patchesBefore = calls.filter(call => call.operation === 'patch_preview').length;
  await instance.previewBlockPatch({ title: '另一标题' });
  assert.equal(calls.filter(call => call.operation === 'patch_preview').length, patchesBefore);
  assert.equal(state().preview.preview_id, 'preview_patch');
  assert.match(state().message, /未核对的保存回执/);
});

test('lost native prompt retains resumable selection; a reopened client reads its pending preview without recreating it', async t => {
  const saved = snap(), pending = draft(snap({ version: 2, content: '新说明' }));
  const context = { schema_version: 'board-edit-context/v1', edit_context_id: 'edit_' + 'a'.repeat(32),
    board_id: saved.spec.board_id, base_version: 1, block_id: 'note', session_id: saved.spec.session_id,
    status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {} };
  let existing = null, losePrompt = true;
  const dispatch = operation => {
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(existing);
    if (operation === 'select_edit') { existing = context; return ok(existing); }
    if (operation === 'preview') return ok(pending);
    throw new Error(operation);
  };
  const one = client(t, dispatch, { editNative: async () => { if (losePrompt) throw new Error('原生请求回执丢失'); } });
  await one.instance.openBoard(saved.spec.board_id); await one.instance.beginEdit('note');
  assert.equal(one.state().editContext.edit_context_id, context.edit_context_id);
  assert.match(one.state().message, /回执丢失/);
  losePrompt = false; await one.instance.resumeEdit(); assert.equal(one.calls.filter(call => call.operation === 'select_edit').length, 1);
  existing = { ...context, status: 'PROPOSED', preview_id: pending.preview_id };
  const reopened = client(t, dispatch);
  await reopened.instance.openPreview(pending.preview_id, context.edit_context_id);
  assert.deepEqual(reopened.state().saved, saved); assert.equal(reopened.state().editContext.edit_context_id, context.edit_context_id);
  assert.deepEqual(reopened.state().preview, pending); assert.equal(reopened.calls.some(call => call.operation === 'select_edit'), false);
  existing = null; // Cancelled/expired/confirmed elsewhere: explicit inspection recovers the saved board.
  await reopened.instance.inspectEdit();
  assert.equal(reopened.state().editContext, null); assert.equal(reopened.state().preview, null);
  assert.deepEqual(reopened.state().saved, saved); assert.match(reopened.state().message, /已结束或过期/);
});

test('source choices retain other authorized board facts when selected context contains only its own result', async t => {
  const saved = snap();
  saved.spec.blocks[0] = { ...saved.spec.blocks[0], kind: 'METRIC', props: {}, source_result_id: 'result_a' };
  saved.facts_by_result_id = { result_a: { scalar: { value: 1 } }, result_b: { scalar: { value: 2 } } };
  const { instance } = client(t, (operation) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(null);
    if (operation === 'select_edit') return ok({ schema_version: 'board-edit-context/v1', edit_context_id: 'edit_choices',
      board_id: saved.spec.board_id, base_version: 1, block_id: 'note', session_id: saved.spec.session_id,
      status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: { result_a: saved.facts_by_result_id.result_a } });
    throw new Error(operation);
  });
  await instance.openBoard(saved.spec.board_id); await instance.selectComponent('note');
  assert.deepEqual(instance.describeSelectedPatch().source_result_options, ['result_a', 'result_b']);
});
