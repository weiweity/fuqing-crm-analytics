export const ACCOUNT_NAME_KEY = 'shine-account-name';
export const ACCOUNT_SOURCE_KEY = 'shine-account-source';
export const ACCOUNT_CHANGE_EVENT = 'shine-account-change';

function accountWindow() {
  const scope = typeof globalThis === 'object' && globalThis ? globalThis : undefined;
  if (scope && scope.window) return scope.window;
  return undefined;
}

function accountStorage() {
  try {
    const store = accountWindow()?.localStorage;
    if (!store || typeof store.getItem !== 'function') return null;
    return store;
  } catch {
    return null;
  }
}

function notifyAccountIdentity() {
  const view = accountWindow();
  if (!view || typeof view.dispatchEvent !== 'function') return;
  try {
    const event = typeof Event === 'function' ? new Event(ACCOUNT_CHANGE_EVENT) : { type: ACCOUNT_CHANGE_EVENT };
    view.dispatchEvent(event);
  } catch {
    try { view.dispatchEvent({ type: ACCOUNT_CHANGE_EVENT }); } catch { /* ignore */ }
  }
}

let snapshot = null;

function loadAccountIdentity() {
  const store = accountStorage();
  if (!store) return null;
  try {
    const name = store.getItem(ACCOUNT_NAME_KEY)?.trim() ?? '';
    if (!name) return null;
    return { name, source: store.getItem(ACCOUNT_SOURCE_KEY)?.trim() || 'feishu' };
  } catch {
    return null;
  }
}

export function readAccountIdentity() {
  const next = loadAccountIdentity();
  if (next === null) {
    snapshot = null;
    return null;
  }
  if (snapshot && snapshot.name === next.name && snapshot.source === next.source) return snapshot;
  snapshot = next;
  return snapshot;
}

export function getServerAccountIdentity() {
  return null;
}

export function writeAccountIdentity(input) {
  const store = accountStorage();
  if (!store) return null;
  const name = String(input?.name ?? '').trim();
  if (!name) {
    clearAccountIdentity();
    return null;
  }
  const source = String(input?.source ?? 'feishu').trim() || 'feishu';
  try {
    store.setItem(ACCOUNT_NAME_KEY, name);
    store.setItem(ACCOUNT_SOURCE_KEY, source);
    snapshot = { name, source };
    notifyAccountIdentity();
    return snapshot;
  } catch {
    return null;
  }
}

export function clearAccountIdentity() {
  const store = accountStorage();
  if (!store) return;
  try {
    store.removeItem(ACCOUNT_NAME_KEY);
    store.removeItem(ACCOUNT_SOURCE_KEY);
    snapshot = null;
    notifyAccountIdentity();
  } catch { /* ignore */ }
}

export function subscribeAccountIdentity(listener) {
  const view = accountWindow();
  if (!view || typeof view.addEventListener !== 'function') return () => {};
  const onStorage = event => {
    if (event.key === ACCOUNT_NAME_KEY || event.key === ACCOUNT_SOURCE_KEY || event.key === null) listener();
  };
  view.addEventListener('storage', onStorage);
  view.addEventListener(ACCOUNT_CHANGE_EVENT, listener);
  return () => {
    view.removeEventListener('storage', onStorage);
    view.removeEventListener(ACCOUNT_CHANGE_EVENT, listener);
  };
}

export function accountSourceLabel(identity) {
  if (!identity) return '登录后同步会话';
  if (identity.source === 'feishu') return '飞书';
  return identity.source;
}
