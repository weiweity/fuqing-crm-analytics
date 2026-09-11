/**
 * B0 synthetic-only policy, pinned to DSH 183f08e9c6dde7e36cd2318eaee70b0da08fb35e.
 * Pure functions: no IO, credentials, mutable session state, or runtime imports.
 * Wire references: packages/client/connection/src/client/rpc.ts:32-50;
 * packages/api/gateway/src/stream-protocol.ts:243-308;
 * packages/api/session-controller/src/types.ts:306-351,375-562;
 * packages/api/workspace-controller/src/types.ts:15-29,108-130;
 * packages/settings/settings/src/types.ts:33-74.
 *
 * Broker responsibilities (NOT supplied by these pure functions): authenticate
 * the one synthetic actor; build scope server-side; validate POST/path/envelope
 * consistency; enforce body/frame limits; atomically journal one in-flight task;
 * bind each WS streamId to the authorized endpoint and connection generation;
 * never reuse an ID within a connection, including after cancel/end; keep DSH
 * credentials server-side; sanitize upstream error envelopes. Fetch is denied.
 *
 * scope: {sessionId, workspaceId, workspacePath, inFlight:boolean,
 *   presetId?:string, actorId?:string, requestActorId?:string,
 *   seenStreamIds?:Set<string>|string[], activeStreamIds?:Set<string>|string[]}
 * Optional actor fields are a broker assertion, never browser-supplied identity.
 * Stream ID sets are snapshots supplied by the broker before each decision.
 */

export const DSH_B0_SOURCE_SHA = '183f08e9c6dde7e36cd2318eaee70b0da08fb35e';
export const MAX_PROMPT_CHARS = 8000;
export const MAX_HISTORY_MESSAGES = 100;
export const SETTINGS_NAMESPACES = Object.freeze(['locale', 'ui-theme', 'ui-chat', 'ui-conversation', 'ui-onboarding']);

const deny = (reason) => ({ allowed: false, reason });
const allow = () => ({ allowed: true });
const own = (object, key) => Object.hasOwn(object, key);
const record = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
  && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const bounded = (value, max = 256) => typeof value === 'string' && value.length > 0 && value.length <= max;
const integer = (value) => Number.isSafeInteger(value) && value >= 0;
const shape = (value, required = [], optional = []) => record(value)
  && required.every((key) => own(value, key))
  && Reflect.ownKeys(value).every((key) => typeof key === 'string' && (required.includes(key) || optional.includes(key)));
const empty = (value) => shape(value);
const inSet = (set, value) => set instanceof Set ? set.has(value) : Array.isArray(set) && set.includes(value);
const preset = (scope) => scope.presetId ?? 'analytics-b0';
function twoSessionList(scope) {
  if (!Array.isArray(scope.sessionIds)) return null;
  if (scope.sessionIds.length !== 2 || new Set(scope.sessionIds).size !== 2 || !scope.sessionIds.every((id) => bounded(id))) return null;
  return bounded(scope.sessionId) && scope.sessionIds.includes(scope.sessionId) ? scope.sessionIds : null;
}
function allowlist(scope) {
  if (scope.sessionIds !== undefined) return twoSessionList(scope);
  return bounded(scope.sessionId) ? [scope.sessionId] : null;
}
const ownSession = (scope, sessionId) => allowlist(scope)?.includes(sessionId) === true;
export function sessionAllowed(scope, sessionId) {
  return record(scope) && ownSession(scope, sessionId);
}
const scopeOkay = (scope) => record(scope) && allowlist(scope) !== null && bounded(scope.sessionId) && bounded(scope.workspaceId)
  && bounded(scope.workspacePath, 4096) && scope.workspacePath.startsWith('/')
  && (scope.requestActorId === undefined || (bounded(scope.actorId) && scope.requestActorId === scope.actorId));
const addressOkay = (value, scope) => shape(value, ['kind', 'sessionId'])
  && value.kind === 'session' && ownSession(scope, value.sessionId);
const budgetOkay = (value) => value === undefined || (integer(value) && value >= 1 && value <= MAX_HISTORY_MESSAGES);

function requestOf(payload) {
  return shape(payload, ['args']) && shape(payload.args, ['request']) ? payload.args.request : null;
}

function emptyArgs(payload) {
  return shape(payload, ['args']) && empty(payload.args);
}

