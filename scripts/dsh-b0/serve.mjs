/** B0 only: pinned CLI + isolated synthetic profile + official local mock.
 * This is a verification runner, NOT the approved business access gateway.
 * No real data, model credentials, user config, or existing demo processes.
 */
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, writeFile, realpath, access } from 'node:fs/promises';
import { resolve, join, dirname, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createServer } from 'node:net';
import { randomBytes } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { findReadyUrl, redactLaunchLog } from './transport-safety.mjs';
import { runtimeCodeRoot } from './runtime-paths.mjs';
import { startB0MockProvider } from './mock-provider.mjs';
import { observeLifecycle } from './lifecycle-observer.mjs';
import { createDiagnosticSink } from './diagnostic-sink.mjs';
import { packSkills } from '../../dsh-plugins/analytics-workbench/pack-skills.mjs';
import { packageDigest } from '../../dsh-plugins/analytics-workbench/src/skill-package.mjs';
import { QUERY_SESSION_IDS, queryMockScript } from './query-scenario.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const b0 = join(root, '.context/dsh-b0');
const upstream = join(b0, 'upstream');
const args = process.argv.slice(2);
let scenario = 'lifecycle';
if (args.at(-1) === '--native-cards' || args.at(-1) === '--native-state' || args.at(-1) === '--native-query') {
  scenario = args.pop().slice(2);
}
const cardScenario = scenario === 'native-cards';
const stateScenario = scenario === 'native-state';
const queryScenario = scenario === 'native-query';
const [pythonFlag, python, pluginFlag, pluginArg, ...extra] = args;
assert.ok(pythonFlag === '--python' && python && isAbsolute(python) && !extra.length
  && (pluginFlag === undefined || (pluginFlag === '--plugin' && pluginArg && isAbsolute(pluginArg))),
'Usage: node serve.mjs --python /absolute/python3.14 [--plugin /absolute/clean-plugin] [--native-cards|--native-state|--native-query]');
assert.equal(process.platform, 'darwin', 'The native verification runner requires the macOS Seatbelt profile');
assert.equal(Number(process.versions.node.split('.')[0]), 24, 'Use Node 24');
const plugin = await realpath(pluginArg ?? join(root, 'dsh-plugins/analytics-workbench'));
const pinned = 'd347e703908d0406b7a7ef80e3a0e594d86b2215';
const webPort = 4317;
const mockPort = 4319;
const binary = process.execPath;
const cli = join(upstream, 'apps/cli/lib/bin.js');
const profilePath = join(root, 'scripts/dsh-b0/sandbox.sb');

async function assertFree(port) {
  const server = createServer();
  await new Promise((ok, fail) => {
    server.once('error', fail);
    server.listen(port, '127.0.0.1', ok);
  });
  await new Promise((ok, fail) => server.close(e => e ? fail(e) : ok()));
}

