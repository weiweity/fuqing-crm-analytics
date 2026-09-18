import test from 'node:test';
import assert from 'node:assert/strict';
import { createErrorBoundary, hostRecoveryCopy } from './error-boundary.mjs';

test('error boundary keeps host available and does not imply a new saved version', () => {
  const boundary = createErrorBoundary({ pageId: 'page_fixture_unbound', version: 1 });
  boundary.running();
  boundary.fail('PAGE_SCRIPT', 'canvas 脚本抛错');
  const state = boundary.getState();
  assert.equal(state.status, 'error');
  assert.equal(state.hostAvailable, true);
  assert.equal(state.recoverable, true);
  assert.match(hostRecoveryCopy(state), /宿主/);
  boundary.restoring({ version: 1 });
  boundary.restored({ version: 1 });
  assert.equal(boundary.getState().status, 'running');
});