/** endpoint name + Typert payload, NOT an HTTP request envelope. */
export function authorizeHttp(method, payload, scope) {
  if (!scopeOkay(scope)) return deny('invalid-or-foreign-actor-scope');
  if (['session/modelCatalog', 'agentPresets/list', 'settings/describe', 'session/canOpenWorkspacePath',
    'settings/canOpenAgentPresetDirectory'].includes(method)) {
    return emptyArgs(payload) ? allow() : deny('unexpected-metadata-arguments');
  }
  // Native session sidebar boot: manager.ts refreshList() invokes list({}).
  if (method === 'session/list') {
    return shape(payload, ['args']) && shape(payload.args, ['_request']) && empty(payload.args._request)
      ? allow() : deny('unexpected-session-list-arguments');
  }
  const request = requestOf(payload);
  if (method === 'session/page') {
    return shape(request, ['address', 'throughSeq'], ['beforeSeq', 'maxMessages'])
      && addressOkay(request.address, scope) && integer(request.throughSeq)
      && (!own(request, 'beforeSeq') || (integer(request.beforeSeq) && request.beforeSeq <= request.throughSeq))
      && budgetOkay(request.maxMessages) ? allow() : deny('invalid-session-page');
  }
  if (method === 'session/cancel') {
    return shape(request, ['sessionId']) && ownSession(scope, request.sessionId)
      ? allow() : deny('invalid-session-cancel');
  }
  if (method === 'session/prompt') {
    if (scope.inFlight !== false) return deny('one-task-already-in-flight');
    if (!shape(request, ['requestId', 'sessionId', 'mode', 'content'], ['clientTimeZone'])
      || !bounded(request.requestId, 128) || !/^[A-Za-z0-9_.:-]+$/.test(request.requestId)
      || !ownSession(scope, request.sessionId) || request.mode !== 'queue'
      || !Array.isArray(request.content) || request.content.length !== 1
      || !shape(request.content[0], ['type', 'text']) || request.content[0].type !== 'text'
      || !bounded(request.content[0].text, MAX_PROMPT_CHARS) || !request.content[0].text.trim()
      || (own(request, 'clientTimeZone') && !['Asia/Shanghai', 'UTC'].includes(request.clientTimeZone))) {
      return deny('invalid-text-only-prompt');
    }
    return allow();
  }
  return deny('endpoint-not-allowed');
}

/** Authorize a decoded remote.mux client frame. Broker owns atomic ID tracking. */
export function authorizeStream(message, scope) {
  if (!scopeOkay(scope)) return deny('invalid-or-foreign-actor-scope');
  if (shape(message, ['type', 'streamId']) && message.type === 'cancel' && bounded(message.streamId, 128)) {
    return inSet(scope.activeStreamIds, message.streamId) ? allow() : deny('unknown-stream-cancel');
  }
  if (!shape(message, ['type', 'streamId', 'endpoint', 'payload']) || message.type !== 'open'
    || !bounded(message.streamId, 128)) return deny('invalid-stream-frame');
  if (inSet(scope.seenStreamIds, message.streamId)) return deny('stream-id-reuse');
  if (['$events', 'session/control', 'workspace/follow'].includes(message.endpoint)) {
    return emptyArgs(message.payload) ? allow() : deny('unexpected-stream-arguments');
  }
  if (message.endpoint === 'session/follow') {
    const request = requestOf(message.payload);
    return shape(request, ['address'], ['maxMessages', 'assistantStream'])
      && addressOkay(request.address, scope) && budgetOkay(request.maxMessages)
      && (!own(request, 'assistantStream') || request.assistantStream === true)
      ? allow() : deny('invalid-session-follow');
  }
  return deny('stream-endpoint-not-allowed');
}

/** No @RemoteFetch endpoint is part of B0, including uploads and file reads. */
export function authorizeFetch() { return deny('fetch-default-deny'); }

