import test from 'node:test';
import assert from 'node:assert/strict';
import { namespaceToolCallLine, startB0MockProvider } from './mock-provider.mjs';
import { startMockLlmServer } from '../../.context/dsh-b0/upstream/packages/test-support/llm-mock-server/lib/index.js';

test('fixture namespaces only request-scoped tool identity, keeping arguments and facts unchanged', () => {
  const original = 'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"mock-call-1","function":{"name":"any_tool","arguments":"{\\\"x\\\":1}"}}]}}]}';
  const one = JSON.parse(namespaceToolCallLine(original, 1).slice(5));
  const two = JSON.parse(namespaceToolCallLine(original, 2).slice(5));
  assert.notEqual(one.choices[0].delta.tool_calls[0].id, two.choices[0].delta.tool_calls[0].id);
  one.choices[0].delta.tool_calls[0].id = 'mock-call-1';
  assert.deepEqual(one, JSON.parse(original.slice(5)));
  for (const line of ['', 'event: message', 'data: [DONE]', 'data: {"choices":[{"delta":{"content":"合成文本"}}]}']) {
    assert.equal(namespaceToolCallLine(line, 1), line);
  }
});

test('official mock wire uses distinct native IDs and observes actual client closure', async () => {
  const mock = await startB0MockProvider(startMockLlmServer, { port: 0, apiKey: 'test-stub-only',
    sequence: ['tool_call_success', 'tool_call_success', 'slow_success'], successText: '合成流', chunkSize: 1, chunkDelayMs: 500 });
  const request = signal => fetch(`${mock.baseURL}/v1/chat/completions`, { method: 'POST',
    headers: { 'content-type': 'application/json', authorization: 'Bearer test-stub-only' }, body: '{}', signal });
  try {
    const first = await (await request()).text();
    const second = await (await request()).text();
    assert.ok(first.includes('b0-request-1:mock-call-1'));
    assert.ok(second.includes('b0-request-2:mock-call-1'));
    const abort = new AbortController();
    const response = await request(abort.signal);
    const reader = response.body.getReader();
    assert.equal((await reader.read()).done, false);
    abort.abort();
    await reader.cancel().catch(() => {});
    const deadline = Date.now() + 3000;
    while (mock.requests[2].outcome === undefined && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(mock.requests[2].outcome, 'client_closed');
  } finally { await mock.close(); }
});

test('finite multi-tool script configures official producers and refuses exhaustion', async () => {
  const mock = await startB0MockProvider(startMockLlmServer, { port: 0, apiKey: 'test-stub-only',
    sequence: ['tool_call_success'], script: [
      { toolName: 'analytics_b0_query', toolArguments: '{"query":"channel_repeat_rate"}' },
      { toolName: 'skill', toolArguments: '{"name":"growth-analysis-b0"}' },
    ] });
  const request = () => fetch(`${mock.baseURL}/v1/chat/completions`, { method: 'POST',
    headers: { 'content-type': 'application/json', authorization: 'Bearer test-stub-only' }, body: '{}' });
  try {
    const first = await (await request()).text();
    const second = await (await request()).text();
    assert.ok(first.includes('analytics_b0_query') && first.includes('b0-request-1:mock-call-1'));
    assert.ok(second.includes('"name":"skill"') && second.includes('b0-request-2:mock-call-1'));
    const exhausted = await request();
    assert.equal(exhausted.status, 409);
    await exhausted.text();
    assert.equal(mock.requests.length, 2);
  } finally { await mock.close(); }
});
