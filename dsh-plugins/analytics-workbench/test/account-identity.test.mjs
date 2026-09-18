import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ACCOUNT_CHANGE_EVENT,
  ACCOUNT_NAME_KEY,
  ACCOUNT_SOURCE_KEY,
  accountSourceLabel,
  clearAccountIdentity,
  readAccountIdentity,
  subscribeAccountIdentity,
  writeAccountIdentity,
} from '../src/client/account-identity.mjs';

function installWindow() {
  const data = new Map();
  const listeners = new Map();
  const previous = globalThis.window;
  const view = {
    localStorage: {
      getItem(key) { return data.has(key) ? data.get(key) : null; },
      setItem(key, value) { data.set(String(key), String(value)); },
      removeItem(key) { data.delete(String(key)); },
    },
    addEventListener(type, fn) {
      const list = listeners.get(type) ?? [];
      list.push(fn);
      listeners.set(type, list);
    },
    removeEventListener(type, fn) {
      listeners.set(type, (listeners.get(type) ?? []).filter(row => row !== fn));
    },
    dispatchEvent(event) {
      for (const fn of listeners.get(event.type) ?? []) fn(event);
      return true;
    },
  };
  globalThis.window = view;
  return {
    restore() {
      if (previous === undefined) delete globalThis.window;
      else globalThis.window = previous;
    },
  };
}

test('writeAccountIdentity persists name/source and notifies the same tab', () => {
  const { restore } = installWindow();
  const seen = [];
  const stop = subscribeAccountIdentity(() => seen.push(readAccountIdentity()));
  try {
    assert.equal(readAccountIdentity(), null);
    const written = writeAccountIdentity({ name: ' 王敏 ' });
    assert.deepEqual(written, { name: '王敏', source: 'feishu' });
    assert.equal(readAccountIdentity(), written);
    assert.deepEqual(readAccountIdentity(), { name: '王敏', source: 'feishu' });
    assert.equal(globalThis.window.localStorage.getItem(ACCOUNT_NAME_KEY), '王敏');
    assert.equal(globalThis.window.localStorage.getItem(ACCOUNT_SOURCE_KEY), 'feishu');
    assert.deepEqual(seen, [{ name: '王敏', source: 'feishu' }]);
    assert.equal(accountSourceLabel(readAccountIdentity()), '飞书');
    writeAccountIdentity({ name: 'Ada', source: 'local' });
    assert.equal(accountSourceLabel(readAccountIdentity()), 'local');
    clearAccountIdentity();
    assert.equal(readAccountIdentity(), null);
    assert.equal(accountSourceLabel(null), '登录后同步会话');
    assert.equal(seen.at(-1), null);
  } finally {
    stop();
    restore();
  }
});

test('empty write clears identity and storage events still refresh', () => {
  const { restore } = installWindow();
  const seen = [];
  const stop = subscribeAccountIdentity(() => seen.push(readAccountIdentity()));
  try {
    writeAccountIdentity({ name: 'Ada', source: 'feishu' });
    writeAccountIdentity({ name: '   ' });
    assert.equal(readAccountIdentity(), null);
    const onStorage = globalThis.window.addEventListener;
    assert.equal(typeof onStorage, 'function');
    globalThis.window.dispatchEvent({
      type: 'storage',
      key: ACCOUNT_NAME_KEY,
    });
    globalThis.window.dispatchEvent({ type: ACCOUNT_CHANGE_EVENT });
    assert.ok(seen.length >= 3);
  } finally {
    stop();
    restore();
  }
});