// Defense-in-depth for extension JSON in this synthetic session. This is not
// semantic DLP: strings inside an approved tool result remain tool-result data.
// Reject structured foreign identities, secret-bearing fields, and unexpected
// host paths. Explicit projection functions below also discard unknown fields.
function scopedJson(value, scope, depth = 0) {
  if (depth > 32) return null;
  if (value === null || typeof value === 'boolean') return value;
  if (typeof value === 'string') return value.length <= 131072 ? value : null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (Array.isArray(value)) {
    if (value.length > 2000) return null;
    const output = [];
    for (const item of value) {
      const next = scopedJson(item, scope, depth + 1);
      if (next === null && item !== null) return null;
      output.push(next);
    }
    return output;
  }
  if (!record(value)) return null;
  const output = {};
  for (const [key, item] of Object.entries(value)) {
    if (['__proto__', 'constructor', 'prototype'].includes(key)) return null;
    if (/^(api[_-]?key|authorization|cookie|set-cookie|secret|credentials?|access[_-]?token)$/i.test(key)) return null;
    if (['sessionId', 'parentSessionId', 'childSessionId', 'parentSession'].includes(key) && item !== scope.sessionId) return null;
    if (key === 'workspaceId' && item !== scope.workspaceId) return null;
    if (['actorId', 'ownerId'].includes(key) && item !== scope.actorId) return null;
    if (['cwd', 'workspacePath', 'path', 'home'].includes(key) && typeof item === 'string'
      && item.startsWith('/') && item !== scope.workspacePath && !item.startsWith(`${scope.workspacePath}/`)) return null;
    const next = scopedJson(item, scope, depth + 1);
    if (next === null && item !== null) return null;
    output[key] = next;
  }
  return output;
}

const projectionKeys = new Set(['title', 'sessionListMetadata', 'modelSelection', 'imageLimits', 'agentPreset', 'sessionStats']);
function projections(value, scope) {
  if (!record(value) || !integer(value.asOfSeq) || !record(value.values)) return { asOfSeq: 0, values: {} };
  const values = {};
  for (const [key, item] of Object.entries(value.values)) {
    if (!projectionKeys.has(key)) continue;
    if (key === 'agentPreset' && item !== null && item !== preset(scope)) continue;
    const safe = scopedJson(item, scope);
    if (safe !== null || item === null) values[key] = safe;
  }
  return { asOfSeq: value.asOfSeq, values };
}

function summary(value, scope) {
  if (!record(value) || !ownSession(scope, value.sessionId) || value.origin === 'subagent'
    || (value.cwd !== undefined && value.cwd !== scope.workspacePath)
    || (value.parentSessionId !== undefined && value.parentSessionId !== value.sessionId)) return null;
  return { sessionId: value.sessionId, updatedAt: Number.isFinite(value.updatedAt) ? value.updatedAt : 0,
    running: value.running === true, blank: value.blank === true, cwd: scope.workspacePath,
    ...(value.projections ? { projections: projections(value.projections, scope) } : {}) };
}

function workspace(value, scope) {
  if (!record(value) || value.workspaceId !== scope.workspaceId || value.path !== scope.workspacePath) return null;
  return { workspaceId: scope.workspaceId, path: scope.workspacePath,
    title: typeof value.title === 'string' ? value.title.slice(0, 200) : 'B0 Synthetic',
    sessionIds: Array.isArray(value.sessionIds) ? value.sessionIds.filter((id) => ownSession(scope, id)) : [],
    createdAt: typeof value.createdAt === 'string' ? value.createdAt : '',
    updatedAt: typeof value.updatedAt === 'string' ? value.updatedAt : '' };
}

function historyRecord(value, scope) {
  if (!record(value) || value.type !== 'event' || !record(value.event)) return null;
  const event = value.event;
  if (!bounded(event.type) || !integer(event.seq) || !Number.isFinite(event.time)) return null;
  const data = scopedJson(event.data, scope);
  if (data === null && event.data !== null) return null;
  return { type: 'event', event: { type: event.type, seq: event.seq, time: event.time, data,
    ...(event.ignorable === true ? { ignorable: true } : {}),
    ...(Array.isArray(event.sourceEventSeqs) && event.sourceEventSeqs.every(integer) ? { sourceEventSeqs: [...event.sourceEventSeqs] } : {}),
    ...(event.surfaceOp === 'append' ? { surfaceOp: 'append' } : {}),
    ...(shape(event.surfaceOp, ['op', 'start', 'end']) && event.surfaceOp.op === 'replace'
      && integer(event.surfaceOp.start) && integer(event.surfaceOp.end)
      ? { surfaceOp: { ...event.surfaceOp } } : {}) } };
}

