/** a7.selected_edit port. UI selection cannot rewrite an in-flight FastAPI target. */

import { SELECTED_EDIT_PORT } from './family.mjs';

const OPAQUE = /^[A-Za-z0-9_.:-]{1,128}$/;
const INTENTS = new Set(['STYLE_ONLY', 'FILTER_CHANGE', 'STRUCTURE']);

export function selectedEditEvent(input) {
  const board_id = input?.board_id;
  const block_id = input?.block_id;
  const base_version = input?.base_version;
  const intent = input?.intent;
  if (typeof board_id !== 'string' || !OPAQUE.test(board_id)) throw new Error('invalid board_id');
  if (typeof block_id !== 'string' || !OPAQUE.test(block_id)) throw new Error('invalid block_id');
  if (!Number.isInteger(base_version) || base_version < 1) throw new Error('invalid base_version');
  if (!INTENTS.has(intent)) throw new Error('invalid intent');
  return Object.freeze({
    port_id: SELECTED_EDIT_PORT,
    board_id,
    block_id,
    base_version,
    intent,
  });
}

export function bindInFlight(inFlight, selection) {
  if (inFlight) {
    return Object.freeze({
      target: inFlight,
      ignored_ui_selection: Boolean(selection) && (
        selection.board_id !== inFlight.board_id
        || selection.block_id !== inFlight.block_id
        || selection.base_version !== inFlight.base_version
      ),
    });
  }
  return Object.freeze({ target: selection, ignored_ui_selection: false });
}
