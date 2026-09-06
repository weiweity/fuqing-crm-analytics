/** Snapshot the two completed B0 probes; never copy launch files or headers. */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const b0 = join(root, '.context/dsh-b0');
const read = async (relative) => JSON.parse(await readFile(join(b0, relative), 'utf8'));
const first = 'runtime-xlXpXV';
const second = 'runtime-281P9N';
const native = await read(`${first}/native-smoke-report.json`);
const gateway = await read(`${first}/gateway-smoke-report.json`);
const firstGateway = await read(`${first}/gateway-smoke-report-first-failed.json`);
const dispatch = await read(`${second}/browser-dispatch-report.json`);
const ledger = (await read(`${second}/gateway-evidence.json`)).dispatch;
const sandbox = JSON.parse((await read('sandbox-probe-xEvfZM/report.json')).stdout);
const nativeDependencies = JSON.parse((await read('sandbox-probe-A4VlAV/report.json')).stdout);
assert.equal(native.status, 'PASS');
assert.equal(gateway.status, 'PASS');
assert.equal(dispatch.status, 'PASS_SCOPED');
assert.equal(ledger.length, 1);
assert.equal(ledger[0].request_key, dispatch.request_key);
assert.equal(ledger[0].run_id, dispatch.duplicate.run_id);
assert.equal(ledger[0].request_hash, dispatch.request_hash);
assert.equal(ledger[0].state, 'DSH_ACCEPTED'); // Explicitly NOT a terminal business state.
assert(sandbox.allPassed && nativeDependencies.allPassed);

const rounds = [];
for (const runtime of [first, second]) {
  const stopped = await read(`${runtime}/stopped.json`);
  assert.equal(stopped.exitCode, 0);
  const mock = await read(`${runtime}/mock-evidence.json`);
  rounds.push({ runtime, stopped_at: stopped.at, exit_code: stopped.exitCode,
    provider_requests: mock.map(r => ({ attempt: r.attempt, behavior: r.behavior, outcome: r.outcome,
      advertised_tools: r.body.tools.map(tool => tool.function.name) })) });
}
assert.equal(rounds[0].provider_requests.length, 4);
assert.equal(rounds[0].provider_requests[2].outcome, 'client_closed');
assert.equal(rounds[1].provider_requests.length, 2);
const counts = tests => ({ passed: tests.filter(t => t.status === 'PASS').length,
  failed: tests.filter(t => t.status === 'FAIL').length });
const report = {
  schema_version: 'dsh-b0-evidence/v1', collected_at: new Date().toISOString(),
  verdict: 'PARTIAL_NOT_INTEGRATION_READY', synthetic_only: true, paid_model_calls: 0,
  upstream_sha: 'd347e703908d0406b7a7ef80e3a0e594d86b2215',
  raw_payloads_or_credentials_copied: false,
  sandbox: { passed: sandbox.results.filter(r => r.passed).length, total: sandbox.results.length },
  native_dependencies: { passed: nativeDependencies.results.filter(r => r.passed).length, total: nativeDependencies.results.length },
  gateway_first_run: counts(firstGateway.tests), gateway_fixed_retest: counts(gateway.tests),
  native: { primary: native.primary.status, cancellation: native.cancellation.status,
    server_error: native.server_error.status, primary_turn_ends: native.primary.turn_ends,
    cancellation_turn_ends: native.cancellation.turn_ends, error_turn_ends: native.server_error.turn_ends },
  browser_dispatch: { status: dispatch.status, request_key: dispatch.request_key, request_hash: dispatch.request_hash,
    run_id: dispatch.duplicate.run_id, original_ledger_state: ledger[0].state, ledger_rows: ledger.length,
    duplicate_status: dispatch.duplicate.status, changed_request_status: dispatch.conflict.status,
    later_request_status: dispatch.later_request.status, limitations: dispatch.limitations },
  rounds,
  limitations: [
    'No complete AnalysisRun, per-run cancellation, durable terminal observer, restart recovery or fencing.',
    'No production identity service, semantic SQL goldens, real model evaluation, or full multi-user security audit.',
    'Cockpit is one static synthetic fixture; localStorage persists a cosmetic title only.',
    'Logo/favicon, all tool-card states, Skill/compaction, BI filter round trip and load limits remain incomplete.',
    'Native UI still exposes denied developer controls; console is not clean.',
    'Browser screenshots and test commands are documented separately; this collector does not rerun them.',
  ],
};
const target = join(root, 'docs/hackathon/assets/b0/evidence.json');
await writeFile(target, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({ target, verdict: report.verdict, gateway: report.gateway_fixed_retest,
  ledger_rows: ledger.length, temporary_runtimes_stopped: rounds.length }));
