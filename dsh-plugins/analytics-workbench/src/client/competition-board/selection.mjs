/** UI selection must not rewrite the in-flight FastAPI patch target. */

const inflightByAttempt = new Map();
let uiSelection = null;
const listeners = new Set();

export function setUiSelection(scope) {
  uiSelection = scope ? Object.freeze({ ...scope }) : null;
  emit();
}

export function beginInflight(scope) {
  if (!scope?.attempt_id || !scope.board_id) throw new Error('inflight scope requires attempt_id and board_id');
  inflightByAttempt.set(scope.attempt_id, Object.freeze({ ...scope }));
  emit();
  return scope.attempt_id;
}

export function endInflight(attemptId) {
  inflightByAttempt.delete(attemptId);
  emit();
}

export function getInflight(attemptId) {
  if (attemptId) return inflightByAttempt.get(attemptId) ?? null;
  const last = [...inflightByAttempt.values()].at(-1);
  return last ?? null;
}

export function getUiSelection() {
  return uiSelection;
}

export function getPatchTarget() {
  return getInflight() ?? uiSelection;
}

export function subscribeSelection(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function disposeSelectionUi() {
  uiSelection = null;
  listeners.clear();
}

export function resetInflightForTests() {
  inflightByAttempt.clear();
  uiSelection = null;
  listeners.clear();
}

function emit() {
  for (const listener of listeners) listener({ inflight: getInflight(), ui: uiSelection, target: getPatchTarget() });
}
