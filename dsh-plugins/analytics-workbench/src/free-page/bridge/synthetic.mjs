/** In-memory authorized result access. Host-side mock until P12 wires the Python service. */
import {
  DATA_SCOPE, FORBIDDEN_FIELDS, FORBIDDEN_OPS, MAX_CUMULATIVE_ROWS, MAX_PAGE_LIMIT,
  MAX_RESPONSE_BYTES, PAGE_TO_HOST_OPS, READ_MODES, SUMMARY_PREVIEW_ROWS,
  bridgeError, identity, record,
} from './contract.mjs';

const READ_FIELDS = new Set([
  'op', 'request_id', 'result_ref', 'data_ref', 'mode', 'cursor', 'limit', 'start', 'end', 'instance_id',
]);
const CANCEL_FIELDS = new Set(['op', 'request_id', 'instance_id']);

export function defaultSyntheticSnapshot({ owner = 'alice', rowCount = 120, ...overrides } = {}) {
  const rows = Array.from({ length: rowCount }, (_, index) => ({ i: index, label: `row-${index}`, value: index * 10 }));
  return {
    result_ref: 'result_fixture_1',
    owner,
    unit: 'CNY 元',
    time_range: { start: '2026-04-30', end: '2026-07-28' },
    queried_at: '2026-07-28T12:00:00.000+00:00',
    source: '合成结果夹具 · result_fixture_1',
    result_version: 1,
    expires_at_ms: null,
    rows,
    session_id: 'native_session_fixture',
    data_scope: DATA_SCOPE,
    ...overrides,
  };
}

export const UNBOUND_MANIFEST = Object.freeze({ result_refs: [], bindings: [] });
export const BOUND_MANIFEST = Object.freeze({
  result_refs: ['result_fixture_1'],
  bindings: [{
    result_ref: 'result_fixture_1',
    unit: 'CNY 元',
    time_range: { start: '2026-04-30', end: '2026-07-28' },
    result_version: 1,
  }],
});

function clone(value) {
  return structuredClone(value);
}

function timeRange(value) {
  if (!record(value) || Object.keys(value).length !== 2
    || typeof value.start !== 'string' || typeof value.end !== 'string'
    || !value.start || !value.end) {
    throw bridgeError('INVALID_PAGE');
  }
  return { start: value.start, end: value.end };
}

function manifestEntries(manifest) {
  if (manifest == null) return [];
  if (!record(manifest)) throw bridgeError('INVALID_PAGE');
  if (Object.keys(manifest).some(key => key !== 'bindings' && key !== 'result_refs')) {
    throw bridgeError('INVALID_PAGE');
  }
  const refs = manifest.result_refs ?? [];
  const bindings = manifest.bindings ?? [];
  if (!Array.isArray(refs) || !Array.isArray(bindings)) throw bridgeError('INVALID_PAGE');
  const entries = [];
  const seen = new Set();
  for (const item of refs) {
    if (!identity(item)) throw bridgeError('INVALID_PAGE');
    if (!seen.has(item)) {
      entries.push({ result_ref: item });
      seen.add(item);
    }
  }
  for (const item of bindings) {
    if (!record(item) || !identity(item.result_ref)) throw bridgeError('INVALID_PAGE');
    const allowed = new Set(['result_ref', 'data_ref', 'unit', 'time_range', 'result_version']);
    if (Object.keys(item).some(key => !allowed.has(key))) throw bridgeError('INVALID_PAGE');
    const entry = { result_ref: item.result_ref };
    if (item.unit != null) entry.unit = item.unit;
    if (item.time_range != null) entry.time_range = timeRange(item.time_range);
    if (item.result_version != null) entry.result_version = item.result_version;
    if (seen.has(item.result_ref)) {
      Object.assign(entries.find(existing => existing.result_ref === item.result_ref), entry);
    } else {
      entries.push(entry);
      seen.add(item.result_ref);
    }
  }
  return entries;
}

function requireActor(actor) {
  if (!actor || !identity(actor.actor_id) || !actor.capabilities?.has?.('dashboard:read')
    || !actor.data_scopes?.has?.(DATA_SCOPE)) {
    throw bridgeError('FORBIDDEN');
  }
}

