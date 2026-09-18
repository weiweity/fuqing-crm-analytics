/** Per-page error boundary. Failures do not create a saved version. */

export const PAGE_STATES = Object.freeze(['idle', 'running', 'stopped', 'error', 'restoring']);

export function createErrorBoundary({ pageId, version } = {}) {
  let state = {
    status: 'idle',
    pageId: pageId ?? null,
    version: version ?? 0,
    reason: '',
    code: null,
    recoverable: true,
    hostAvailable: true,
  };
  const listeners = new Set();
  const emit = (patch) => {
    state = { ...state, ...patch, hostAvailable: true };
    for (const listener of listeners) listener(state);
  };

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    running(next = {}) {
      emit({ status: 'running', reason: '', code: null, ...next });
    },
    stopped(reason = '页面已停止') {
      emit({ status: 'stopped', reason, code: 'PAGE_STOPPED' });
    },
    fail(code, reason) {
      emit({ status: 'error', code, reason, recoverable: true });
    },
    restoring(next = {}) {
      emit({ status: 'restoring', reason: '正在恢复已保存版本', code: null, ...next });
    },
    restored(next = {}) {
      emit({ status: 'running', reason: '', code: null, ...next });
    },
  };
}

export function hostRecoveryCopy(state) {
  if (!state || state.status === 'running' || state.status === 'idle') return '';
  if (state.status === 'stopped') return '页面已停止。宿主的重启与已保存版本入口仍可用。';
  if (state.status === 'restoring') return '正在恢复已保存版本。';
  return `页面失败：${state.reason || '未知错误'}。宿主资料库、版本和重启入口仍可用。`;
}
