import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { HTML_SANDBOX } from '../../board-spec/html-sandbox.mjs';
import {
  FREE_PAGE_SANDBOX, describeIsolation, sandboxAllowsSameOrigin, sandboxAllowsScripts,
} from './isolation-policy.mjs';

const here = dirname(fileURLToPath(import.meta.url));

test('old static sandbox remains no-script; free-page sandbox is not a CPU isolation claim', async () => {
  assert.equal(HTML_SANDBOX, '');
  assert.equal(sandboxAllowsScripts(HTML_SANDBOX), false);
  assert.equal(sandboxAllowsScripts(FREE_PAGE_SANDBOX), true);
  assert.equal(sandboxAllowsSameOrigin(FREE_PAGE_SANDBOX), false);
  const described = describeIsolation();
  assert.equal(described.allowSameOrigin, false);
  assert.equal(described.permissionIsolation, true);
  assert.match(String(described.cpuIsolation), /unverified|not a CPU isolation claim|sandbox attributes/i);
  const source = await readFile(resolve(here, '../../board-spec/html-sandbox.mjs'), 'utf8');
  assert.doesNotMatch(source, /allow-scripts/);
});
