import test from 'node:test';
import assert from 'node:assert/strict';
import { authorizeHttp, authorizeStream, authorizeFetch, filterHttpResult, filterStreamItem, sessionAllowed } from './gateway-policy.mjs';

const scope = Object.freeze({ actorId: 'b0-actor', requestActorId: 'b0-actor', sessionId: 'b0-session',
  workspaceId: 'b0-workspace', workspacePath: '/synthetic/workspace', inFlight: false,
  presetId: 'analytics-b0', seenStreamIds: new Set(), activeStreamIds: new Set() });
const empty = () => ({ args: {} });
const payload = (request) => ({ args: { request } });
const address = () => ({ kind: 'session', sessionId: scope.sessionId });
const prompt = () => ({ requestId: 'request-1', sessionId: scope.sessionId, mode: 'queue',
  content: [{ type: 'text', text: '哪个渠道复购更强？' }], clientTimeZone: 'Asia/Shanghai' });
const open = (endpoint, streamId = 'stream-1', value = empty()) => ({ type: 'open', streamId, endpoint, payload: value });
const ownSummary = () => ({ sessionId: scope.sessionId, updatedAt: 10, running: false, blank: false,
  cwd: scope.workspacePath, projections: { asOfSeq: 1, values: { title: 'B0', agentPreset: 'analytics-b0' } } });
const ownWorkspace = () => ({ workspaceId: scope.workspaceId, path: scope.workspacePath, title: 'B0',
  sessionIds: [scope.sessionId, 'other-session'], createdAt: '2026-09-05T00:00:00Z', updatedAt: '2026-09-05T00:00:00Z' });
const event = (data = { content: [{ type: 'text', text: 'Synthetic only' }] }) => ({ type: 'event',
  event: { type: 'assistant/message', seq: 1, time: 10, data } });
const snapshot = () => ({ type: 'snapshot', header: { id: scope.sessionId, version: 2, createdAt: 10, isSeeded: false,
  cwd: scope.workspacePath, agentPreset: 'analytics-b0' }, cursor: 1, records: [event()], hasMore: false,
  projections: { asOfSeq: 1, values: { title: 'B0' } } });

for (const method of ['session/modelCatalog', 'agentPresets/list', 'settings/describe',
  'session/canOpenWorkspacePath', 'settings/canOpenAgentPresetDirectory']) {
  test(`metadata exact empty arguments: ${method}`, () => {
    assert.equal(authorizeHttp(method, empty(), scope).allowed, true);
    assert.equal(authorizeHttp(method, { args: { actorId: 'other' } }, scope).allowed, false);
    assert.equal(authorizeHttp(method, { args: {}, extra: true }, scope).allowed, false);
  });
}

test('native session/list accepts only its real _request empty object', () => {
  assert.equal(authorizeHttp('session/list', { args: { _request: {} } }, scope).allowed, true);
  for (const value of [empty(), { args: { _request: { cursor: 'another-scope' } } }, { args: { request: {} } }]) {
    assert.equal(authorizeHttp('session/list', value, scope).allowed, false);
  }
});

test('prompt is same-session text-only queue, bounded and single-flight', () => {
  assert.equal(authorizeHttp('session/prompt', payload(prompt()), scope).allowed, true);
  for (const request of [
    { ...prompt(), sessionId: 'other-session' }, { ...prompt(), mode: 'steer' },
    { ...prompt(), actorId: 'other-actor' }, { ...prompt(), source: { kind: 'system' } },
    { ...prompt(), requestId: '../new' }, { ...prompt(), content: [{ type: 'text', text: 'x'.repeat(8001) }] },
    { ...prompt(), content: [{ type: 'file', receiptId: 'file-1' }] },
    { ...prompt(), content: [{ type: 'image', mediaType: 'image/png', data: 'synthetic' }] },
    { ...prompt(), content: [{ type: 'text', text: '  ' }] },
    { ...prompt(), content: [{ type: 'text', text: 'a' }, { type: 'text', text: 'b' }] },
    { ...prompt(), clientTimeZone: '../etc' },
  ]) assert.equal(authorizeHttp('session/prompt', payload(request), scope).allowed, false);
  assert.equal(authorizeHttp('session/prompt', payload(prompt()), { ...scope, inFlight: true }).allowed, false);
  assert.equal(authorizeHttp('session/prompt', payload(prompt()), { ...scope, inFlight: undefined }).allowed, false);
});

