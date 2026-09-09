import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  QUESTIONS, SCENARIO, RUNNING_TOOL_CARD, runningCannotBeInferredFromSuccess, assertReleaseTarget,
  writeOwnedRelease, redactHold, hasRunningToolCard, verifyExistingScope, abortOwnedHold,
  parseComposer, canSendNextPrompt, nativeRequestSettled, nativeTurnHasDurableResult, waitUntil,
} from './native-state-smoke.mjs';
import { summarizeRequest } from '../../dsh-plugins/analytics-workbench/src/native-evidence.mjs';

const here = dirname(fileURLToPath(import.meta.url));

test('native-state questions are four distinct prompts and do not infer running from success', () => {
  assert.equal(SCENARIO, 'native-state');
  assert.equal(QUESTIONS.length, 4);
  assert.equal(new Set(QUESTIONS).size, 4);
  assert.ok(QUESTIONS.every(text => text.startsWith('B0 状态')));
  assert.equal(runningCannotBeInferredFromSuccess({ status: 'SUCCEEDED' }), false);
  assert.equal(runningCannotBeInferredFromSuccess({ status: 'RUNNING' }), null);
  assert.equal(redactHold({ execution_id: 'exec_' + 'ab'.repeat(16), release_nonce: 'secret-nonce-value' }).release_nonce, undefined);
  assert.equal(redactHold({ execution_id: 'exec_' + 'ab'.repeat(16), release_nonce: 'secret-nonce-value' }).release_nonce_present, true);
});

test('release path is bound to the current execution id and rejects traversal', async () => {
  const probe = await mkdtemp(join(tmpdir(), 'b0-native-state-'));
  await mkdir(join(probe, 'release'), { mode: 0o700 });
  const executionId = 'exec_' + 'ab'.repeat(16);
  assert.equal(assertReleaseTarget(probe, executionId), join(probe, 'release', executionId));
  await writeOwnedRelease(probe, executionId, 'nonce-value-for-owned-release');
  assert.equal(await readFile(join(probe, 'release', executionId), 'utf8'), 'nonce-value-for-owned-release');
  assert.throws(() => assertReleaseTarget(probe, '../etc/passwd'));
  assert.throws(() => assertReleaseTarget(probe, 'exec_not-hex'));
  assert.throws(() => assertReleaseTarget(probe, 'exec_' + 'ab'.repeat(16) + '/../x'));
});

test('running proof requires the actual tool card text, not a generic task RUNNING status', () => {
  assert.equal(RUNNING_TOOL_CARD, 'B0 合成工具运行中');
  assert.equal(hasRunningToolCard(['B0 合成工具运行中…']), true);
  assert.equal(hasRunningToolCard(['运行中', 'RUNNING']), false);
  assert.equal(hasRunningToolCard([]), false);
  const existing = verifyExistingScope();
  assert.equal(existing.running_live_observed, false);
  assert.equal(existing.live_running_pass, false);
  assert.equal(existing.limited_scope, true);
  assert.equal(existing.scope, 'durable-only');
});

test('error path releases the current hold without sending another prompt', async () => {
  const probe = await mkdtemp(join(tmpdir(), 'b0-native-state-abort-'));
  await mkdir(join(probe, 'release'), { mode: 0o700 });
  const executionId = 'exec_' + 'cd'.repeat(16);
  const nonce = 'nonce-value-for-owned-release';
  await writeFile(join(probe, 'current.json'), JSON.stringify({ execution_id: executionId, release_nonce: nonce }) + '\n', { mode: 0o600 });
  const abort = await abortOwnedHold(probe, { waitMs: 200 });
  assert.equal(abort.released, true);
  assert.equal(abort.prompts_resent, 0);
  assert.equal(abort.execution_id, executionId);
  assert.equal(await readFile(join(probe, 'release', executionId), 'utf8'), nonce);
  const again = await abortOwnedHold(probe, { waitMs: 200 });
  assert.equal(again.prompts_resent, 0);
  assert.ok(again.released === false);
});

