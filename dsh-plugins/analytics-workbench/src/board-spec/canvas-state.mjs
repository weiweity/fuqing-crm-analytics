import { applyPatch, parseRollback } from './schema.mjs';
import { interpretBoard } from './interpret.mjs';
import { proposeAskLocal } from './ask.mjs';

function fail(code, message) {
  return { ok: false, error: { code, message } };
}

/**
 * @param {object} spec
 * @param {object} facts
 */
export function createCanvasState(spec, facts) {
  const view = interpretBoard(spec, facts);
  if (!view.ok) return view;
  return {
    ok: true,
    value: {
      spec,
      facts,
      history: [spec],
      tab: 'board',
      selected_block_id: null,
      ask: '',
      pending_patch: null,
    },
  };
}

export function setTab(state, tab) {
  if (!['board', 'links', 'browser'].includes(tab)) {
    return fail('CANVAS_TAB', `非法 tab: ${tab}`);
  }
  return { ok: true, value: { ...state, tab } };
}

export function selectBlock(state, blockId) {
  const view = interpretBoard(state.spec, state.facts);
  if (!view.ok) return view;
  if (!view.value.blocks.some((b) => b.block_id === blockId)) {
    return fail('CANVAS_SELECT', `没有 block_id ${blockId}`);
  }
  return { ok: true, value: { ...state, selected_block_id: blockId, pending_patch: null } };
}

export function setAsk(state, ask) {
  return { ok: true, value: { ...state, ask: typeof ask === 'string' ? ask : '' } };
}

export function visibleBlocks(state) {
  const view = interpretBoard(state.spec, state.facts);
  if (!view.ok) return [];
  const blocks = view.value.blocks;
  if (state.tab === 'links') return blocks.filter((b) => b.kind === 'LINK');
  if (state.tab === 'browser') return [];
  return blocks;
}

export function stageTitlePatch(state) {
  return proposeAskLocal(state);
}

export function cancelPatch(state) {
  return { ok: true, value: { ...state, pending_patch: null } };
}

export function confirmPatch(state) {
  if (!state.pending_patch) return fail('CANVAS_NO_PENDING', '没有待确认的 PATCH');
  const next = applyPatch(state.spec, state.pending_patch);
  if (!next.ok) return next;
  return {
    ok: true,
    value: {
      ...state,
      spec: next.value,
      history: [...state.history, next.value],
      pending_patch: null,
      ask: '',
    },
  };
}

export function rollbackTo(state, toVersion) {
  const parsed = parseRollback({ board_id: state.spec.board_id, to_version: toVersion });
  if (!parsed.ok) return parsed;
  const found = state.history.find((s) => s.version === toVersion);
  if (!found) return fail('ROLLBACK_MISSING', `没有 version ${toVersion}`);
  return {
    ok: true,
    value: {
      ...state,
      spec: found,
      selected_block_id: null,
      pending_patch: null,
      ask: '',
    },
  };
}