test('page and cancel reject another session, subagents, extras and unbounded pages', () => {
  const page = { address: address(), throughSeq: 10, beforeSeq: 8, maxMessages: 40 };
  assert.equal(authorizeHttp('session/page', payload(page), scope).allowed, true);
  for (const request of [{ ...page, maxMessages: 100000 }, { ...page, beforeSeq: 11 },
    { ...page, address: { kind: 'session', sessionId: 'other' } },
    { ...page, address: { kind: 'subagent', parentSessionId: scope.sessionId, childSessionId: 'child' } },
    { ...page, path: '/private' }]) assert.equal(authorizeHttp('session/page', payload(request), scope).allowed, false);
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: scope.sessionId }), scope).allowed, true);
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: 'other' }), scope).allowed, false);
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: scope.sessionId, keepInbox: false }), scope).allowed, false);
});

for (const method of ['session/create', 'session/selectModel', 'session/fork', 'session/rename', 'session/search',
  'session/attachment', 'session/openWorkspacePath', 'session/updateQueue', 'agentPresets/select', 'agentPresets/copy',
  'agentPresets/read', 'agentPresets/deletePreset', 'workspace/create', 'workspace/delete', 'directoryPicker/list',
  'directoryPicker/pick', 'directoryPicker/createDirectory', 'settings/update', 'settings/mutate', 'settings/replace',
  'settings/openSettingsDocument', 'credentials/describe', 'credentials/set', 'commands/execute', '$events/result',
  'plugins/list', 'session/%70rompt', '/api/session/prompt', 'future/endpoint']) {
  test(`default deny HTTP ${method}`, () => assert.equal(authorizeHttp(method, empty(), scope).allowed, false));
}

test('actor scope is server-owned and fails closed on mismatch', () => {
  const foreign = { ...scope, requestActorId: 'other-actor' };
  assert.equal(authorizeHttp('session/modelCatalog', empty(), foreign).allowed, false);
  assert.equal(authorizeStream(open('$events'), foreign).allowed, false);
  assert.equal(filterHttpResult('session/list', { items: [ownSummary()] }, foreign), null);
  assert.equal(filterStreamItem('$events', { type: 'ready', clientId: 'c' }, foreign), null);
});

test('all RemoteFetch variants are denied', () => {
  for (const path of ['/api/uploadFile', '/api/session/attachment', '/api/unknown']) {
    assert.equal(authorizeFetch(path, {}, scope).allowed, false);
  }
});

test('WS admits only four declared streams and exact payloads', () => {
  for (const endpoint of ['$events', 'session/control', 'workspace/follow']) {
    assert.equal(authorizeStream(open(endpoint), scope).allowed, true);
    assert.equal(authorizeStream(open(endpoint, 's', { args: { sessionId: scope.sessionId } }), scope).allowed, false);
  }
  assert.equal(authorizeStream(open('session/follow', 's', payload({ address: address(), assistantStream: true, maxMessages: 40 })), scope).allowed, true);
  assert.equal(authorizeStream(open('session/follow', 's', payload({ address: { kind: 'session', sessionId: 'other' } })), scope).allowed, false);
  assert.equal(authorizeStream(open('session/follow', 's', payload({ address: address(), cursor: 'any' })), scope).allowed, false);
  assert.equal(authorizeStream(open('settings/follow'), scope).allowed, false);
  assert.equal(authorizeStream({ ...open('$events'), extra: true }, scope).allowed, false);
});

test('WS multiplex ID cannot be reopened across endpoints or after cancellation', () => {
  const opened = { ...scope, seenStreamIds: new Set(['s']), activeStreamIds: new Set(['s']) };
  assert.equal(authorizeStream({ type: 'cancel', streamId: 's' }, opened).allowed, true);
  assert.equal(authorizeStream(open('session/control', 's'), opened).allowed, false);
  const cancelled = { ...opened, activeStreamIds: new Set() };
  assert.equal(authorizeStream(open('$events', 's'), cancelled).allowed, false);
  assert.equal(authorizeStream({ type: 'cancel', streamId: 's' }, cancelled).allowed, false);
  assert.equal(authorizeStream({ type: 'cancel', streamId: 'unknown' }, opened).allowed, false);
  assert.equal(authorizeStream(open('$events', 'new'), opened).allowed, true);
});

