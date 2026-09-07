/** Render the actual compiled standalone views with the pinned React renderer. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { SavedAnalysisView } from '../lib/views/saved-analysis-view.js';

const root = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(root, '../../.context/dsh-b0/upstream'));
const require = createRequire(join(upstream, 'apps/web/package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

for (const [name, Component, marker] of [
  ['saved analysis', SavedAnalysisView, 'analytics-saved-analysis-view'],
]) {
  test(`compiled ${name} renders without a session and preserves unavailable/denied states`, () => {
    const empty = renderToStaticMarkup(React.createElement(Component, { list: [], sessionId: null }));
    assert.ok(empty.includes(`data-testid="${marker}"`));
    assert.ok(empty.includes('data-kind="empty"'));
    assert.ok(empty.includes('data-http="NOT_CONNECTED"'));
    const denied = renderToStaticMarkup(React.createElement(Component, {
      error: { status: 403, code: 'FORBIDDEN', message: 'SENSITIVE_FIXTURE' },
    }));
    assert.ok(denied.includes('data-kind="error"'));
    assert.ok(denied.includes('当前身份不可见'));
    assert.ok(!denied.includes('SENSITIVE_FIXTURE'));
  });
}
