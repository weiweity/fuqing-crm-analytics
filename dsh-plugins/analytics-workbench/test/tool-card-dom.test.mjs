import test from 'node:test';
import assert from 'node:assert/strict';
import { CARD_CASES, QUERY_CARD_CASES, loadCardHarness } from './tool-card-harness.mjs';
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
for (const example of QUERY_CARD_CASES) {
  test(`compiled React query tool card DOM: ${example.id}`, () => {
    const html = harness.renderQuery(example.block);
    assert.ok(html.includes(example.expected));
    assert.equal(html.includes('data-testid="analytics-query-tool-result"'), example.success);
    assert.equal(html.includes('role="status"'), !example.success);
    assert.doesNotMatch(html, /<script|<img|<a\b|SENSITIVE_FAKE_DETAIL|onerror=/i);
    assert.equal(html.includes('data-testid="analytics-query-cancel"'), example.id === 'query-running');
    if (example.id !== 'query-running') assert.doesNotMatch(html, /<button/i);
    if (!example.success) {
      assert.doesNotMatch(html, /25%|N=30|result_ref|EMPTY_MATURE_COHORT|空成熟队列/);
    }
    if (example.id === 'query-null') {
      assert.ok(html.includes('EMPTY_MATURE_COHORT'));
      assert.ok(html.includes('空成熟队列'));
    }
  });
}
test('query card stylesheet uses native DSH body token and does not keep the 13px body size', () => {
  assert.match(harness.css, /--dsw-font-base-16/);
  assert.doesNotMatch(harness.css, /\.analytics-query-card \{ font-size:13px/);
  assert.match(harness.css, /tabular-nums/);
  assert.match(harness.css, /\.analytics-query-card button \{/);
  assert.match(harness.css, /min-height:36px/);
  assert.doesNotMatch(harness.css, /min-height:44px/);
});
test('compiled plugin owns B0 and query tool keys, preserving other native card registrations', () => {
  assert.deepEqual(harness.registrations.filter(r => r.options.name === 'tool.call.toolview').map(r => r.options.key),
    ['analytics_b0_query', 'analytics_channel_followup_query', 'analytics_first_purchase_query']);
});
