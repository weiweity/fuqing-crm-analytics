/** Session-scoped delivery scan for the cockpit cabinet. No UI store, no index.tsx wiring. */

import { resolvePageGenerateSession } from '../initial-session.mjs';
import {
  classifyWorkspaceFile,
  cockpitProductIdentity,
  collectWorkspaceScan,
  readWorkspaceFileText,
  workspaceRelFromEventPath,
} from './cockpit-products.mjs';
import { createNavigationEpoch, isSupersededRead } from './navigation/navigation-epoch.mjs';

export function captureDeliverySessionSource(list, compositionSessionId) {
  const sessionId = resolvePageGenerateSession(list, compositionSessionId);
  if (typeof sessionId !== 'string' || !sessionId) {
    return { status: 'no-session', sessionId: null, reason: 'no-explicit-session' };
  }
  return { status: 'captured', sessionId, reason: null };
}

export function inspectDeliveryHostCapabilities(host) {
  let remote;
  let workspaceChanges;
  let uiConversation;
  try { remote = host?.remote; } catch { remote = undefined; }
  try { workspaceChanges = host?.workspaceChanges; } catch { workspaceChanges = undefined; }
  try { uiConversation = host?.uiConversation; } catch { uiConversation = undefined; }
  const workspaceFiles = remote?.workspaceFiles;
  const canSubscribeWorkspaceChanges = typeof host?.subscribeWorkspaceChanges === 'function';
  const canSubscribePresented = typeof host?.subscribePresented === 'function';
  return {
    canListWorkspace: typeof workspaceFiles?.list === 'function',
    canReadWorkspace: typeof workspaceFiles?.read === 'function',
    canSubscribeWorkspaceChanges,
    canSubscribePresented,
    hasWorkspaceChangesService: typeof workspaceChanges?.summary === 'function',
    hasUiConversation: typeof uiConversation?.events?.register === 'function',
    refreshMode: canSubscribeWorkspaceChanges ? 'event+manual' : 'manual',
    workspaceChangesReason: canSubscribeWorkspaceChanges
      ? null
      : 'client inject is slots/sessions/theme/layout/remote/remote.session; workspace/changes is a Session event served by Host workspaceChanges.summary and consumed by ui-deliverables',
    presentedReason: canSubscribePresented
      ? null
      : 'present deliveries live in conversation turn deliverables; createPagePackageWaiter only observes plugin tool receipts',
  };
}

export function tryAttachWorkspaceChangeRefresh(host, onChange) {
  const cap = inspectDeliveryHostCapabilities(host);
  if (typeof host?.subscribeWorkspaceChanges !== 'function') {
    return { attached: false, reason: cap.workspaceChangesReason, unsubscribe() {} };
  }
  let alive = true;
  const returned = host.subscribeWorkspaceChanges((payload) => {
    if (alive && typeof onChange === 'function') onChange(payload);
  });
  return {
    attached: true,
    reason: null,
    unsubscribe() {
      alive = false;
      if (typeof returned === 'function') returned();
    },
  };
}

export function ingestWorkspaceEventFiles(sessionId, files, { existing = [] } = {}) {
  if (!sessionId) return [];
  const out = [];
  const seen = new Set();
  for (const item of existing) {
    const id = cockpitProductIdentity(item);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(item);
  }
  for (const file of files ?? []) {
    const rel = workspaceRelFromEventPath(typeof file === 'string' ? file : file?.path);
    if (!rel) continue;
    const kind = classifyWorkspaceFile(rel);
    if (!kind) continue;
    const item = {
      id: `file:${sessionId}:${rel}`,
      kind,
      title: rel.split('/').pop(),
      path: rel,
      sessionId,
      source: 'workspace-event',
    };
    const id = cockpitProductIdentity(item);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(item);
  }
  return out;
}

function emptySnapshot(epoch = 0, refreshMode = 'manual') {
  return {
    status: 'no-session',
    sessionId: null,
    files: [],
    truncated: false,
    error: null,
    epoch,
    refreshMode,
  };
}

