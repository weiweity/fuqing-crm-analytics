import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { decodeCompetitionResultRef, canEndorse } from './decode.mjs';
import { createHttpBoardTransport } from './transport.mjs';

const result = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/result.json', import.meta.url), 'utf8'));

test('computed GSV is a separate, endorsable saved result with raw ratios', () => {
  assert.ok(decodeCompetitionResultRef(result));
  assert.equal(result.facts.current.gsv, 410);
  assert.equal(result.facts.comparison.gsv, 305);
  assert.equal(result.facts.difference, 105);
  assert.equal(canEndorse(result), true);
  assert.equal(canEndorse({ ...result, analysis_id: null }), false);
});

test('computed decoder rejects forged family, percentages and corrupt values', () => {
  for (const change of [
    x => { x.execution_kind = 'MODEL_RUN'; },
    x => { x.query_version = 'channel-followup-query/v1'; },
    x => { x.facts.current.gsv = '410'; },
    x => { x.facts.current.gsv = NaN; },
    x => { x.facts.current.customer_count = 100; },
    x => { x.facts.current.through_date = '2026-09-20'; },
    x => { x.facts.change_ratio *= 100; },
    x => { x.facts.difference = 0; },
    x => { x.row_count = 1; },
    x => { x.evidence_digest = 'broken'; },
  ]) {
    const invalid = structuredClone(result); change(invalid);
    assert.equal(decodeCompetitionResultRef(invalid), null);
    assert.equal(canEndorse(invalid), false);
  }
});

test('HTTP transport does not load malformed computed amounts into endorsement list', async () => {
  const invalid = structuredClone(result); invalid.facts.current.gsv = 'bad';
  const transport = createHttpBoardTransport({ baseUrl: 'http://127.0.0.1:18084', token: 'synthetic-test-token',
    fetchImpl: async () => new Response(JSON.stringify({ items: [invalid] }), { status: 200 }) });
  const response = await transport.listEndorseableResults({});
  assert.equal(response.ok, false);
  assert.equal(response.status, 502);
});
