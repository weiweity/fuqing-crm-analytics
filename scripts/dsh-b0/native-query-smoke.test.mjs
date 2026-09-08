import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseComposer, canSendNextPrompt } from './native-state-smoke.mjs';
import {
  QUESTIONS, QUERY_CARD_EXPECT, QUERY_SESSION_IDS, SCENARIO,
  bindListedSessions, cardHasForeignDays, cardShowsQuery, parseNewSessionButtonRef,
  parseTreeitemRef, queryMockScript, queryRequest, sessionReadyWithoutForeign, sessionSwitchPlan,
} from './query-scenario.mjs';
import { decodeQueryRequest } from '../../dsh-plugins/analytics-workbench/src/query-model.mjs';

const here = dirname(fileURLToPath(import.meta.url));

test('native-query is two distinct prompts on two registered sessions', () => {
  assert.equal(SCENARIO, 'native-query');
  assert.equal(QUESTIONS.length, 2);
  assert.equal(new Set(QUESTIONS).size, 2);
  assert.deepEqual([...QUERY_SESSION_IDS], ['session-query-synthetic-a', 'session-query-synthetic-b']);
  assert.notEqual(QUERY_SESSION_IDS[0], QUERY_SESSION_IDS[1]);
});

test('finite mock is two query calls plus two wrap-ups with N30 then N60, no slow chunks', () => {
  const script = queryMockScript();
  assert.equal(script.length, 4);
  assert.deepEqual(script.map(step => step.sequence), [['tool_call_success'], ['success'], ['tool_call_success'], ['success']]);
  assert.equal(script[0].toolName, 'analytics_channel_followup_query');
  assert.equal(script[2].toolName, 'analytics_channel_followup_query');
  assert.equal(JSON.parse(script[0].toolArguments).observation_days, 30);
  assert.equal(JSON.parse(script[2].toolArguments).observation_days, 60);
  assert.ok(script.every(step => step.chunkDelayMs === 0));
  assert.ok(!JSON.stringify(script).includes('source_question'));
});

test('query request matches the G4a FIXED window and empty channel_ids', () => {
  for (const days of [30, 60]) {
    const request = queryRequest(days);
    assert.deepEqual(decodeQueryRequest(request), {
      ...request, cohort_window: { ...request.cohort_window }, channel_ids: [], product_ids: [],
    });
    assert.equal(request.cohort_window.start_date, '2026-06-01');
    assert.equal(request.cohort_window.end_date, '2026-09-01');
    assert.equal(request.data_snapshot_ref, 'synthetic-channel-followup-v1');
    assert.deepEqual(request.channel_ids, []);
  }
});

test('composer ready still gates the next send', () => {
  assert.equal(canSendNextPrompt({ backendTerminal: true, nativeSettled: true, composerReady: false }), false);
  const ready = '@e58 [textbox] "Message or run a task... / commands, @ files or sessions"\n@e70 [button] "Send message"\n';
  assert.equal(parseComposer(ready).sendEnabled, true);
});

test('session switch plan uses unique other blank or visible title, never raw session ids', () => {
  const allowed = [...QUERY_SESSION_IDS];
  const a = { sessionId: allowed[0], blank: false, projections: { values: { title: '30日合成查询' } } };
  const b = { sessionId: allowed[1], blank: true, projections: { values: { title: '' } } };
  const listed = bindListedSessions([a, b], allowed);
  assert.deepEqual(listed.map(row => row.sessionId), allowed);
  assert.equal(sessionSwitchPlan(listed, allowed[0], allowed[0]).action, 'noop');
  assert.equal(sessionSwitchPlan(listed, allowed[0], allowed[1]).action, 'new-session-button');
  assert.equal(sessionSwitchPlan(listed, allowed[0], 'session-other').action, 'reject');
  const titled = bindListedSessions([a, { ...b, blank: false, projections: { values: { title: '60日合成查询' } } }], allowed);
  assert.equal(sessionSwitchPlan(titled, allowed[0], allowed[1]).action, 'treeitem');
  assert.equal(sessionSwitchPlan(titled, allowed[0], allowed[1]).title, '60日合成查询');
  const idAsTitle = bindListedSessions([a, { ...b, blank: false, projections: { values: { title: allowed[1] } } }], allowed);
  assert.equal(sessionSwitchPlan(idAsTitle, allowed[0], allowed[1]).action, 'reject');
  const twoBlanks = bindListedSessions([
    { sessionId: allowed[0], blank: true, projections: { values: { title: '' } } },
    { sessionId: allowed[1], blank: true, projections: { values: { title: '' } } },
  ], allowed);
  assert.equal(sessionSwitchPlan(twoBlanks, allowed[0], allowed[1]).action, 'new-session-button');
  assert.equal(bindListedSessions([a, b, { sessionId: 'session-other', blank: true }], allowed), null);
});

