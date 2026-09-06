/** Native UI verification via the user's explicitly supplied browse binary.
 * Own fresh B0 runtime only. No direct prompt/cancel RPC, new browser engine,
 * provider credentials, automatic retry, real data, or user-owned tab cleanup.
 */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';
import { join, resolve, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const [namedRuntime, browse, tab, resumeFlag, ...extra] = process.argv.slice(2);
assert.ok(namedRuntime && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length
  && (resumeFlag === undefined || resumeFlag === '--resume-verified-two'),
  'Usage: node native-ui-smoke.mjs <current-runtime> /absolute/browse <owned-tab-id> [--resume-verified-two]');
const runtime = resolve(namedRuntime);
const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
assert.equal(current.runtime, runtime);
assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 4 * 1024 * 1024 });
const rows = () => db.prepare('SELECT run_id, attempt_id, status, tool_steps_used FROM runs ORDER BY rowid').all();
const report = { kind: 'B0_NATIVE_UI_KERNEL', started_at: new Date().toISOString(), runtime: namedRuntime, tab: Number(tab), actions: [] };
report.plugin_hashes = Object.fromEntries(await Promise.all(['index.js', 'tool.js', 'skills.js', 'client.js']
  .map(async name => [name, createHash('sha256').update(await readFile(join(current.plugin, 'lib', name))).digest('hex')])));
const evidence = mode => JSON.parse(execFileSync(process.execPath,
  [join(root, 'scripts/dsh-b0/kernel-native-evidence.mjs'), mode, runtime], { cwd: root, encoding: 'utf8', timeout: 55000 }));
async function waitUntil(check) {
  const deadline = Date.now() + 7000;
  while (Date.now() < deadline) { if (check()) return; await delay(100); }
  throw new Error('Native UI/ledger verification deadline expired');
}
function ref(snapshot, pattern) { const match = snapshot.match(pattern); assert.ok(match, 'Expected native accessible control missing'); return match[1]; }
function send(text) {
  const snapshot = b('snapshot', '-i');
  const input = ref(snapshot, /(@e\d+) \[textbox\] "(?:Describe what you want to build|Message or run a task)\.\.\. \/ commands, @ files or sessions"/);
  const button = ref(snapshot, /(@e\d+) \[button\] "Send message"/);
  b('fill', input, text);
  b('click', button);
  report.actions.push({ type: 'native-send', text });
}
try {
  if (resumeFlag) assert.deepEqual(rows().map(row => row.status), ['SUCCEEDED', 'SUCCEEDED']);
  else assert.equal(rows().length, 0, 'UI smoke refuses to duplicate an existing question');
  b('tab', tab);
  assert.equal(b('url').trim(), 'http://127.0.0.1:4318/');
  const questions = [
    'B0 第一问：请展示固定合成渠道复购样例。',
    'B0 第二问：再查询一次固定合成渠道，验证连续发送。',
    'B0 第三问：慢速生成，用于恢复后取消验证。',
    'B0 第四问：停止后再次查询固定合成渠道。',
    'B0 第五问：固定服务端错误样例，验证失败不会伪装完成。',
    'B0 第六问：慢速生成，用于原生宿主崩溃恢复验证。',
    'B0 第七问：宿主恢复后再次查询固定合成渠道。',
  ];
  if (resumeFlag) {
    const accepted = db.prepare('SELECT payload_json FROM dispatch_intents ORDER BY rowid').all();
    assert.deepEqual(accepted.map(row => JSON.parse(row.payload_json).native_request.content[0].text), questions.slice(0, 2));
    report.resumed_after = evidence('--two-questions');
    report.actions.push({ type: 'resume-verified-first-two', existing_runs: 2, prompts_resent: 0 });
  }
  for (let index = resumeFlag ? 2 : 0; index < questions.length; index++) {
    send(questions[index]);
    if (index === 2) {
      await waitUntil(() => rows()[2]?.status === 'RUNNING');
      report.restart = evidence('--restart-active');
      const before = b('snapshot', '-i');
      const stop = ref(before, /(@e\d+) \[button\] "Stop generating"/);
      b('click', stop);
      report.actions.push({ type: 'native-stop', observed_ref: stop, before });
    }
    if (index === 5) {
      await waitUntil(() => rows()[5]?.status === 'RUNNING');
      report.host_restart = evidence('--restart-host');
      b('reload');
      await waitUntil(() => b('snapshot').includes(questions[5]));
    }
    const expected = ['SUCCEEDED', 'SUCCEEDED', 'CANCELLED', 'SUCCEEDED', 'FAILED', 'FAILED', 'SUCCEEDED'][index];
    await waitUntil(() => rows()[index]?.status === expected);
    if (index === 1) report.two_questions = evidence('--two-questions');
  }
  report.final = evidence('--extended-final');
  const before = rows();
  b('reload');
  await waitUntil(() => {
    const snapshot = b('snapshot');
    // The composer shows only the latest three ledger rows. Turn 3 is now
    // outside that window; verify its durable native history, not a vanished
    // Chinese label from the recent-runs projection. Keep the native failure
    // marker distinct from the word "failure" inside a submitted question.
    return questions.every(text => snapshot.includes(text))
      && snapshot.includes('[text]: Stopped') && snapshot.includes('This turn failed')
      && snapshot.includes('B0 任务内核状态') && snapshot.includes('失败 · 已核对退出');
  });
  assert.deepEqual(rows(), before);
  report.after_refresh = b('snapshot');
  report.refresh = { native_history_restored: true, new_runs: 0, original_ids_and_results_preserved: true };
  const consoleRows = b('console').split('\n').filter(line => /^\[\d{4}-/.test(line)
    && line.slice(1, 25) >= report.started_at).map(line => line.replace(/http[^\s]+/g, '[local URL]').slice(0, 500));
  assert.ok(!consoleRows.some(line => /event feed subscriber failed|TypeError|Uncaught/.test(line)), 'Native UI replay error');
  report.console = consoleRows;
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  report.error = String(error.message).replace(/([?&](?:token|b0)=)[A-Za-z0-9_-]+/g, '$1[REDACTED]').slice(0, 1000);
  process.exitCode = 1;
} finally {
  db.close();
  report.completed_at = new Date().toISOString();
  const path = join(runtime, `native-ui-${Date.now()}.json`);
  await writeFile(path, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ status: report.status, error: report.error, refresh: report.refresh,
    runs: report.final?.runs, report_path: path }));
}