export function createCockpitDelivery(adapters = {}) {
  const listDir = adapters.listDir;
  const read = adapters.read;
  const max = adapters.max;
  const dirDepth = adapters.dirDepth;
  const epoch = createNavigationEpoch();
  const listeners = new Set();
  let sessionId = null;
  let snapshot = emptySnapshot();
  let auto = { attached: false, unsubscribe() {} };

  const emit = () => {
    for (const listener of listeners) listener(snapshot);
  };
  const setSnapshot = (next) => {
    snapshot = next;
    emit();
    return snapshot;
  };

  const api = {
    captureSource(list, compositionSessionId) {
      const captured = captureDeliverySessionSource(list, compositionSessionId);
      api.setSessionId(captured.sessionId);
      return captured;
    },
    setSessionId(id) {
      const next = typeof id === 'string' && id ? id : null;
      if (next !== sessionId) {
        sessionId = next;
        const ticket = epoch.begin('delivery-session');
        epoch.settle(ticket.epoch);
        setSnapshot({ ...emptySnapshot(ticket.epoch, snapshot.refreshMode), sessionId: next, status: next ? 'empty' : 'no-session' });
      }
      return { status: next ? 'captured' : 'no-session', sessionId: next, reason: next ? null : 'no-explicit-session' };
    },
    getSessionId() {
      return sessionId;
    },
    getSnapshot() {
      return snapshot;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    inspectHost: inspectDeliveryHostCapabilities,
    attachHostEvents(host) {
      auto.unsubscribe();
      auto = tryAttachWorkspaceChangeRefresh(host, () => { void api.refresh(); });
      snapshot = { ...snapshot, refreshMode: auto.attached ? 'event+manual' : 'manual' };
      emit();
      return { attached: auto.attached, reason: auto.reason };
    },
    async refresh(options = {}) {
      const id = options.sessionId ?? sessionId;
      const ticket = epoch.begin('delivery-refresh');
      if (!id) {
        if (!epoch.isCurrent(ticket.epoch)) return snapshot;
        epoch.settle(ticket.epoch);
        return setSnapshot(emptySnapshot(ticket.epoch, snapshot.refreshMode));
      }
      sessionId = id;
      setSnapshot({
        ...snapshot,
        status: 'loading',
        sessionId: id,
        error: null,
        epoch: ticket.epoch,
      });
      try {
        const scan = await collectWorkspaceScan(listDir, id, {
          signal: options.signal ?? ticket.signal,
          max,
          dirDepth,
        });
        if (!epoch.isCurrent(ticket.epoch)) return snapshot;
        epoch.settle(ticket.epoch);
        const status = scan.status === 'error' || scan.status === 'no-session'
          ? scan.status
          : (scan.files.length ? 'ready' : 'empty');
        return setSnapshot({
          status,
          sessionId: id,
          files: scan.files,
          truncated: scan.truncated,
          error: scan.error,
          epoch: ticket.epoch,
          refreshMode: snapshot.refreshMode,
          lists: scan.lists,
        });
      } catch (error) {
        if (isSupersededRead(error) || !epoch.isCurrent(ticket.epoch)) return snapshot;
        epoch.settle(ticket.epoch);
        return setSnapshot({
          status: 'error',
          sessionId: id,
          files: [],
          truncated: false,
          error: 'refresh-failed',
          epoch: ticket.epoch,
          refreshMode: snapshot.refreshMode,
        });
      }
    },
    async readFile(path, options = {}) {
      const id = options.sessionId ?? sessionId;
      return readWorkspaceFileText(read, id, path, options);
    },
    ingestEventFiles(files, options = {}) {
      const id = options.sessionId ?? sessionId;
      if (!id) return [];
      return ingestWorkspaceEventFiles(id, files, { existing: options.existing ?? snapshot.files });
    },
    dispose() {
      auto.unsubscribe();
      epoch.dispose();
      listeners.clear();
    },
  };
  return api;
}
