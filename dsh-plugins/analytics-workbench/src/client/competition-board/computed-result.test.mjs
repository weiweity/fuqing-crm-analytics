import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { decodeCompetitionResultRef, canEndorse, formatAmountUnit } from './decode.mjs';
import { createHttpBoardTransport } from './transport.mjs';

const result = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/result.json', import.meta.url), 'utf8'));
const unitCases = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/unit-results.json', import.meta.url), 'utf8'));

test('units follow versioned computed facts; legacy results remain unchanged', () => {
  assert.equal(formatAmountUnit(result), '未记录（旧结果）');
  for (const [name, item] of Object.entries(unitCases)) {
    assert.ok(decodeCompetitionResultRef(item));
    assert.equal(canEndorse(item), true);
    assert.equal(item.facts.current.gsv, 410);
    assert.match(formatAmountUnit(item), name === 'unknown' ? /未知/ : name === 'major' ? /人民币元/ : /人民币分/);
  }
});

test('v2 HTTP decoder rejects missing, ambiguous or mismatched units', async () => {
  for (const change of [
    x => { delete x.facts.money_unit; },
    x => { x.facts.money_unit.status = 'KNOWN'; },
    x => { x.facts.money_unit.currency = 'CNY'; },
    x => { x.facts.money_unit.amount_unit = 'minor'; },
    x => { x.facts.money_unit.scale = 100; },
    x => { x.facts_schema_ref = result.facts_schema_ref; },
    x => { x.existing_result_schema = result.existing_result_schema; },
    x => { x.facts.schema_version = 'competition-gsv-facts/v3'; },
  ]) {
    const invalid = structuredClone(unitCases.unknown); change(invalid);
    assert.equal(decodeCompetitionResultRef(invalid), null);
    const transport = createHttpBoardTransport({ fetchImpl: async () => new Response(JSON.stringify({ items: [invalid] })) });
    const response = await transport.listEndorseableResults({});
    assert.equal(response.ok, false);
    assert.equal(response.status, 502);
  }
  const invalidOld = structuredClone(result);
  invalidOld.facts.money_unit = unitCases.minor.facts.money_unit;
  assert.equal(decodeCompetitionResultRef(invalidOld), null);
});

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