test('HTTP session list strips foreign rows and unknown fields', () => {
  const result = filterHttpResult('session/list', { items: [{ ...ownSummary(), secret: 'not-visible' },
    { ...ownSummary(), sessionId: 'other-session' }] }, scope);
  assert.equal(result.items.length, 1);
  assert.equal(JSON.stringify(result).includes('not-visible'), false);
  assert.equal(JSON.stringify(result).includes('other-session'), false);
});

test('preset roster is fixed, read-only and has no source paths', () => {
  const result = filterHttpResult('agentPresets/list', { authorable: true, presets: [
    { id: 'analytics-b0', trust: 'system', isDefault: true, name: 'B0', path: '/private' },
    { id: 'standard', trust: 'system', isDefault: false, description: 'unknown' },
  ] }, scope);
  assert.equal(result.authorable, false);
  assert.equal(result.presets.length, 1);
  assert.equal(JSON.stringify(result).includes('/private'), false);
});

test('settings.describe exports only explicit UI namespaces, no base/user/secrets', () => {
  const result = filterHttpResult('settings/describe', { writable: true, hasDocument: true, namespaces: [
    { ns: 'ui-conversation', schema: {}, value: { busyEnter: 'steer', apiKey: 'hidden' }, base: { key: 'hidden' }, user: { secret: 'hidden' }, revision: 3, secrets: [{ set: true }] },
    { ns: 'llm-deepseek', schema: {}, value: { apiKey: 'hidden' } },
    { ns: 'another-private-namespace', schema: {}, value: {} },
  ] }, scope);
  assert.equal(result.writable, false);
  assert.equal(result.hasDocument, false);
  assert.deepEqual(result.namespaces.map((item) => item.ns), ['ui-conversation']);
  assert.equal(result.namespaces[0].value.busyEnter, 'queue');
  assert.equal(JSON.stringify(result).includes('hidden'), false);
});

test('model metadata keeps only the configured default route, no diagnostics or extra fields', () => {
  const result = filterHttpResult('session/modelCatalog', { default: { provider: 'mock', model: 'synthetic' },
    groups: [{ id: 'mock', name: 'Mock', apiKey: 'hidden', models: [{ id: 'synthetic', name: 'B0', endpoint: 'private' }, { id: 'other', name: 'other' }] },
      { id: 'private-provider', name: 'hidden', models: [] }], failures: [{ message: 'private credentials path' }] }, scope);
  assert.equal(result.groups.length, 1);
  assert.equal(result.groups[0].models.length, 1);
  assert.deepEqual(result.failures, []);
  assert.equal(JSON.stringify(result).includes('private'), false);
});

test('events bootstrap does not reveal HOME or forward waterfall/global events', () => {
  assert.deepEqual(filterStreamItem('$events', { type: 'ready', clientId: 'c', host: { home: '/Users/private', secret: 'hidden' } }, scope),
    { type: 'ready', clientId: 'c', host: { home: '/synthetic' } });
  for (const value of [{ type: 'waterfall', agentId: scope.sessionId, event: 'approval/request' },
    { type: 'cancel', eventId: 'e' }, { type: 'emit', event: 'credentials/reference-updated', args: ['secret'] },
    { type: 'emit', event: 'settings/document-updated', args: [] },
    { type: 'emit', event: 'api-session/status', args: ['other-session', true] },
    { type: 'emit', event: 'api-session/error', args: [scope.sessionId, '/private/secret'] }]) {
    assert.equal(filterStreamItem('$events', value, scope), null);
  }
  assert.deepEqual(filterStreamItem('$events', { type: 'emit', event: 'api-session/status', args: [scope.sessionId, true] }, scope),
    { type: 'emit', event: 'api-session/status', args: [scope.sessionId, true] });
});