test('next prompt requires native turn settlement and composer, not backend terminal alone', () => {
  assert.equal(canSendNextPrompt({ backendTerminal: true, nativeSettled: false, composerReady: true }), false);
  assert.equal(canSendNextPrompt({ backendTerminal: true, nativeSettled: true, composerReady: false }), false);
  assert.equal(canSendNextPrompt({ backendTerminal: false, nativeSettled: true, composerReady: true }), true);
  const generating = '@e58 [textbox] "Message or run a task... / commands, @ files or sessions"\n@e66 [button] "Stop generating"\n';
  assert.equal(parseComposer(generating).readyToFill, false);
  const empty = '@e58 [textbox] "Message or run a task... / commands, @ files or sessions"\n@e70 [button] "Send message" [disabled]\n';
  const idle = parseComposer(empty);
  assert.equal(idle.readyToFill, true);
  assert.equal(idle.sendEnabled, false);
  const ready = '@e58 [textbox] "Message or run a task... / commands, @ files or sessions"\n@e70 [button] "Send message"\n';
  assert.equal(parseComposer(ready).sendEnabled, true);
});

test('summarizer turn-end plus durable tool result gates the scheduler, not a fixed sleep', async () => {
  const requestId = 'req-1';
  const events = [
    { type: 'turn/start', data: { turn: 1 } },
    { type: 'user/message', data: { source: { kind: 'user', rpcId: requestId } } },
    { type: 'tool/call', data: { callId: 'c1', turn: 1 } },
  ];
  assert.equal(nativeRequestSettled(summarizeRequest(events, requestId)), false);
  assert.equal(nativeTurnHasDurableResult(events, requestId), false);
  events.push({ type: 'tool/result', data: { turn: 1, message: { content: [{ type: 'tool-result', toolCallId: 'c1', isError: true }] } } });
  assert.equal(nativeRequestSettled(summarizeRequest(events, requestId)), false);
  events.push({ type: 'turn/end', data: { turn: 1, reason: { kind: 'error' } } });
  const summary = summarizeRequest(events, requestId);
  assert.equal(nativeRequestSettled(summary), true);
  assert.equal(summary.targetTurn, 1);
  assert.equal(nativeTurnHasDurableResult(events, requestId), true);
  let phase = 0;
  let t = 0;
  const clock = { now: () => t, sleep: async (ms) => { t += ms; phase += 1; } };
  const ok = await waitUntil(() => canSendNextPrompt({
    backendTerminal: true,
    nativeSettled: phase >= 1,
    composerReady: phase >= 2,
  }), { budgetMs: 500, tickMs: 100, clock });
  assert.equal(ok, true);
  assert.ok(phase >= 2);
  const starved = await waitUntil(() => false, { budgetMs: 30, tickMs: 10, clock: { now: () => t, sleep: async (ms) => { t += ms; } } });
  assert.equal(starved, false);
});

test('serve opt-in keeps production kernel default and uses the test-only module only for native-state', async () => {
  const serve = await readFile(join(here, 'serve.mjs'), 'utf8');
  assert.match(serve, /\[--native-cards\|--native-state\|--native-query\|--native-query-fault\|--native-query-assets\|--native-first-purchase\]/);
  assert.match(serve, /queryFaultScenario \? 'backend\.tests\.analytics_query_native_fault_probe' : stateScenario \? 'backend\.tests\.analytics_native_probe' : 'backend\.analytics_runtime'/);
  assert.match(serve, /verificationScenario: scenario/);
  assert.equal((serve.match(/backend\.analytics_runtime/g) || []).length, 1);
  assert.doesNotMatch(serve, /fault_mode|inject_fault|\/internal\/native\/probe/);
  assert.match(serve, /sql_hold/);
  assert.match(serve, /unknown_schema/);
});
