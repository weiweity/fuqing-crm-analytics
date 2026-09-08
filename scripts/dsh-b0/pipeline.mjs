/** One local/CI pipeline. --check installs nothing and never opens a business DB.
 * --prepare explicitly fetches only the pinned public DSH and build dependency
 * closure; it never switches/resets an existing checkout or installs globally.
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile, writeFile, mkdir, mkdtemp, cp, lstat, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { packageManagerEnv } from './package-manager-env.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const plugin = join(root, 'dsh-plugins/analytics-workbench');
const b0 = join(root, '.context/dsh-b0');
const buildTools = join(plugin, 'build-tools');
const [mode, pythonFlag, python, ...extra] = process.argv.slice(2);
assert.ok(['--prepare', '--check'].includes(mode) && pythonFlag === '--python' && isAbsolute(python ?? '') && !extra.length,
  'Usage: node scripts/dsh-b0/pipeline.mjs --prepare|--check --python /absolute/python3.14');
assert.ok(!process.env.B0_BUILD_UPSTREAM || mode === '--check',
  'B0_BUILD_UPSTREAM is a read-only --check override; --prepare must use the local pinned checkout');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(b0, 'upstream'));
const pin = JSON.parse(await readFile(join(plugin, 'toolchain.json'), 'utf8'));
assert.equal(Number(process.versions.node.split('.')[0]), pin.node_major);
let env = {
  ...Object.fromEntries(Object.entries(process.env).filter(([key]) => ['HOME', 'CI', 'SYSTEMROOT'].includes(key))),
  PATH: `${dirname(process.execPath)}:${dirname(python)}:/usr/bin:/bin`,
  PYTHONPATH: root, PYTHONNOUSERSITE: '1', PYTHON_DOTENV_DISABLED: '1',
  PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1',
  B0_BUILD_UPSTREAM: upstream,
  COREPACK_ENABLE_DOWNLOAD_PROMPT: '0', LEFTHOOK: '0',
};
function run(command, args, cwd = root, extraEnv = {}) {
  const result = spawnSync(command, args, { cwd, env: { ...env, ...extraEnv }, stdio: 'inherit', timeout: 900000 });
  assert.ok(!result.error && result.status === 0, `B0 stage failed: ${command} ${args.join(' ')} (${result.error?.message ?? result.status})`);
}
function output(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, env, encoding: 'utf8', timeout: 30000, maxBuffer: 1024 * 1024 });
  assert.ok(!result.error && result.status === 0, `B0 verification failed: ${result.error?.message ?? result.stderr}`);
  return result.stdout.trim();
}
const git = args => output('git', ['-C', upstream, ...args]);
async function verifySource() {
  assert.equal(git(['rev-parse', 'HEAD']), pin.upstream_sha, 'Pinned upstream SHA mismatch');
  assert.equal(git(['status', '--porcelain', '--untracked-files=no']), '', 'Refusing locally modified upstream');
  assert.equal(createHash('sha256').update(await readFile(join(upstream, 'pnpm-lock.yaml'))).digest('hex'), pin.upstream_lock_sha256);
  assert.equal(JSON.parse(await readFile(join(upstream, 'package.json'), 'utf8')).packageManager, `pnpm@${pin.pnpm}`);
}
await mkdir(b0, { recursive: true, mode: 0o700 });
if (mode === '--prepare') {
  let exists = true;
  try { await lstat(upstream); } catch (error) { if (error.code !== 'ENOENT') throw error; exists = false; }
  if (!exists) {
    await mkdir(upstream, { mode: 0o700 });
    run('git', ['init', '--quiet', upstream]);
    run('git', ['-C', upstream, 'fetch', '--depth=1', pin.upstream_url, pin.upstream_sha]);
    run('git', ['-C', upstream, 'checkout', '--detach', pin.upstream_sha]);
  }
  await verifySource();
  env = await packageManagerEnv(join(b0, 'tool-bin'), env, upstream);
  assert.equal(output('corepack', ['pnpm', '--version'], upstream), pin.pnpm);
  run('corepack', ['pnpm', 'install', '--frozen-lockfile', '--ignore-scripts', '--registry=https://registry.npmjs.org'], upstream);
  // Only native dependencies needed by this fixed profile. No repository hook
  // installer, optional provider SDK lifecycle, global configuration or publish.
  run('corepack', ['pnpm', 'rebuild', 'esbuild', 'fs-ext', 'koffi', 'node-pty'], upstream);
  run('corepack', ['pnpm', 'run', 'build:official'], upstream);
  run('corepack', ['pnpm', 'install', '--frozen-lockfile', '--ignore-scripts', '--registry=https://registry.npmjs.org'], buildTools);
  await verifySource();
  console.log('B0 pinned preparation complete; run --check next. Python packages are never installed by this script.');
} else {
  await verifySource();
  for (const file of ['asset-ui-smoke.mjs', 'theme-ui-smoke.mjs', 'native-ui-smoke.mjs', 'native-card-smoke.mjs', 'native-state-smoke.mjs', 'native-query-smoke.mjs', 'native-query-fault-smoke.mjs', 'native-query-fault-scenario.mjs', 'query-scenario.mjs', 'tool-card-dom-smoke.mjs', 'gateway-smoke.mjs', 'control-permission-probe.mjs', 'native-query-assets-smoke.mjs', 'asset-routes.mjs']) {
    run(process.execPath, ['--check', join(root, 'scripts/dsh-b0', file)]);
  }
  run(python, ['-c', String.raw`
import importlib.metadata as metadata, pathlib, sys
assert sys.version_info >= (3, 14), 'Use explicit Python 3.14+'
for line in pathlib.Path('scripts/dsh-b0/requirements.lock').read_text().splitlines():
    if not line or line.startswith('#'): continue
    name, version = line.split('==')
    assert metadata.version(name) == version, f'B0 dependency drift: {name}'
print('B0 exact Python closure verified')
`]);
  run(process.execPath, ['scripts/dsh-b0/run-kernel-contract.mjs', '--check', '--python', python]);
  run(process.execPath, ['scripts/dsh-b0/query-contract.mjs', '--check', '--python', python]);
  run(process.execPath, ['scripts/dsh-b0/query-run-contract.mjs', '--check', '--python', python]);
  run(process.execPath, ['scripts/dsh-b0/analysis-contract.mjs', '--check', '--python', python]);
  run(process.execPath, ['scripts/dsh-b0/cockpit-contract.mjs', '--check', '--python', python]);
  const pyTests = ['jobs', 'access', 'run_contracts', 'run_resources', 'native_runtime', 'worker', 'context', 'native_probe', 'query_contracts', 'channel_followup', 'query_jobs', 'query_run_contracts', 'query_worker', 'query_runtime', 'query_native_fault', 'saved_analyses', 'analysis_http', 'cockpit', 'cockpit_http', 'query_assets_runtime'].map(name => `backend/tests/test_analytics_${name}.py`);
  run(python, ['-m', 'pytest', '--noconftest', '-W', 'error::ResourceWarning', '-q', ...pyTests]);
  run(python, ['-m', 'ruff', 'check', 'backend/analytics_app.py', 'backend/analytics_runtime.py', 'backend/analytics_query_app.py',
    'backend/analytics_analysis_app.py', 'backend/analytics_cockpit_app.py',
    'backend/analytics_fixture.py', 'backend/analytics_query_fixture.py', 'backend/analytics_worker.py', 'backend/semantic/analytics_b0.py',
    'backend/semantic/analytics_channel_followup.py',
    'backend/contracts/analytics.py', 'backend/contracts/analytics_query.py', 'backend/contracts/analytics_query_run.py',
    'backend/contracts/analytics_analysis.py', 'backend/contracts/analytics_cockpit.py', 'backend/services/analytics', 'backend/tests/analytics_run_support.py',
    'backend/tests/analytics_run_fault_probe.py', 'backend/tests/analytics_worker_probe.py',
    'backend/tests/analytics_query_worker_probe.py',
    'backend/tests/analytics_native_probe.py', 'backend/tests/analytics_query_native_fault_probe.py', ...pyTests]);
  const builtTests = ['built.test.mjs', 'loader.test.mjs', 'skills-loader.test.mjs', 'tool-card-dom.test.mjs', 'query-skills-loader.test.mjs', 'sessionless-view-dom.test.mjs', 'query-card-fault.test.mjs', 'query-card-cancel.test.mjs', 'query-card-save.test.mjs', 'asset-overlay.test.mjs'];
  const sourceTests = (await readdir(join(plugin, 'test'))).filter(name => name.endsWith('.test.mjs') && !builtTests.includes(name));
  run(process.execPath, ['--test', ...sourceTests.map(name => join(plugin, 'test', name)),
    'scripts/dsh-b0/gateway-policy.test.mjs', 'scripts/dsh-b0/transport-safety.test.mjs', 'scripts/dsh-b0/mock-provider.test.mjs',
    'scripts/dsh-b0/lifecycle-observer.test.mjs', 'scripts/dsh-b0/permission-fence.test.mjs', 'scripts/dsh-b0/ui-seams.test.mjs',
    'scripts/dsh-b0/package-manager-env.test.mjs', 'scripts/dsh-b0/diagnostic-sink.test.mjs',
    'scripts/dsh-b0/native-state-smoke.test.mjs', 'scripts/dsh-b0/native-query-smoke.test.mjs',
    'scripts/dsh-b0/native-query-fault-smoke.test.mjs', 'scripts/dsh-b0/native-query-assets-smoke.test.mjs',
    'scripts/dsh-b0/asset-routes.test.mjs']);
  run(process.execPath, [join(plugin, 'build.mjs'), upstream]);
  run(process.execPath, ['--test', ...builtTests.map(file => join(plugin, 'test', file))], root, { B0_BUILD_UPSTREAM: upstream });

  const clean = await mkdtemp(join(b0, 'clean-build-'));
  // No source symlinks or existing output/node_modules in the clean copy.
  for (const item of ['package.json', 'toolchain.json', 'toolchain.mjs', 'build.mjs', 'pack-skills.mjs', 'skill-package.lock.json', 'query-skill-package.lock.json', 'skills', 'src', 'test']) {
    await cp(join(plugin, item), join(clean, item), { recursive: true, errorOnExist: true, force: false, dereference: true });
  }
  run(process.execPath, [join(clean, 'build.mjs'), upstream]);
  run(process.execPath, ['--test', ...builtTests.map(file => join(clean, 'test', file))], clean, { B0_BUILD_UPSTREAM: upstream });
  const hashes = {};
  for (const item of ['index.js', 'tool.js', 'skills.js', 'client.js', 'views/saved-analysis-view.js', 'views/cockpit-view.js']) {
    const original = await readFile(join(plugin, 'lib', item));
    const rebuilt = await readFile(join(clean, 'lib', item));
    assert.deepEqual(original, rebuilt, `Clean build output mismatch: ${item}`);
    assert.ok(!/file:\/\/\/|\/Users\/|\/home\/runner\//.test(rebuilt.toString()), `Machine path in artifact: ${item}`);
    hashes[item] = createHash('sha256').update(rebuilt).digest('hex');
  }
  const report = { schema_version: 'dsh-b0-build-evidence/v1', at: new Date().toISOString(),
    upstream_sha: pin.upstream_sha, upstream_lock_sha256: pin.upstream_lock_sha256,
    node: process.version, python: output(python, ['--version']), clean_plugin: clean,
    stages: ['contract', 'python-unit', 'ruff', 'node-unit', 'host-types', 'client-types', 'build', 'real-cordis-loader-synthetic-services', 'clean-rebuild'],
    artifact_sha256: hashes, remote_ci_executed: false, native_dsh_profile_e2e: 'separate evidence required' };
  await writeFile(join(b0, 'build-evidence.json'), JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
  console.log(`B0 pipeline passed; clean plugin: ${clean}`);
}
