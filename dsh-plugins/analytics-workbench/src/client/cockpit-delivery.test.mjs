import test from 'node:test';
import assert from 'node:assert/strict';
import { resolvePageGenerateSession } from '../initial-session.mjs';
import {
  captureDeliverySessionSource, createCockpitDelivery, inspectDeliveryHostCapabilities,
  ingestWorkspaceEventFiles, tryAttachWorkspaceChangeRefresh,
} from './cockpit-delivery.mjs';

function row(id, mainView = 0) {
  return { id, retainedBy: mainView ? { mainView } : {} };
}

test('capture requires an explicit listed session and never uses ids[0]', () => {
  const live = {
    ids: ['session-old', 'session-visible'],
    byId: {
      'session-old': row('session-old'),
      'session-visible': row('session-visible', 1),
    },
  };
  assert.equal(resolvePageGenerateSession(live), 'session-visible');
  assert.equal(captureDeliverySessionSource(live).sessionId, 'session-visible');
  assert.equal(captureDeliverySessionSource(live, 'session-old').sessionId, 'session-old');
  const none = {
    ids: ['session-old', 'session-other'],
    byId: { 'session-old': row('session-old'), 'session-other': row('session-other') },
  };
  assert.equal(captureDeliverySessionSource(none).status, 'no-session');
  assert.notEqual(captureDeliverySessionSource(none).sessionId, none.ids[0]);
});

test('delivery refresh reports no-session, empty, ready, truncated, and error', async () => {
  const tree = {
    sess: {
      '.': { path: '', entries: [{ name: 'a.html', type: 'file' }] },
    },
  };
  const delivery = createCockpitDelivery({
    listDir: async (sessionId, path) => {
      if (sessionId === 'boom') throw new Error('list failed');
      if (sessionId === 'empty') return { path: '', entries: [] };
      return tree[sessionId]?.[path === '.' ? '.' : path] ?? { ok: false };
    },
  });
  assert.equal((await delivery.refresh()).status, 'no-session');
  delivery.setSessionId('empty');
  assert.equal((await delivery.refresh()).status, 'empty');
  delivery.setSessionId('sess');
  const ready = await delivery.refresh();
  assert.equal(ready.status, 'ready');
  assert.deepEqual(ready.files.map(item => item.path), ['a.html']);
  delivery.setSessionId('boom');
  assert.equal((await delivery.refresh()).status, 'error');
  delivery.dispose();
});

test('stale refresh does not overwrite a newer session snapshot', async () => {
  let releaseSlow;
  const slow = new Promise(resolve => { releaseSlow = resolve; });
  const delivery = createCockpitDelivery({
    listDir: async (sessionId) => {
      if (sessionId === 'slow') {
        await slow;
        return { path: '', entries: [{ name: 'old.html', type: 'file' }] };
      }
      return { path: '', entries: [{ name: 'new.html', type: 'file' }] };
    },
  });
  const first = delivery.refresh({ sessionId: 'slow' });
  const second = await delivery.refresh({ sessionId: 'fast' });
  assert.equal(second.sessionId, 'fast');
  assert.deepEqual(second.files.map(item => item.path), ['new.html']);
  releaseSlow();
  await first;
  assert.equal(delivery.getSnapshot().sessionId, 'fast');
  assert.deepEqual(delivery.getSnapshot().files.map(item => item.path), ['new.html']);
  delivery.dispose();
});

test('event ingest rejects absolute and parent paths and dedupes repeats', () => {
  const first = ingestWorkspaceEventFiles('sess', [
    'ops-dashboard-live/web/index.html',
    '/tmp/escape.html',
    '../secret.html',
    { path: 'ops-dashboard-live/web/index.html' },
  ]);
  assert.deepEqual(first.map(item => item.path), ['ops-dashboard-live/web/index.html']);
  const again = ingestWorkspaceEventFiles('sess', ['ops-dashboard-live/web/index.html'], { existing: first });
  assert.equal(again.length, 1);
});

test('host capability inspect stays manual unless a real subscribe function exists', () => {
  const missing = inspectDeliveryHostCapabilities({
    remote: { workspaceFiles: { list: async () => ({}), read: async () => ({}) } },
  });
  assert.equal(missing.canListWorkspace, true);
  assert.equal(missing.canReadWorkspace, true);
  assert.equal(missing.canSubscribeWorkspaceChanges, false);
  assert.equal(missing.refreshMode, 'manual');
  assert.match(missing.workspaceChangesReason, /ui-deliverables/);
  let calls = 0;
  const attached = tryAttachWorkspaceChangeRefresh({
    subscribeWorkspaceChanges(listener) {
      listener({ turn: 1 });
      return () => {};
    },
  }, () => { calls += 1; });
  assert.equal(attached.attached, true);
  assert.equal(calls, 1);
  attached.unsubscribe();
  const skipped = tryAttachWorkspaceChangeRefresh({}, () => { calls += 1; });
  assert.equal(skipped.attached, false);
});

test('readFile uses the captured session and does not invent a fallback', async () => {
  const delivery = createCockpitDelivery({
    read: async (sessionId, path) => {
      assert.equal(sessionId, 'session-visible');
      return { text: `<p>${path}</p>` };
    },
  });
  assert.equal((await delivery.readFile('a.html')).reason, 'no-session');
  delivery.setSessionId('session-visible');
  assert.equal((await delivery.readFile('a.html')).text, '<p>a.html</p>');
  delivery.dispose();
});