assert.equal(execFileSync('git', ['-C', upstream, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(), pinned);
for (const file of [cli, profilePath, python, join(plugin, 'lib/index.js'), join(plugin, 'lib/tool.js')]) await access(file);
const { methodPackageDigest, queryMethodPackageDigest } = await import(pathToFileURL(join(plugin, 'lib/skills.js')).href);
assert.equal(methodPackageDigest, packageDigest((await packSkills(plugin)).manifest), 'Built Skill package differs from the reviewed source closure');
if (queryScenario) {
  assert.equal(queryMethodPackageDigest, packageDigest((await packSkills(plugin, 'channel_followup')).manifest, 'channel_followup'),
    'Built query Skill package differs from the reviewed source closure');
}
await Promise.all([4315, 4316, 4318, webPort, mockPort].map(assertFree));
await mkdir(b0, { recursive: true, mode: 0o700 });
const runtime = await mkdtemp(join(b0, 'runtime-'));
const lifecycle = observeLifecycle(runtime);
const diagnostics = createDiagnosticSink(process.stderr,
  () => lifecycle.record('diagnostic-pipe-closed', { errorCode: 'EPIPE' }));
const ownHome = join(runtime, 'harness');
const workspace = join(runtime, 'synthetic-workspace');
const presets = join(runtime, 'presets');
const kernelState = join(runtime, 'kernel');
const fixtureDirectory = join(runtime, 'fixture');
const runtimeToken = randomBytes(32).toString('base64url');
const gatewayToken = randomBytes(32).toString('base64url');
const sessionIds = queryScenario ? [...QUERY_SESSION_IDS] : ['session-b0-synthetic-primary'];
const sessionId = sessionIds[0];
for (const path of [kernelState, fixtureDirectory, ownHome, workspace, join(presets, 'analytics-b0'), join(runtime, 'tmp'), join(ownHome, 'agents'), join(runtime, 'skills'), join(ownHome, 'profiles/web')]) {
  await mkdir(path, { recursive: true, mode: 0o700 });
}
const writeJson = (path, value) => writeFile(path, JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
const fixture = JSON.parse(execFileSync(python, queryScenario
  ? [join(root, 'scripts/dsh-b0/setup-query-fixture.py'), fixtureDirectory]
  : ['-m', 'backend.analytics_fixture', '--create', fixtureDirectory], {
  cwd: root, encoding: 'utf8', timeout: 30000, env: {
    PATH: `${dirname(python)}:/usr/bin:/bin`, PYTHONPATH: root, PYTHONNOUSERSITE: '1',
    PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1',
  },
}));
const kernelConfig = queryScenario
  ? { state_dir: kernelState, family: 'channel_followup', session_id: sessionId, session_ids: sessionIds,
    runtime_token: runtimeToken, gateway_token: gatewayToken, fixture,
    method_package_digest: queryMethodPackageDigest }
  : { state_dir: kernelState, session_id: sessionId, runtime_token: runtimeToken,
    gateway_token: gatewayToken, fixture, method_package_digest: methodPackageDigest };
await writeJson(join(runtime, 'kernel-private.json'), kernelConfig);
if (stateScenario) {
  const probe = join(runtime, 'probe');
  await mkdir(probe, { recursive: true, mode: 0o700 });
  await mkdir(join(probe, 'release'), { recursive: true, mode: 0o700 });
  await writeFile(join(probe, 'sequence.json'),
    JSON.stringify(['sql_hold', 'unknown_schema', 'illegal_facts', 'passthrough']) + '\n', { mode: 0o600 });
}
await writeJson(join(ownHome, 'profiles/web/package.json'), {
  name: 'shine-mage-b0-web-profile', private: true, type: 'module',
  dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app'], patchReload: 'startup' } },
});
await writeJson(join(presets, 'analytics-b0/agent.cordis.yml'), [
  { id: 'persona', name: '@deepseek-ai/dsh-persona', config: {
    text: queryScenario
      ? '你是仅用于合成渠道后续购买验证的经营分析助手。所有数据都是合成的，只能使用已登记查询工具；不得把合成输出称为真实经营结论。'
      : '你是仅用于B0验证的经营分析助手。所有数据都是合成的，只能使用已登记分析工具；不得把合成输出称为真实经营结论。',
    complete: true, includeRuntimeContext: false,
  } },
  { id: 'analytics-b0-tool', name: pathToFileURL(join(plugin, 'lib/tool.js')).href },
  { id: 'analytics-b0-skill-roots', name: '@deepseek-ai/dsh-skill-filesystem',
    config: { includeDefaultRoots: false, customSkillDirs: [], watch: false, watchFollowSymlinks: false } },
  { id: 'analytics-b0-native-skill', name: '@deepseek-ai/dsh-tool-skill' },
  { id: 'analytics-b0-skills', name: pathToFileURL(join(plugin, 'lib/skills.js')).href },
  { id: 'analytics-b0-compaction', name: 'cordis:group', group: true, isolate: { compaction: true }, config: [
    { id: 'analytics-b0-compaction-basic', name: '@deepseek-ai/dsh-compaction-basic', config: {
      thresholdRatio: 0.8, retainTokens: 2048, maxTokens: 1024, compactionRetries: 0, maxOverflowRetries: 0,
    } },
  ] },
]);
const disabled = ['session-title-llm', 'llm-pi-ai', 'web-search-deepseek', 'web-fetch-http',
  'session-telemetry-otel', 'session-log-deepseek', 'plugin-package-inventory-deepseek',
  'agent-instructions', 'skill-filesystem', 'client-hmr', 'directory-picker'];
const patch = [
  ...disabled.map(id => ({ id, disabled: true })),
  { id: 'agent-presets', config: { default: 'analytics-b0', includeShippedRoot: false,
    includeUserRoot: false, roots: [{ path: presets, trust: 'system' }] } },
  { id: 'session-controller', config: { nativeOpen: false } },
  { id: 'llm-deepseek', config: { apiKeyEnv: 'B0_MOCK_KEY', baseURL: `http://127.0.0.1:${mockPort}/v1`,
    thinking: 'disabled', reasoningEffort: 'off', maxTokens: 1024, streamIdleTimeoutMs: 5000,
    retryPolicy: { mode: 'normal', maxRetries: 0 } } },
  { insert: [{ id: 'analytics-b0-ui', name: pathToFileURL(join(plugin, 'lib/index.js')).href }] },
];
const overlay = join(runtime, 'b0.patch.yml');
await writeJson(overlay, patch);
// Keep the existing HOME value unchanged solely for os.homedir(). Never
// repurpose it as a task directory. Seatbelt denies its private data; DSH_HOME
// and explicit preset roots own all app state. Drop other ambient config/key vars.
const environment = {
  ...Object.fromEntries(Object.entries(process.env).filter(([key]) => key === 'HOME')),
  PATH: `${dirname(binary)}:/usr/bin:/bin`,
  LANG: 'en_US.UTF-8', TZ: 'Asia/Shanghai', OPENSSL_CONF: '/dev/null',
  DSH_HOME: ownHome, DSH_AGENTS_HOME: join(ownHome, 'agents'),
  DSH_BUNDLED_SKILL_DIR: join(runtime, 'skills'), DSH_TELEMETRY_DISABLED: '1',
  TMPDIR: join(runtime, 'tmp'), B0_MOCK_KEY: 'b0-mock-only',
  B0_RUNTIME_TOKEN: runtimeToken, B0_SESSION_ID: sessionId,
  ...(queryScenario ? { B0_RUNTIME_FAMILY: 'channel_followup', B0_SESSION_IDS: sessionIds.join(',') } : {}),
};
const { startMockLlmServer } = await import(pathToFileURL(join(upstream, 'packages/test-support/llm-mock-server/lib/index.js')).href);
const mock = await startB0MockProvider(startMockLlmServer, { host: '127.0.0.1', port: mockPort, apiKey: 'b0-mock-only',
  // Opt-in finite wire script. Native-cards: success, real worker fault (no next
  // model step), Skill, recovered query. Native-state: SQL-hold success, two
  // parent-protocol rejections, recovered query. No journal outcome is fabricated.
  ...(cardScenario ? { script: [
    { sequence: ['tool_call_success'] }, { sequence: ['success'] },
    { sequence: ['tool_call_success'] },
    { sequence: ['tool_call_success'], toolName: 'skill', toolArguments: JSON.stringify({ name: 'growth-analysis-b0' }) },
    { sequence: ['tool_call_success'] }, { sequence: ['success'] },
    { sequence: ['tool_call_success'] }, { sequence: ['success'] },
  ] } : stateScenario ? { script: [
    { sequence: ['tool_call_success'] }, { sequence: ['success'] },
    { sequence: ['tool_call_success'] },
    { sequence: ['tool_call_success'] },
    { sequence: ['tool_call_success'] }, { sequence: ['success'] },
  ] } : queryScenario ? { script: queryMockScript() } : {}),
  sequence: ['tool_call_success', 'success', 'tool_call_success', 'success', 'slow_success', 'tool_call_success', 'success', 'server_error',
    'slow_success', 'tool_call_success', 'success'],
  toolName: queryScenario ? 'analytics_channel_followup_query' : 'analytics_b0_query',
  toolArguments: queryScenario ? queryMockScript()[0].toolArguments : JSON.stringify({ query: 'channel_repeat_rate' }),
  successText: queryScenario ? '合成查询完成：数字来自真实 worker SQL，不是模型编造。' : 'B0合成验证：这个结论不代表真实业务表现。',
  chunkSize: 1, chunkDelayMs: queryScenario ? 0 : 1200,
});
lifecycle.record('mock-ready');

// Parameter names are shared with the separately regression-tested profile.
const sandboxArgs = [
  '-D', `NODE_BINARY=${await realpath(binary)}`,
  '-D', `RUNTIME_CELLAR=${runtimeCodeRoot(binary)}`,
  '-D', `READ_SOURCE=${upstream}`, '-D', `READ_PLUGIN=${plugin}`, '-D', `READ_CONFIG=${runtime}`,
  '-D', `STATE_HOME=${ownHome}`, '-D', `WORKSPACE=${workspace}`, '-D', `TEMP_DIR=${join(runtime, 'tmp')}`,
  '-D', 'BIND_ENDPOINT=localhost:4317', '-D', 'MOCK_ENDPOINT=localhost:4319',
  '-D', 'BRIDGE_ENDPOINT=localhost:4316', '-D', 'KERNEL_ENDPOINT=localhost:4315',
  '-f', profilePath,
];
let child;
let kernel;
let kernelExit;
let kernelGeneration = 0;
let restarting;
let hostGeneration = 0;
let hostReadyGeneration = 0;
let restartingHost;
let stopping = false;
let launchUrl;
let completeLog = '';
let childExit;
const currentPath = join(b0, 'current.json');
function startKernel() {
  kernelGeneration++;
  const generation = kernelGeneration;
  kernel = spawn(python, ['-m', stateScenario ? 'backend.tests.analytics_native_probe' : 'backend.analytics_runtime'], { cwd: root, env: {
    PATH: `${dirname(python)}:/usr/bin:/bin`, PYTHONPATH: root, PYTHONNOUSERSITE: '1',
    PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1',
  }, stdio: ['pipe', 'ignore', 'pipe'] });
  const owned = kernel;
  lifecycle.record('kernel-start', { childPid: owned.pid, generation });
  owned.once('exit', (exitCode, signal) => lifecycle.record('kernel-exit', { childPid: owned.pid, generation, exitCode, signal }));
  kernel.stdin.end(JSON.stringify(kernelConfig) + '\n');
  kernel.stderr.on('data', chunk => { diagnostics.write(String(chunk).replaceAll(runtimeToken, '[REDACTED]').replaceAll(gatewayToken, '[REDACTED]')); });
  kernelExit = new Promise(ok => { kernel.once('exit', ok); kernel.once('error', ok); });
}
async function writeCurrent() {
  await writeJson(currentPath, { runtime, supervisorPid: process.pid, childPid: child?.pid,
    kernelPid: kernel?.pid, kernelGeneration, hostGeneration, hostReadyGeneration, webPort, mockPort, pinned, plugin,
    verificationScenario: scenario });
}
async function bootHost() {
  hostGeneration++;
  launchUrl = undefined;
  completeLog = '';
  child = spawn('/usr/bin/sandbox-exec', [...sandboxArgs, binary, cli, '--profile', 'web', '--patch', overlay,
    '--host', '127.0.0.1', '--port', String(webPort), '--no-open'], { cwd: workspace, env: environment, stdio: ['ignore', 'pipe', 'pipe'] });
  const owned = child;
  const generation = hostGeneration;
  lifecycle.record('host-start', { childPid: owned.pid, generation });
  owned.once('close', (exitCode, signal) => lifecycle.record('host-close', { childPid: owned.pid, generation, exitCode, signal }));
  // close also drains the old log pipes before a new generation starts.
  childExit = new Promise(ok => { owned.once('close', (code, signal) => ok({ code, signal })); owned.once('error', ok); });
  const ingest = chunk => {
    const clean = String(chunk).replace(/\u001b\[[0-9;]*m/g, '');
    completeLog += clean;
    if (completeLog.length > 2 * 1024 * 1024) { owned.kill('SIGTERM'); return; }
    launchUrl = findReadyUrl(completeLog, `http://127.0.0.1:${webPort}`);
    // Persist only complete redacted logs; launch tokens can cross chunks.
  };
  owned.stdout.on('data', ingest); owned.stderr.on('data', ingest);
  await writeCurrent();
  const deadline = Date.now() + 45000;
  while (!launchUrl && owned.exitCode === null && owned.signalCode === null && Date.now() < deadline) await delay(100);
  await writeFile(join(runtime, `boot-generation-${hostGeneration}.log`), redactLaunchLog(completeLog), { mode: 0o600 });
  assert.ok(launchUrl, 'DSH startup did not produce a ready URL within 45s');
  await writeFile(join(runtime, 'boot.log'), redactLaunchLog(completeLog), { mode: 0o600 });
  await writeJson(join(runtime, 'browser-private.json'), { launchUrl });
  hostReadyGeneration = hostGeneration;
  await writeCurrent();
  lifecycle.record('host-ready', { childPid: owned.pid, generation });
}
async function restartKernel() {
  if (stopping || restarting) return;
  restarting = (async () => {
    // Explicit fault-injection control for this owned synthetic child only.
    kernel.kill('SIGKILL');
    await kernelExit;
    if (stopping) return;
    startKernel();
    await writeCurrent();
    console.log(`B0_KERNEL_RESTARTED generation=${kernelGeneration}; original ledger and DSH remain`);
  })();
  try { await restarting; } finally { restarting = undefined; }
}
async function restartHost() {
  if (stopping || restartingHost) return;
  restartingHost = (async () => {
    const prior = { pid: child.pid, generation: hostGeneration };
    child.kill('SIGKILL');
    const exited = await childExit;
    if (stopping) return;
    await bootHost();
    await writeJson(join(runtime, `host-restart-${hostGeneration}.json`), {
      at: new Date().toISOString(), before: prior, after: { pid: child.pid, generation: hostGeneration },
      original_owned_exit: exited, kernel_pid_unchanged: kernel.pid,
      same_private_home: true, same_ledger: true, prompts_sent_by_supervisor: 0,
    });
    console.log(`B0_HOST_RESTARTED generation=${hostGeneration}; same native history and original kernel`);
  })();
  try { await restartingHost; } finally { restartingHost = undefined; }
}
async function stop(reason, exitCode = 0) {
  if (stopping) return;
  stopping = true;
  const diagnosticReason = reason.startsWith('child-exit:') ? 'child-exit' : reason;
  lifecycle.record('stop-start', { reason: diagnosticReason, exitCode });
  if (restarting) await restarting;
  if (restartingHost) await restartingHost;
  if (child && child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
  if (childExit) {
    let drained = false;
    await Promise.race([childExit.then(() => { drained = true; }), delay(7000)]);
    if (!drained) { child.kill('SIGKILL'); await childExit; }
  }
  if (kernel && kernel.exitCode === null && kernel.signalCode === null) kernel.kill('SIGTERM');
  if (kernelExit) {
    let drained = false;
    await Promise.race([kernelExit.then(() => { drained = true; }), delay(7000)]);
    if (!drained) { kernel.kill('SIGKILL'); await kernelExit; }
  }
  await mock.close();
  // Do not retain mock Authorization headers; only synthetic body/outcomes.
  await writeJson(join(runtime, 'mock-evidence.json'), mock.requests.map(r => ({
    attempt: r.attempt, behavior: r.behavior, outcome: r.outcome, body: r.body,
  })));
  await writeJson(join(runtime, 'stopped.json'), { at: new Date().toISOString(), reason, pid: child?.pid, exitCode: child?.exitCode, signal: child?.signalCode });
  console.log(`B0_STOPPED ${reason}; original 5173/8000 untouched`);
  process.exitCode = exitCode;
  lifecycle.record('stop-complete', { reason: diagnosticReason, exitCode });
}
process.once('SIGTERM', () => { lifecycle.record('signal', { signal: 'SIGTERM' }); void stop('SIGTERM'); });
process.once('SIGINT', () => { lifecycle.record('signal', { signal: 'SIGINT' }); void stop('SIGINT'); });
process.on('SIGUSR1', () => { lifecycle.record('signal', { signal: 'SIGUSR1' }); void restartKernel(); });
process.on('SIGUSR2', () => { lifecycle.record('signal', { signal: 'SIGUSR2' }); void restartHost().catch(() => { void stop('host-restart-failed', 1); }); });
try {
  startKernel();
  await bootHost();
  console.log(`B0_READY http://127.0.0.1:${webPort}/ (synthetic native verification only)`);
  console.log(`B0_EVIDENCE ${runtime}`);
  while (!stopping) {
    const watched = child;
    const exit = await childExit;
    if (restartingHost) await restartingHost;
    else if (!stopping && watched === child) await stop(`child-exit:${JSON.stringify(exit)}`, exit.code ?? 1);
  }
} catch (error) {
  lifecycle.record('startup-error', { errorCode: error?.code });
  console.error(String(error));
  await stop('startup-failed', 1);
}