test('control baseline and increments cannot leak sibling sessions', () => {
  const result = filterStreamItem('session/control', { type: 'baseline', value: {
    queues: { [scope.sessionId]: [], other: [{ message: 'hidden' }] }, jobs: { other: [{ label: 'hidden' }] },
    projections: { [scope.sessionId]: { asOfSeq: 1, values: { title: 'B0', arbitraryPrivate: { secret: 'hidden' } } }, other: { title: 'hidden' } },
  } }, scope);
  assert.deepEqual(Object.keys(result.value.queues), [scope.sessionId]);
  assert.deepEqual(result.value.jobs, {});
  assert.equal(JSON.stringify(result).includes('hidden'), false);
  assert.equal(filterStreamItem('session/control', { type: 'queue', sessionId: 'other', items: [] }, scope), null);
  assert.equal(filterStreamItem('session/control', { type: 'projection', sessionId: scope.sessionId, key: 'arbitraryPrivate', value: 'hidden', seq: 1 }, scope), null);
});

test('workspace stream filters roots, memberships and archived/order identifiers', () => {
  const baseline = filterStreamItem('workspace/follow', { type: 'baseline', value: {
    items: [ownWorkspace(), { ...ownWorkspace(), workspaceId: 'other', path: '/private' }], archivedSessionIds: ['other-session', scope.sessionId] } }, scope);
  assert.equal(baseline.value.items.length, 1);
  assert.deepEqual(baseline.value.items[0].sessionIds, [scope.sessionId]);
  assert.deepEqual(baseline.value.archivedSessionIds, [scope.sessionId]);
  assert.equal(filterStreamItem('workspace/follow', { type: 'upsert', workspace: { ...ownWorkspace(), path: '/private' } }, scope), null);
  assert.deepEqual(filterStreamItem('workspace/follow', { type: 'order', workspaceIds: ['other', scope.workspaceId] }, scope), { type: 'order', workspaceIds: [scope.workspaceId] });
});

test('follow snapshots reject other session headers; durable/event data remains scoped', () => {
  assert.equal(filterStreamItem('session/follow', snapshot(), scope).header.id, scope.sessionId);
  assert.equal(filterStreamItem('session/follow', { ...snapshot(), header: { ...snapshot().header, id: 'other' } }, scope), null);
  assert.equal(filterStreamItem('session/follow', { ...snapshot(), header: { ...snapshot().header, cwd: '/wrong-workspace' } }, scope), null);
  assert.equal(filterStreamItem('session/follow', { ...snapshot(), header: { ...snapshot().header, agentPreset: 'standard' } }, scope), null);
  for (const data of [{ sessionId: 'other' }, { workspaceId: 'other' }, { actorId: 'other' },
    { nested: { apiKey: 'hidden' } }, { path: '/Users/private' }, { cwd: '/synthetic/workspace-other' }]) {
    assert.equal(filterStreamItem('session/follow', event(data), scope), null);
  }
  assert.equal(filterStreamItem('session/follow', { type: 'new-unknown-frame', data: 'private' }, scope), null);
  assert.equal(filterStreamItem('unknown/stream', snapshot(), scope), null);
});

test('HTTP page drops foreign structured data and does not mutate inputs', () => {
  const input = { records: [event(), event({ sessionId: 'other', text: 'hidden' })], hasMore: false };
  const before = JSON.stringify(input);
  const result = filterHttpResult('session/page', input, scope);
  assert.equal(result.records.length, 1);
  assert.equal(JSON.stringify(input), before);
  assert.equal(filterHttpResult('future/endpoint', input, scope), null);
});

test('malformed/null and prototype-pollution payloads fail closed', () => {
  for (const value of [null, [], 'string', { args: [] }, JSON.parse('{"args":{},"__proto__":{"privileged":true}}')]) {
    assert.equal(authorizeHttp('session/modelCatalog', value, scope).allowed, false);
  }
  assert.equal(filterStreamItem('session/follow', event(JSON.parse('{"__proto__":{"secret":"hidden"}}')), scope), null);
});

