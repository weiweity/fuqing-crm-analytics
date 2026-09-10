import test from 'node:test';
import assert from 'node:assert/strict';
import { createHttpBoardTransport } from './competition-board/transport.mjs';
import {
  createHttpAudienceTransport, wrapAudiencePreviewPayload,
} from './competition-actions/transport.mjs';
import { assertCompetitionHttpBase, competitionHttpOptions } from './competition-http.mjs';
import { RESULT_SUCCESS } from './competition-board/c0-fixtures.mjs';

test('competition HTTP options refuse user demo ports', () => {
  assert.throws(() => assertCompetitionHttpBase('http://127.0.0.1:4327'), /4327/);
  assert.throws(() => assertCompetitionHttpBase('http://127.0.0.1:8000/api'), /8000/);
  assert.throws(() => assertCompetitionHttpBase('http://127.0.0.1:5173'), /5173/);
  assert.equal(assertCompetitionHttpBase('http://127.0.0.1:18082'), 'http://127.0.0.1:18082');
  const previousBase = process.env.COMPETITION_HTTP_BASE;
  const previousToken = process.env.COMPETITION_HTTP_TOKEN;
  delete process.env.COMPETITION_HTTP_BASE;
  delete process.env.COMPETITION_HTTP_TOKEN;
  try {
    assert.equal(competitionHttpOptions(), null);
  } finally {
    if (previousBase === undefined) delete process.env.COMPETITION_HTTP_BASE;
    else process.env.COMPETITION_HTTP_BASE = previousBase;
    if (previousToken === undefined) delete process.env.COMPETITION_HTTP_TOKEN;
    else process.env.COMPETITION_HTTP_TOKEN = previousToken;
  }
});

test('HTTP audience wrap turns UI chips into C0 T05 preview body', () => {
  const wrapped = wrapAudiencePreviewPayload({ combine: 'AND', rules: ['ORIGIN_CHANNEL_ABSENT'] });
  assert.equal(wrapped.cohort.cohort_id, 'cohort_t05_ly_f4_10');
  assert.equal(wrapped.auto_send, false);
  assert.equal(wrapped.cohort.rules[0].non_repurchase, 'ORIGIN_CHANNEL_ABSENT');
  const already = wrapAudiencePreviewPayload({ cohort: { cohort_id: 'cohort_a9_t05_ly_f4_10' } });
  assert.equal(already.cohort.cohort_id, 'cohort_a9_t05_ly_f4_10');
});

test('HTTP transports post C0 paths and unwrap results list', async () => {
  const calls = [];
  const fetchImpl = async (path, init = {}) => {
    calls.push({ path, method: init.method || 'GET', body: init.body ? JSON.parse(init.body) : null });
    if (String(path).endsWith('/results')) {
      return {
        status: 200,
        async json() { return { items: [structuredClone(RESULT_SUCCESS)], http_api: 'CONNECTED' }; },
      };
    }
    if (String(path).includes('/candidates/preview')) {
      return {
        status: 200,
        async json() {
          return {
            candidates: { candidate_set_id: 'cand_http_1', unique_count: 6, customer_keys: ['t05u05'] },
            http_api: 'CONNECTED',
          };
        },
      };
    }
    if (String(path).includes('/diagnosis/capabilities')) {
      return { status: 200, async json() { return { live_transport: 'HTTP_CONNECTED' }; } };
    }
    return { status: 200, async json() { return { http_api: 'CONNECTED' }; } };
  };
  const board = createHttpBoardTransport({ fetchImpl });
  const listed = await board.listEndorseableResults();
  assert.equal(listed.ok, true);
  assert.equal(listed.body[0].result_id, RESULT_SUCCESS.result_id);
  const audience = createHttpAudienceTransport({ fetchImpl });
  const preview = await audience.previewCandidates({}, { combine: 'AND', rules: ['STOREWIDE_ABSENT'] });
  assert.equal(preview.ok, true);
  assert.equal(preview.body.candidates.candidate_set_id, 'cand_http_1');
  assert.equal(calls[0].path, '/api/v1/analytics/competition/results');
  assert.equal(calls[1].path, '/api/v1/analytics/competition/candidates/preview');
  assert.equal(calls[1].body.cohort.cohort_id, 'cohort_t05_ly_f4_10');
  assert.equal(calls[1].body.cohort.rules[0].non_repurchase, 'STOREWIDE_ABSENT');
});