function settingsView(value, scope) {
  if (!record(value) || !Array.isArray(value.namespaces)) return null;
  const namespaces = value.namespaces.flatMap((entry) => {
    if (!record(entry) || !SETTINGS_NAMESPACES.includes(entry.ns) || !record(entry.value)) return [];
    const fields = { locale: ['preference'], 'ui-theme': ['preference', 'fontSize'], 'ui-chat': ['transcriptView'],
      'ui-conversation': ['busyEnter'], 'ui-onboarding': ['welcomeNoticeVersion'] }[entry.ns];
    const selected = Object.fromEntries(fields.filter((field) => own(entry.value, field)).map((field) => [field, entry.value[field]]));
    if (entry.ns === 'ui-conversation') selected.busyEnter = 'queue';
    const safe = scopedJson(selected, scope);
    const schema = scopedJson(entry.schema, scope);
    if (safe === null || schema === null) return [];
    return [{ ns: entry.ns, schema, value: safe, applies: entry.applies === 'restart' ? 'restart' : 'live',
      secrets: [], revision: integer(entry.revision) ? entry.revision : 0 }];
  });
  return { writable: false, hasDocument: false, namespaces };
}

/** Input is result.value, not the RPC server-response envelope. */
export function filterHttpResult(method, value, scope) {
  if (!scopeOkay(scope)) return null;
  if (['session/prompt', 'session/cancel'].includes(method)) return value?.accepted === true ? { accepted: true } : null;
  if (['session/canOpenWorkspacePath', 'settings/canOpenAgentPresetDirectory'].includes(method)) return false;
  if (method === 'session/list') return record(value) && Array.isArray(value.items)
    ? { items: value.items.map((item) => summary(item, scope)).filter(Boolean) } : null;
  if (method === 'session/page') return record(value) && Array.isArray(value.records)
    ? { records: value.records.map((item) => historyRecord(item, scope)).filter(Boolean), hasMore: value.hasMore === true } : null;
  if (method === 'settings/describe') return settingsView(value, scope);
  if (method === 'agentPresets/list') {
    if (!record(value) || !Array.isArray(value.presets)) return null;
    return { authorable: false, presets: value.presets.filter((row) => record(row) && row.id === preset(scope) && row.trust === 'system').map((row) => ({
      id: preset(scope), trust: 'system', isDefault: row.isDefault === true,
      ...(typeof row.name === 'string' ? { name: row.name.slice(0, 200) } : {}),
      ...(typeof row.description === 'string' ? { description: row.description.slice(0, 1000) } : {}),
      ...(row.broken !== undefined ? { broken: 'B0 preset unavailable' } : {}),
    })) };
  }
  if (method === 'session/modelCatalog') {
    if (!record(value) || !record(value.default) || !Array.isArray(value.groups)) return null;
    const selection = (item) => record(item) && bounded(item.provider) && bounded(item.model)
      ? { provider: item.provider, model: item.model, ...(bounded(item.reasoningEffort) ? { reasoningEffort: item.reasoningEffort } : {}) } : null;
    const selected = selection(value.default);
    if (!selected) return null;
    const groups = value.groups.filter((row) => record(row) && row.id === selected.provider && Array.isArray(row.models)).map((row) => ({
      id: row.id, name: typeof row.name === 'string' ? row.name.slice(0, 200) : row.id,
      models: row.models.filter((model) => record(model) && model.id === selected.model).map((model) => ({
        id: model.id, name: typeof model.name === 'string' ? model.name.slice(0, 200) : model.id,
      })),
    }));
    return { default: selected, routableProviders: [selected.provider], groups, failures: [] };
  }
  return null;
}

