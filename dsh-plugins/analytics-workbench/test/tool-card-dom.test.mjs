import test from 'node:test';
import assert from 'node:assert/strict';
import { CARD_CASES, loadCardHarness } from './tool-card-harness.mjs';
const harness = await loadCardHarness();
for (const example of CARD_CASES) {
  test(`compiled React tool card DOM: ${example.id}`, () => {
    const html = harness.render(example.block);
    assert.ok(html.includes(example.expected));
    assert.equal(html.includes('data-testid="analytics-b0-tool-result"'), example.success);
    assert.equal(html.includes('role="status"'), !example.success);
    assert.doesNotMatch(html, /<script|<img|<button|<a\b|SENSITIVE_FAKE_DETAIL|onerror=|99%/i);
    if (!example.success) assert.doesNotMatch(html, /25%|100 位|25 位/);
  });
}
test('compiled plugin owns only its tool key, preserving other native card registrations', () => {
  assert.deepEqual(harness.registrations.filter(r => r.options.name === 'tool.call.toolview').map(r => r.options.key), ['analytics_b0_query']);
});