export function createSyntheticAccess({ clock = () => Date.now(), actor } = {}) {
  const snapshots = new Map();
  const revoked = new Set();
  const dataRefs = new Map();
  const cancelled = new Set();
  const consumed = new Map();
  const cache = new Map();
  let handles = 0;

  function putSnapshot(payload) {
    const snapshot = {
      ...defaultSyntheticSnapshot(),
      ...payload,
      time_range: timeRange(payload.time_range ?? defaultSyntheticSnapshot().time_range),
      rows: clone(payload.rows ?? defaultSyntheticSnapshot().rows),
    };
    if (!identity(snapshot.result_ref) || !identity(snapshot.owner)) throw bridgeError('INVALID_PAGE');
    snapshots.set(snapshot.result_ref, snapshot);
    revoked.delete(snapshot.result_ref);
    for (const key of [...cache.keys()]) {
      if (key.includes(`:${snapshot.result_ref}:`)) cache.delete(key);
    }
    return snapshot;
  }

  function authorized(current, resultRef) {
    const snapshot = snapshots.get(resultRef);
    if (!snapshot || snapshot.owner !== current.actor_id) throw bridgeError('NOT_FOUND');
    if (revoked.has(resultRef)) throw bridgeError('RESULT_REVOKED');
    if (!current.data_scopes.has(snapshot.data_scope)) throw bridgeError('FORBIDDEN');
    if (snapshot.expires_at_ms != null && clock() >= snapshot.expires_at_ms) throw bridgeError('RESULT_STALE');
    return snapshot;
  }

  function matchBinding(snapshot, binding) {
    if (binding.unit != null && binding.unit !== snapshot.unit) throw bridgeError('RESULT_STALE');
    if (binding.time_range != null
      && (binding.time_range.start !== snapshot.time_range.start
        || binding.time_range.end !== snapshot.time_range.end)) {
      throw bridgeError('RESULT_STALE');
    }
    if (binding.result_version != null && binding.result_version !== snapshot.result_version) {
      throw bridgeError('RESULT_STALE');
    }
  }

  function parseRequest(request, allowed, op) {
    if (!record(request)) throw bridgeError('INVALID_PAGE');
    if (FORBIDDEN_FIELDS.some(field => Object.hasOwn(request, field))) throw bridgeError('BRIDGE_UNKNOWN_OP');
    if (FORBIDDEN_OPS.includes(request.op) || !PAGE_TO_HOST_OPS.includes(request.op)) {
      throw bridgeError('BRIDGE_UNKNOWN_OP');
    }
    if (request.op !== op) throw bridgeError('BRIDGE_UNKNOWN_OP');
    if (Object.keys(request).some(key => !allowed.has(key))) throw bridgeError('INVALID_PAGE');
    return request;
  }

  function raiseIfCancelled(current, requestId) {
    if (requestId && cancelled.has(`${current.actor_id}:${requestId}`)) throw bridgeError('RESULT_UNAVAILABLE');
  }

  function sliceRows(snapshot, request, mode) {
    const total = snapshot.rows.length;
    if (mode === 'summary') {
      const rows = clone(snapshot.rows.slice(0, SUMMARY_PREVIEW_ROWS));
      return { rows, cursor: total > rows.length ? cursorOf(snapshot, rows.length) : null };
    }
    const limit = request.limit ?? MAX_PAGE_LIMIT;
    if (!Number.isInteger(limit) || limit < 1 || limit > MAX_PAGE_LIMIT) throw bridgeError('INVALID_PAGE');
    if (mode === 'page') {
      if (request.start != null || request.end != null) throw bridgeError('INVALID_PAGE');
      const offset = request.cursor == null ? 0 : parseCursor(snapshot, request.cursor);
      const end = Math.min(offset + limit, total);
      return {
        rows: clone(snapshot.rows.slice(offset, end)),
        cursor: end < total ? cursorOf(snapshot, end) : null,
      };
    }
    if (request.cursor != null) throw bridgeError('INVALID_PAGE');
    const start = request.start ?? 0;
    const end = request.end ?? start + limit;
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end < start || end > total) {
      throw bridgeError('INVALID_PAGE');
    }
    if (end - start > MAX_PAGE_LIMIT) throw bridgeError('PACKAGE_TOO_LARGE');
    return { rows: clone(snapshot.rows.slice(start, end)), cursor: null };
  }

  function cursorOf(snapshot, offset) {
    return `v${snapshot.result_version}:${offset}`;
  }

  function parseCursor(snapshot, cursor) {
    if (typeof cursor !== 'string' || !/^v[1-9][0-9]{0,15}:[0-9]{1,16}$/.test(cursor)) {
      throw bridgeError('INVALID_PAGE');
    }
    const [versionText, offsetText] = cursor.slice(1).split(':');
    const version = Number(versionText);
    const offset = Number(offsetText);
    if (version !== snapshot.result_version) throw bridgeError('RESULT_STALE');
    if (offset > snapshot.rows.length) throw bridgeError('INVALID_PAGE');
    return offset;
  }

  function consume(current, instanceId, count) {
    const key = `${current.actor_id}:${instanceId ?? '_'}`;
    const used = (consumed.get(key) ?? 0) + count;
    if (used > MAX_CUMULATIVE_ROWS) throw bridgeError('PACKAGE_TOO_LARGE');
    consumed.set(key, used);
  }

  function bindingState(current = actor, manifest) {
    requireActor(current);
    const entries = manifestEntries(manifest);
    if (entries.length === 0) {
      return {
        binding_state: 'UNBOUND_SAMPLE',
        verified: false,
        refs: [],
        reasons: [],
        host_source: { endorses: 'result_provenance', does_not_endorse: 'page_dom' },
      };
    }
    const refs = [];
    const reasons = [];
    let verified = 0;
    for (const entry of entries) {
      const item = {
        result_ref: entry.result_ref, status: 'UNAVAILABLE', unit: null, time_range: null,
        queried_at: null, source: null, result_version: null,
      };
      try {
        const snapshot = authorized(current, entry.result_ref);
        matchBinding(snapshot, entry);
        Object.assign(item, {
          status: 'VERIFIED', unit: snapshot.unit, time_range: { ...snapshot.time_range },
          queried_at: snapshot.queried_at, source: snapshot.source, result_version: snapshot.result_version,
        });
        verified += 1;
      } catch (error) {
        item.status = error.code;
        reasons.push(error.code);
      }
      refs.push(item);
    }
    const state = verified === entries.length ? 'BOUND_VERIFIED' : 'BOUND_STALE';
    return {
      binding_state: state,
      verified: state === 'BOUND_VERIFIED',
      refs,
      reasons,
      host_source: { endorses: 'result_provenance', does_not_endorse: 'page_dom' },
    };
  }

  function authorize(current = actor, request, manifest) {
    requireActor(current);
    const payload = parseRequest(request, READ_FIELDS, 'data.read');
    const listed = Object.fromEntries(manifestEntries(manifest).map(entry => [entry.result_ref, entry]));
    const hasRef = Object.hasOwn(payload, 'result_ref');
    const hasData = Object.hasOwn(payload, 'data_ref');
    if (hasRef === hasData) throw bridgeError('INVALID_PAGE');
    let snapshot;
    let binding;
    if (hasData) {
      if (!identity(payload.data_ref)) throw bridgeError('INVALID_PAGE');
      const issued = dataRefs.get(payload.data_ref);
      if (!issued || issued.owner !== current.actor_id) throw bridgeError('NOT_FOUND');
      if (!listed[issued.result_ref]) throw bridgeError('FORBIDDEN');
      snapshot = authorized(current, issued.result_ref);
      if (snapshot.result_version !== issued.result_version) throw bridgeError('RESULT_STALE');
      binding = listed[issued.result_ref];
    } else {
      if (!identity(payload.result_ref)) throw bridgeError('INVALID_PAGE');
      if (!listed[payload.result_ref]) throw bridgeError('FORBIDDEN');
      snapshot = authorized(current, payload.result_ref);
      binding = listed[payload.result_ref];
    }
    matchBinding(snapshot, binding);
    return { snapshot, binding, payload };
  }

  async function read(request, { actor: current = actor, manifest } = {}) {
    const { snapshot, binding, payload } = authorize(current, request, manifest);
    if (payload.request_id != null && !identity(payload.request_id)) throw bridgeError('INVALID_PAGE');
    raiseIfCancelled(current, payload.request_id);
    const mode = payload.mode ?? 'summary';
    if (!READ_MODES.includes(mode)) throw bridgeError('INVALID_PAGE');
    const cacheKey = `${current.actor_id}:${snapshot.result_ref}:${snapshot.result_version}`;
    const cached = cache.get(cacheKey) ?? snapshot;
    cache.set(cacheKey, cached);
    const { rows, cursor } = sliceRows(cached, payload, mode);
    const dataRef = `data_${(++handles).toString(16).padStart(8, '0')}`;
    dataRefs.set(dataRef, {
      owner: current.actor_id, result_ref: snapshot.result_ref, result_version: snapshot.result_version,
    });
    const body = {
      ok: true,
      op: 'data.read',
      mode,
      result_ref: snapshot.result_ref,
      data_ref: dataRef,
      result_version: snapshot.result_version,
      summary: {
        unit: snapshot.unit,
        time_range: { ...snapshot.time_range },
        queried_at: snapshot.queried_at,
        source: snapshot.source,
        row_count: snapshot.rows.length,
      },
      rows,
      cursor,
      binding_state: 'BOUND_VERIFIED',
      host_source: {
        label: snapshot.source,
        endorses: 'result_provenance',
        does_not_endorse: 'page_dom',
        session_id: snapshot.session_id || null,
      },
    };
    const encoded = JSON.stringify(body);
    if (new TextEncoder().encode(encoded).length > MAX_RESPONSE_BYTES) throw bridgeError('PACKAGE_TOO_LARGE');
    consume(current, payload.instance_id, rows.length);
    raiseIfCancelled(current, payload.request_id);
    return body;
  }

  function cancel(request, current = actor) {
    requireActor(current);
    const payload = parseRequest(request, CANCEL_FIELDS, 'data.cancel');
    if (!identity(payload.request_id)) throw bridgeError('INVALID_PAGE');
    cancelled.add(`${current.actor_id}:${payload.request_id}`);
    return { request_id: payload.request_id, status: 'CANCELLED' };
  }

  function revoke(resultRef, current = actor) {
    requireActor(current);
    if (!identity(resultRef)) throw bridgeError('INVALID_PAGE');
    const snapshot = snapshots.get(resultRef);
    if (!snapshot || snapshot.owner !== current.actor_id) throw bridgeError('NOT_FOUND');
    revoked.add(resultRef);
  }

  return {
    putSnapshot,
    read,
    cancel,
    revoke,
    bindingState,
    authorize,
    _snapshots: snapshots,
  };
}