test('snapshot parsers match New session / treeitem titles and ignore raw session ids', () => {
  const snapshot = '@e10 [treeitem] "30日合成查询"\n@e11 [button] "New session"\n@e12 [button] "session-query-synthetic-b"\n';
  assert.equal(parseNewSessionButtonRef(snapshot), '@e11');
  assert.equal(parseTreeitemRef(snapshot, '30日合成查询'), '@e10');
  assert.equal(parseTreeitemRef(snapshot, 'session-query-synthetic-b'), null);
  assert.equal(parseNewSessionButtonRef('@e3 [button] "在B0 Synthetic中新建会话"\n'), '@e3');
  assert.equal(parseNewSessionButtonRef('@e4 [button] "新会话"\n'), '@e4');
});

test('visible card wait requires exact session and rejects the other N', () => {
  const uiA = { session: QUERY_SESSION_IDS[0], days: ['30'],
    cards: [`N=30 二单 ${QUERY_CARD_EXPECT[30].repeat} 净支付 ${QUERY_CARD_EXPECT[30].yuan}`] };
  const uiB = { session: QUERY_SESSION_IDS[1], days: ['60'],
    cards: [`N=60 二单 ${QUERY_CARD_EXPECT[60].repeat} 净支付 ${QUERY_CARD_EXPECT[60].yuan}`] };
  const emptyB = { session: QUERY_SESSION_IDS[1], days: [], cards: [] };
  assert.equal(cardShowsQuery(uiA, QUERY_CARD_EXPECT[30]), true);
  assert.equal(sessionReadyWithoutForeign(emptyB, QUERY_SESSION_IDS[1], 30), true);
  assert.equal(sessionReadyWithoutForeign({ session: QUERY_SESSION_IDS[1], days: ['30'], cards: ['N=30'] }, QUERY_SESSION_IDS[1], 30), false);
  assert.equal(cardHasForeignDays(uiB, 30), false);
  assert.equal(sessionReadyWithoutForeign(uiA, QUERY_SESSION_IDS[1], 30) || cardHasForeignDays(uiA, 30) === false && uiA.session === QUERY_SESSION_IDS[1], false);
});

test('serve opt-in keeps production kernel for native-query and does not enable the probe', async () => {
  const serve = await readFile(join(here, 'serve.mjs'), 'utf8');
  assert.match(serve, /\[--native-cards\|--native-state\|--native-query\|--native-query-fault\|--native-query-assets\]/);
  assert.match(serve, /queryScenario/);
  assert.match(serve, /B0_RUNTIME_FAMILY: 'channel_followup'/);
  assert.match(serve, /queryFaultScenario \? 'backend\.tests\.analytics_query_native_fault_probe' : stateScenario \? 'backend\.tests\.analytics_native_probe' : 'backend\.analytics_runtime'/);
  assert.equal((serve.match(/backend\.analytics_runtime/g) || []).length, 1);
  assert.doesNotMatch(serve, /queryScenario \? 'backend\.tests/);
  assert.doesNotMatch(serve, /queryScenario \? \{ script: queryFaultMockScript/);
});
