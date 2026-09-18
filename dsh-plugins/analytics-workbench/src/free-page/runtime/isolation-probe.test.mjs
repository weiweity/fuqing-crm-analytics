import test from 'node:test';
import assert from 'node:assert/strict';
import { runIsolationProbe } from './isolation-probe.mjs';
import { chromeAvailable } from './chrome-cdp.mjs';

test('T0 Chrome fixture: host operable, close/restart, saved restore; no CPU claim from sandbox', {
  timeout: 120_000,
  skip: chromeAvailable() ? false : 'Google Chrome is not installed',
}, async () => {
  const evidence = await runIsolationProbe();
  assert.ok(evidence.browser.version);
  assert.equal(evidence.sandbox, 'allow-scripts');
  assert.equal(evidence.allowSameOrigin, false);
  assert.equal(evidence.ports.avoided, 6677);
  assert.notEqual(evidence.ports.harness, 6677);
  assert.equal(evidence.gates.host_operable, true, JSON.stringify(evidence.gates));
  assert.equal(evidence.gates.close_restart, true, JSON.stringify(evidence.gates));
  assert.equal(evidence.gates.saved_restore, true, JSON.stringify(evidence.gates));
  assert.equal(Array.isArray(evidence.egress_proxy_hits), true);
  assert.doesNotMatch(String(evidence.cpu_isolation), /^true$/i);
});