const sessionB = 'session-query-synthetic-b';
const two = Object.freeze({ ...scope, sessionIds: [scope.sessionId, sessionB] });
const bSummary = () => ({ ...ownSummary(), sessionId: sessionB });
const bSnapshot = () => ({ ...snapshot(), header: { ...snapshot().header, id: sessionB } });

test('two-session allowlist admits A and B HTTP/stream and rejects a third session', () => {
  assert.equal(sessionAllowed(two, scope.sessionId), true);
  assert.equal(sessionAllowed(two, sessionB), true);
  assert.equal(sessionAllowed(two, 'session-other'), false);
  assert.equal(sessionAllowed(scope, sessionB), false);
  assert.equal(authorizeHttp('session/prompt', payload({ ...prompt(), sessionId: sessionB }), two).allowed, true);
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: sessionB }), two).allowed, true);
  assert.equal(authorizeHttp('session/page', payload({ address: { kind: 'session', sessionId: sessionB }, throughSeq: 2 }), two).allowed, true);
  for (const request of [
    { ...prompt(), sessionId: 'session-other' },
  ]) assert.equal(authorizeHttp('session/prompt', payload(request), two).allowed, false);
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: 'session-other' }), two).allowed, false);
  assert.equal(authorizeHttp('session/page', payload({ address: { kind: 'session', sessionId: 'session-other' }, throughSeq: 2 }), two).allowed, false);
  assert.equal(authorizeStream(open('session/follow', 's', payload({ address: { kind: 'session', sessionId: sessionB }, assistantStream: true })), two).allowed, true);
  assert.equal(authorizeStream(open('session/follow', 's', payload({ address: { kind: 'session', sessionId: 'session-other' } })), two).allowed, false);
  assert.equal(authorizeHttp('session/modelCatalog', empty(), { ...scope, sessionIds: [scope.sessionId] }).allowed, false);
});

test('two-session list and workspace keep A+B and drop a third identity', () => {
  const listed = filterHttpResult('session/list', { items: [ownSummary(), bSummary(), { ...ownSummary(), sessionId: 'session-other' }] }, two);
  assert.deepEqual(listed.items.map((item) => item.sessionId), [scope.sessionId, sessionB]);
  const baseline = filterStreamItem('workspace/follow', { type: 'baseline', value: {
    items: [{ ...ownWorkspace(), sessionIds: [scope.sessionId, sessionB, 'session-other'] }],
    archivedSessionIds: [scope.sessionId, sessionB, 'session-other'],
  } }, two);
  assert.deepEqual(baseline.value.items[0].sessionIds, [scope.sessionId, sessionB]);
  assert.deepEqual(baseline.value.archivedSessionIds, [scope.sessionId, sessionB]);
});

test('A follow stream drops B frames; B follow keeps B and drops A', () => {
  const aBound = { ...two, sessionId: scope.sessionId };
  const bBound = { ...two, sessionId: sessionB };
  assert.equal(filterStreamItem('session/follow', bSnapshot(), aBound), null);
  assert.equal(filterStreamItem('session/follow', snapshot(), bBound), null);
  assert.equal(filterStreamItem('session/follow', bSnapshot(), bBound).header.id, sessionB);
  assert.equal(filterStreamItem('session/follow', snapshot(), aBound).header.id, scope.sessionId);
  assert.equal(filterStreamItem('$events', { type: 'emit', event: 'api-session/status', args: [sessionB, true] }, two).args[0], sessionB);
  assert.equal(filterStreamItem('$events', { type: 'emit', event: 'api-session/status', args: ['session-other', true] }, two), null);
});

test('cancel target is the requested registered session, not a sibling or third', () => {
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: scope.sessionId }), two).allowed, true);
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: sessionB }), two).allowed, true);
  assert.equal(authorizeHttp('session/cancel', payload({ sessionId: 'session-other' }), two).allowed, false);
  const control = filterStreamItem('session/control', { type: 'baseline', value: {
    queues: { [scope.sessionId]: [], [sessionB]: [], other: [{ hidden: true }] },
    jobs: { [sessionB]: [] }, projections: {},
  } }, two);
  assert.deepEqual(Object.keys(control.value.queues).sort(), [scope.sessionId, sessionB].sort());
  assert.equal(JSON.stringify(control).includes('hidden'), false);
});
