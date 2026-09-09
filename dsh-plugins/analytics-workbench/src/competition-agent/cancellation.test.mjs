import test from 'node:test';
import assert from 'node:assert/strict';
import { liveDiagnosisCall } from './tools.mjs';

for (const kind of ['CANCELLED', 'ALREADY_PUBLISHED', 'UNCONFIRMED', 'wrong-binding']) {
  test(`native abort preserves publication outcome: ${kind}`, async () => {
    const before = { base: process.env.COMPETITION_HTTP_BASE, token: process.env.COMPETITION_HTTP_TOKEN };
    const fetchBefore = globalThis.fetch;
    const calls = [];
    const controller = new AbortController();
    const args = { session_id: 'actual-host-session', request_id: 'step-1', condition: { private: 'not-in-cancel' } };
    try {
      process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:18083';
      process.env.COMPETITION_HTTP_TOKEN = 'synthetic-test-token';
      globalThis.fetch = async (url, options) => {
        calls.push({ url, options });
        if (url.endsWith('/step')) return new Promise((_resolve, reject) => {
          options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true });
        });
        assert.equal(options.signal.aborted, false, 'cancel needs a fresh signal');
        if (kind === 'UNCONFIRMED') throw new Error('cancel network unavailable');
        if (kind === 'ALREADY_PUBLISHED') return Response.json({ error: { code: kind } }, { status: 409 });
        return Response.json({ status: 'CANCELLED', session_id: kind === 'wrong-binding' ? 'another-session' : args.session_id,
          request_id: args.request_id, late_attempt_publish: false });
      };
      const pending = liveDiagnosisCall('competition_growth_step', args, controller.signal);
      controller.abort();
      await assert.rejects(pending, error => {
        assert.equal(error.name, 'AbortError');
        assert.equal(error.cancellation.status, kind === 'wrong-binding' ? 'UNCONFIRMED' : kind);
        return true;
      });
      assert.equal(calls.length, 2, 'one execution and one cancel, no execution retry');
      assert.match(calls[1].url, /\/diagnosis\/cancel$/);
      assert.deepEqual(JSON.parse(calls[1].options.body), { session_id: args.session_id, request_id: args.request_id });
      assert.equal(calls[1].options.redirect, 'error');
      await assert.rejects(liveDiagnosisCall('competition_growth_step', args, controller.signal), { name: 'AbortError' });
      assert.equal(calls.length, 2, 'already-aborted tools cannot dispatch');
    } finally {
      globalThis.fetch = fetchBefore;
      if (before.base === undefined) delete process.env.COMPETITION_HTTP_BASE; else process.env.COMPETITION_HTTP_BASE = before.base;
      if (before.token === undefined) delete process.env.COMPETITION_HTTP_TOKEN; else process.env.COMPETITION_HTTP_TOKEN = before.token;
    }
  });
}
