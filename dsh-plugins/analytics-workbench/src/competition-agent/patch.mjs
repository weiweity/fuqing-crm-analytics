/** Controlled patch codec. STYLE_ONLY does not query; FILTER_CHANGE creates a new run. */

const SCRIPTISH = ['<script', 'javascript:', 'onerror=', 'eval(', '../', '/etc/'];
const INTENTS = new Set(['STYLE_ONLY', 'FILTER_CHANGE', 'STRUCTURE']);

function unsafe(value) {
  if (typeof value === 'string') {
    const lowered = value.toLowerCase();
    return SCRIPTISH.some(token => lowered.includes(token));
  }
  if (Array.isArray(value)) return value.some(unsafe);
  if (value && typeof value === 'object') {
    return Object.keys(value).some(unsafe) || Object.values(value).some(unsafe);
  }
  return false;
}

export function planPatch({ intent, payload, selection, inFlight }) {
  if (!INTENTS.has(intent)) throw new Error('invalid intent');
  if (unsafe(payload) || unsafe(selection) || unsafe(inFlight)) throw new Error('MODEL_INVALID_PATCH');
  const target = inFlight || selection;
  if (!target?.board_id || !target?.block_id || !target?.base_version) throw new Error('missing selection');
  const ignored = Boolean(inFlight && selection && (
    selection.board_id !== inFlight.board_id
    || selection.block_id !== inFlight.block_id
    || selection.base_version !== inFlight.base_version
  ));
  const queries = intent === 'FILTER_CHANGE';
  if (intent === 'STYLE_ONLY' && payload?.filter_change) throw new Error('MODEL_INVALID_PATCH');
  if (intent === 'FILTER_CHANGE' && !payload?.filter_change) throw new Error('MODEL_INVALID_PATCH');
  return Object.freeze({
    schema_version: 'competition-diagnosis-patch-plan/v1',
    queries,
    creates_new_run: queries,
    apply_status: queries ? 'NOT_CONNECTED' : 'PLANNED_OFFLINE',
    ignored_ui_selection: ignored,
    in_flight_target: Object.freeze({
      board_id: target.board_id,
      block_id: target.block_id,
      base_version: target.base_version,
    }),
    live_transport: 'NOT_CONNECTED',
  });
}
