import test from 'node:test';
import assert from 'node:assert/strict';
import { B0_PRIMARY_SESSION_ID as primary, configuredSession, bindInitialSession } from '../src/initial-session.mjs';

const ready = { phase: 'ready', ids: [primary], byId: { [primary]: { id: primary } }, current: undefined };
function fixture(initial) {
  let snapshot = initial;
  const listeners = new Set();
  const opened = [];
  const sessions = {
    list: { getSnapshot: () => snapshot, subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); } },
    open(id) { opened.push(id); snapshot = { ...snapshot, current: id }; for (const listener of listeners) listener(); },
    create() { assert.fail('B0 automatic selection must never create'); },
  };
  return { sessions, opened, listeners, publish(next) { snapshot = next; for (const listener of listeners) listener(); } };
}
test('selection requires ready and exact matching Host ids plus byId entry', () => {
  assert.equal(configuredSession(ready), primary);
  for (const value of [{ ...ready, phase: 'pending' }, { ...ready, ids: ['another'] },
    { ...ready, byId: {} }, { ...ready, byId: { [primary]: { id: 'another' } } }]) {
    assert.equal(configuredSession(value), null);
  }
});
test('pending and unrelated ready lists do not select; arriving exact primary selects once', () => {
  const f = fixture({ ...ready, phase: 'pending' });
  const dispose = bindInitialSession(f.sessions, () => assert.fail('unexpected selection failure'));
  assert.deepEqual(f.opened, []);
  f.publish({ phase: 'ready', ids: ['another'], byId: { another: { id: 'another' } } });
  assert.deepEqual(f.opened, []);
  f.publish(ready);
  assert.deepEqual(f.opened, [primary]);
  // Reentrant notification and subsequent user navigation must not reopen it.
  f.publish({ ...ready, current: 'another' });
  f.publish(ready);
  assert.deepEqual(f.opened, [primary]);
  dispose();
  assert.equal(f.listeners.size, 0);
});
test('already restored exact primary consumes the initial choice without another open', () => {
  const f = fixture({ ...ready, current: primary });
  const dispose = bindInitialSession(f.sessions, () => assert.fail('unexpected failure'));
  f.publish({ ...ready, current: 'another' });
  assert.deepEqual(f.opened, []);
  dispose();
});
test('unmount while pending prevents later selection', () => {
  const f = fixture({ ...ready, phase: 'pending' });
  const dispose = bindInitialSession(f.sessions, () => assert.fail('unexpected failure'));
  dispose();
  f.publish(ready);
  assert.deepEqual(f.opened, []);
});
test('open failure is reported once, never retried or replaced with another session', () => {
  const f = fixture(ready);
  let failures = 0, attempts = 0;
  f.sessions.open = id => { assert.equal(id, primary); attempts++; throw new Error('no longer available'); };
  const dispose = bindInitialSession(f.sessions, () => { failures++; });
  f.publish(ready);
  assert.equal(attempts, 1);
  assert.equal(failures, 1);
  dispose();
});