/** Input is item.value; broker binds endpoint from its admitted streamId map. */
export function filterStreamItem(endpoint, value, scope) {
  if (!scopeOkay(scope) || !record(value)) return null;
  if (endpoint === '$events') {
    if (value.type === 'ready' && bounded(value.clientId)) return { type: 'ready', clientId: value.clientId, host: { home: '/synthetic' } };
    if (value.type !== 'emit' || !Array.isArray(value.args)) return null;
    const args = value.args;
    if (value.event === 'api-session/added' && args.length === 1) {
      const row = summary(args[0], scope);
      return row ? { type: 'emit', event: value.event, args: [row] } : null;
    }
    if (!ownSession(scope, args[0])) return null;
    if (value.event === 'api-session/removed' && args.length === 1) return { type: 'emit', event: value.event, args: [args[0]] };
    if (value.event === 'api-session/status' && args.length === 2 && typeof args[1] === 'boolean') return { type: 'emit', event: value.event, args: [args[0], args[1]] };
    if (value.event === 'api-session/activity' && args.length === 2 && Number.isFinite(args[1])) return { type: 'emit', event: value.event, args: [args[0], args[1]] };
    return null;
  }
  if (endpoint === 'workspace/follow') {
    const ownIds = (items, test) => Array.isArray(items) ? items.filter(test) : [];
    if (value.type === 'baseline' && record(value.value) && Array.isArray(value.value.items)) return {
      type: 'baseline', value: { items: value.value.items.map((item) => workspace(item, scope)).filter(Boolean),
        archivedSessionIds: ownIds(value.value.archivedSessionIds, (id) => ownSession(scope, id)) } };
    if (value.type === 'upsert') { const item = workspace(value.workspace, scope); return item ? { type: 'upsert', workspace: item } : null; }
    if (value.type === 'remove' && value.workspaceId === scope.workspaceId) return { type: 'remove', workspaceId: scope.workspaceId };
    if (value.type === 'order') return { type: 'order', workspaceIds: ownIds(value.workspaceIds, (id) => id === scope.workspaceId) };
    if (value.type === 'archived') return { type: 'archived', archivedSessionIds: ownIds(value.archivedSessionIds, (id) => ownSession(scope, id)) };
    return null;
  }
  if (endpoint === 'session/control') {
    const listed = allowlist(scope) ?? [];
    if (value.type === 'baseline' && record(value.value)) {
      const output = { queues: {}, jobs: {}, projections: {} };
      for (const key of ['queues', 'jobs', 'projections']) {
        if (!record(value.value[key])) continue;
        for (const sessionId of listed) {
          if (!own(value.value[key], sessionId)) continue;
          const item = value.value[key][sessionId];
          const bound = { ...scope, sessionId };
          const safe = key === 'projections' ? projections(item, bound) : scopedJson(item, bound);
          if (safe !== null) output[key][sessionId] = safe;
        }
      }
      return { type: 'baseline', value: output };
    }
    if (!ownSession(scope, value.sessionId)) return null;
    const bound = { ...scope, sessionId: value.sessionId };
    if (value.type === 'queue' || value.type === 'jobs') {
      const key = value.type === 'queue' ? 'items' : 'jobs';
      const safe = Array.isArray(value[key]) ? scopedJson(value[key], bound) : null;
      return safe === null ? null : { type: value.type, sessionId: value.sessionId, [key]: safe };
    }
    if (value.type === 'projection' && projectionKeys.has(value.key) && integer(value.seq)) {
      if (value.key === 'agentPreset' && value.value !== null && value.value !== preset(scope)) return null;
      const safe = scopedJson(value.value, bound);
      return safe === null && value.value !== null ? null : { type: 'projection', sessionId: value.sessionId, key: value.key, value: safe, seq: value.seq };
    }
    return null;
  }
  if (endpoint === 'session/follow') {
    if (value.type === 'snapshot') {
      const header = value.header;
      if (!record(header) || header.id !== scope.sessionId || header.origin === 'subagent'
        || (header.cwd !== undefined && header.cwd !== scope.workspacePath)
        || (header.agentPreset !== undefined && header.agentPreset !== preset(scope))
        || (header.parentSession !== undefined && header.parentSession !== scope.sessionId)
        || !integer(value.cursor) || !Array.isArray(value.records)) return null;
      const output = { type: 'snapshot', header: { version: header.version, id: scope.sessionId,
        createdAt: header.createdAt, isSeeded: header.isSeeded === true, cwd: scope.workspacePath,
        ...(header.agentPreset === preset(scope) ? { agentPreset: preset(scope) } : {}) }, cursor: value.cursor,
      records: value.records.map((item) => historyRecord(item, scope)).filter(Boolean), hasMore: value.hasMore === true,
      projections: projections(value.projections, scope) };
      if (value.assistantStream !== undefined) {
        const safe = scopedJson(value.assistantStream, scope);
        if (safe !== null) output.assistantStream = safe;
      }
      return output;
    }
    if (value.type === 'event') return historyRecord(value, scope);
    if (value.type === 'assistant-stream' && record(value.frame)
      && ['start', 'chunk', 'end'].includes(value.frame.type)) {
      const safe = scopedJson(value.frame, scope);
      return safe === null ? null : { type: 'assistant-stream', frame: safe };
    }
  }
  return null;
}
