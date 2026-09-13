import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { decodeCompetitionResultRef, canEndorse, formatAmountUnit, round4 } from './decode.mjs';
import { createHttpBoardTransport } from './transport.mjs';

const result = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/result.json', import.meta.url), 'utf8'));
const unitCases = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/unit-results.json', import.meta.url), 'utf8'));
const dailyCases = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/daily-results.json', import.meta.url), 'utf8'));
const waterfallCases = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/waterfall-results.json', import.meta.url), 'utf8'));
const funnelCases = JSON.parse(readFileSync(new URL('../../../tests/competition-computed/funnel-results.json', import.meta.url), 'utf8'));

test('actual v5 counts share the current purchasing cohort without changing v4 amounts or units', () => {
  for (const [name, item] of Object.entries(funnelCases)) {
    assert.ok(decodeCompetitionResultRef(item), name);
    assert.deepEqual(item.facts.channel_bridge, waterfallCases[name].facts.channel_bridge);
    assert.deepEqual(item.facts.current, { ...waterfallCases[name].facts.current, customer_count_unavailable_reason: null });
    const frequency = item.facts.current_purchase_frequency;
    assert.equal(frequency.status, 'AVAILABLE');
    assert.equal(frequency.stages[0].customer_count, item.facts.current.customer_count);
    assert.equal(formatAmountUnit(item), formatAmountUnit(waterfallCases[name]));
  }
});

test('v5 rejects missing, misleading, nonnested and extra funnel data', () => {
  for (const change of [
    x => { delete x.facts.current_purchase_frequency; },
    x => { x.facts.current_purchase_frequency.stages.pop(); },
    x => { x.facts.current_purchase_frequency.stages.reverse(); },
    x => { x.facts.current_purchase_frequency.stages[0].customer_count += 1; },
    x => { x.facts.current_purchase_frequency.stages[1].customer_count = true; },
    x => { x.facts.current_purchase_frequency.stages[1].customer_count = 100; },
    x => { x.facts.current_purchase_frequency.stages[0].extra = true; },
    x => { x.facts.current_purchase_frequency.extra = true; },
    x => { x.facts.current_purchase_frequency.entity = 'VISITOR'; },
    x => { x.facts.current_purchase_frequency.status = 'UNAVAILABLE'; },
    x => { Object.assign(x.facts.current_purchase_frequency, { status: 'UNAVAILABLE', unavailable_reason: 'PERIOD_UNAVAILABLE', stages: [] }); },
  ]) {
    const invalid = structuredClone(funnelCases.major); change(invalid);
    assert.equal(decodeCompetitionResultRef(invalid), null);
  }
  const unavailable = structuredClone(funnelCases.major);
  Object.assign(unavailable.facts.current_purchase_frequency, { status: 'UNAVAILABLE', unavailable_reason: 'INVALID_CUSTOMER', stages: [] });
  Object.assign(unavailable.facts.current, { customer_count: null, customer_count_unavailable_reason: 'INVALID_CUSTOMER' });
  assert.ok(decodeCompetitionResultRef(unavailable), 'unavailable funnel cannot invalidate other valid representations');
});

test('actual v4 results retain daily data and validate the channel contribution bridge', () => {
  for (const [name, item] of Object.entries(waterfallCases)) {
    assert.ok(decodeCompetitionResultRef(item), name);
    assert.equal(canEndorse(item), true);
    assert.deepEqual(item.facts.current_daily, dailyCases[name].facts.current_daily);
    assert.equal(item.facts.channel_bridge.status, name === 'unknown' ? 'UNAVAILABLE' : 'AVAILABLE');
    assert.equal(formatAmountUnit(item), formatAmountUnit(dailyCases[name]));
  }
});

test('v4 rejects corrupt or fabricated channel contributions, even when totals remain available', () => {
  for (const change of [
    x => { delete x.facts.channel_bridge; },
    x => { x.facts.channel_bridge.contributions[0].delta += 1; },
    x => { x.facts.channel_bridge.contributions.pop(); },
    x => { x.facts.channel_bridge.contributions[0].current_gsv += 1; },
    x => { x.facts.channel_bridge.contributions[0].delta = true; },
    x => { x.facts.channel_bridge.dimension = 'CAUSE'; },
    x => { x.facts.channel_bridge.contributions.reverse(); },
    x => { x.facts.channel_bridge.status = 'UNAVAILABLE'; },
    x => { x.facts.channel_bridge.contributions[0].channel = ''; },
    x => { x.facts.channel_bridge.contributions[0].unit = 'USD'; },
    x => { x.facts.channel_bridge.unavailable_reason = 'MONEY_UNIT_UNKNOWN'; },
  ]) {
    const invalid = structuredClone(waterfallCases.major); change(invalid);
    assert.equal(decodeCompetitionResultRef(invalid), null);
  }
});

test('actual v3 daily results are decodable and retain source-declared raw units', () => {
  for (const [name, item] of Object.entries(dailyCases)) {
    assert.ok(decodeCompetitionResultRef(item), name);
    assert.equal(canEndorse(item), true);
    const series = item.facts.current_daily;
    assert.equal(series.points.length, 31);
    assert.equal(series.points.reduce((sum, p) => sum + p.gsv, 0), item.facts.current.gsv);
    assert.equal(formatAmountUnit(item), formatAmountUnit(unitCases[name]));
  }
});

test('v3 refuses absent, reordered, invented, nonfinite and unsupported daily facts', () => {
  for (const change of [
    x => { delete x.facts.current_daily; },
    x => { x.facts.current_daily.points.reverse(); },
    x => { x.facts.current_daily.points.pop(); },
    x => { x.facts.current_daily.points[0].gsv = Infinity; },
    x => { x.facts.current_daily.points[0].gsv = '10'; },
    x => { x.facts.current_daily.points[0].gsv = null; },
    x => { x.facts.current_daily.points[0].order_count += 1; },
    x => { x.facts.current_daily.points[0].date = '2026-02-30'; },
    x => { x.facts.current_daily.timezone = 'UTC'; },
    x => { x.facts.current_daily.grain = 'MONTH'; },
    x => { x.facts.current_daily.status = 'UNSUPPORTED_RANGE'; },
    x => { x.facts.current_daily.extra = true; },
  ]) {
    const invalid = structuredClone(dailyCases.unknown); change(invalid);
    assert.equal(decodeCompetitionResultRef(invalid), null);
  }
});

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

// ---------------------------------------------------------------------------
// Reconciliation under float rounding (review R1). Mirrors the backend cases in
// backend/tests/test_competition_computed_results.py on the same numbers so the two
// languages accept and reject the same documents.
// ---------------------------------------------------------------------------

const REVIEW_CURRENT_CHANNELS = [65728804463.2438, 55574578714.0255, 92978413517.0508, 66808821249.1391];
const REVIEW_COMPARISON_CHANNELS = [65728804463.6639, 55574578714.7121, 92978413517.3764, 66808821248.2815];

const largeTwoPeriod = () => {
  const payload = structuredClone(funnelCases.major);
  const facts = payload.facts;
  const currentTotal = 281090617943.4592;
  const comparisonTotal = 281090617944.0339;
  facts.current = { ...facts.current, gsv: currentTotal, order_count: 4, customer_count: 4 };
  facts.comparison = { ...facts.comparison, gsv: comparisonTotal, order_count: 4, customer_count: 4 };
  facts.difference = -0.5746;
  facts.change_ratio = (currentTotal - comparisonTotal) / comparisonTotal;
  facts.change_ratio_unavailable_reason = null;
  facts.current_daily = { ...facts.current_daily, points: facts.current_daily.points.map((point, index) => ({
    date: point.date, gsv: index === 4 ? currentTotal : 0, order_count: index === 4 ? 4 : 0 })) };
  facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'AVAILABLE', unavailable_reason: null,
    contributions: REVIEW_CURRENT_CHANNELS.map((value, index) => ({
      channel: `CH_${index}`, current_gsv: value, comparison_gsv: REVIEW_COMPARISON_CHANNELS[index],
      delta: [-0.4201, -0.6866, -0.3256, 0.8576][index] })) };
  facts.current_purchase_frequency = { ...facts.current_purchase_frequency, stages: [
    { minimum_orders: 1, customer_count: 4 }, { minimum_orders: 2, customer_count: 0 },
    { minimum_orders: 3, customer_count: 0 }] };
  return payload;
};

const sparseLargeDaily = currentTotal => {
  const payload = structuredClone(funnelCases.major);
  const facts = payload.facts;
  const comparisonTotal = 305;
  const total = Number((currentTotal - comparisonTotal).toFixed(4));
  facts.current = { ...facts.current, gsv: currentTotal, order_count: 1, customer_count: 1 };
  facts.comparison = { ...facts.comparison, gsv: comparisonTotal, order_count: 3, customer_count: 3 };
  facts.difference = total;
  facts.change_ratio = (currentTotal - comparisonTotal) / comparisonTotal;
  facts.change_ratio_unavailable_reason = null;
  facts.current_daily = { ...facts.current_daily, points: facts.current_daily.points.map((point, index) => ({
    date: point.date, gsv: index === 4 ? currentTotal : 0, order_count: index === 4 ? 1 : 0 })) };
  facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'AVAILABLE', unavailable_reason: null,
    contributions: [{ channel: 'CH_RETAIL', current_gsv: currentTotal, comparison_gsv: comparisonTotal, delta: total }] };
  facts.current_purchase_frequency = { ...facts.current_purchase_frequency, stages: [
    { minimum_orders: 1, customer_count: 1 }, { minimum_orders: 2, customer_count: 0 },
    { minimum_orders: 3, customer_count: 0 }] };
  return payload;
};

test('v5 reconciliation accepts a legitimate large two-period channel decomposition', () => {
  const payload = largeTwoPeriod();
  assert.ok(decodeCompetitionResultRef(payload), 'a result this source actually produced must decode');
  const summed = payload.facts.channel_bridge.contributions.reduce((sum, item) => sum + item.delta, 0);
  // The rounded channel differences miss the rounded total difference by one four-decimal
  // step of float representation error; that must not reject the decomposition.
  assert.equal(Number(summed.toFixed(4)), -0.5747);
  assert.notEqual(payload.facts.difference, -0.5747);
});

test('v5 reconciliation keeps sparse zero-order days and their exact total', () => {
  const payload = sparseLargeDaily(100_000_000_000);
  assert.equal(payload.facts.current_daily.points.filter(point => point.order_count).length, 1);
  assert.equal(payload.facts.current_daily.points.reduce((sum, point) => sum + point.gsv, 0),
    payload.facts.current.gsv);
  assert.ok(decodeCompetitionResultRef(payload));
});

test('v5 reconciliation rejects a daily gap larger than float representation noise', () => {
  for (const gap of [0.001, 0.0005, 0.0002]) {
    const payload = sparseLargeDaily(100_000_000_000);
    payload.facts.current_daily.points[4].gsv += gap;
    assert.equal(decodeCompetitionResultRef(payload), null, `fabricated daily gap ${gap}`);
  }
});

test('v5 reconciliation rejects a fabricated channel split that still sums to the parent', () => {
  // current_gsv and delta move together, so only the parent reconciliation can catch it.
  const payload = largeTwoPeriod();
  payload.facts.channel_bridge.contributions[0].current_gsv += 0.001;
  payload.facts.channel_bridge.contributions[0].delta += 0.001;
  assert.equal(decodeCompetitionResultRef(payload), null);
});

test('v5 reconciliation rejects compensated channel deltas that keep the total', () => {
  const payload = largeTwoPeriod();
  payload.facts.channel_bridge.contributions[0].delta += 0.00008;
  payload.facts.channel_bridge.contributions[1].delta -= 0.00008;
  assert.equal(decodeCompetitionResultRef(payload), null);
});

// Each channel difference is judged against its own subtraction, never against the
// operand-scaled budget the aggregate reconciliation needs (review R2).
const channelDeltaParity = () => {
  const payload = structuredClone(funnelCases.major);
  const facts = payload.facts;
  const currentTotal = 2_000_000_000_200;
  const comparisonTotal = 2_000_000_000_000;
  facts.current = { ...facts.current, gsv: currentTotal, order_count: 2, customer_count: 2 };
  facts.comparison = { ...facts.comparison, gsv: comparisonTotal, order_count: 2, customer_count: 2 };
  facts.difference = 200;
  facts.change_ratio = (currentTotal - comparisonTotal) / comparisonTotal;
  facts.change_ratio_unavailable_reason = null;
  facts.current_daily = { ...facts.current_daily, points: facts.current_daily.points.map((point, index) => ({
    date: point.date, gsv: index === 4 ? currentTotal : 0, order_count: index === 4 ? 2 : 0 })) };
  facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'AVAILABLE', unavailable_reason: null, contributions: [
    { channel: 'CH_0', current_gsv: 1_000_000_000_100, comparison_gsv: 1_000_000_000_000, delta: 100 },
    { channel: 'CH_1', current_gsv: 1_000_000_000_100, comparison_gsv: 1_000_000_000_000, delta: 100 }] };
  facts.current_purchase_frequency = { ...facts.current_purchase_frequency, stages: [
    { minimum_orders: 1, customer_count: 2 }, { minimum_orders: 2, customer_count: 0 },
    { minimum_orders: 3, customer_count: 0 }] };
  return payload;
};

test('v5 judges each channel difference against its own subtraction', () => {
  const legit = channelDeltaParity();
  assert.ok(decodeCompetitionResultRef(legit));
  // Every period total stays intact, so only the per-channel rule can reject these.
  for (const offset of [0.0002, 0.0001, 0.00008]) {
    const forged = structuredClone(legit);
    forged.facts.channel_bridge.contributions[0].delta = 100 + offset;
    forged.facts.channel_bridge.contributions[1].delta = 100 - offset;
    assert.equal(forged.facts.channel_bridge.contributions.reduce((sum, item) => sum + item.delta, 0), 200);
    assert.equal(decodeCompetitionResultRef(forged), null, `fabricated channel offset ${offset}`);
  }
});

const fullLeapYearDaily = () => {
  const payload = structuredClone(funnelCases.major);
  const facts = payload.facts;
  const total = 451851847.7766;
  const period = { start_date: '2024-01-01', end_date: '2024-12-31', end_bound: 'INCLUSIVE_CALENDAR_DAY' };
  const start = Date.UTC(2024, 0, 1);
  payload.resolved_condition = { ...payload.resolved_condition, current_period: period };
  facts.current = { requested_period: period, through_date: '2024-12-31', gsv: total, order_count: 366,
    customer_count: 366, customer_count_unavailable_reason: null };
  facts.difference = total - 305;
  facts.change_ratio = (total - 305) / 305;
  facts.change_ratio_unavailable_reason = null;
  facts.current_daily = { ...facts.current_daily, points: Array.from({ length: 366 }, (_, index) => ({
    date: new Date(start + index * 86400000).toISOString().slice(0, 10), gsv: 1234567.8901, order_count: 1 })) };
  facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'AVAILABLE', unavailable_reason: null, contributions: [
    { channel: 'CH_RETAIL', current_gsv: total, comparison_gsv: 305, delta: Number((total - 305).toFixed(4)) }] };
  facts.current_purchase_frequency = { ...facts.current_purchase_frequency, stages: [
    { minimum_orders: 1, customer_count: 366 }, { minimum_orders: 2, customer_count: 0 },
    { minimum_orders: 3, customer_count: 0 }] };
  return payload;
};

test('v5 accumulates a full leap year of large days without a flat tolerance', () => {
  const payload = fullLeapYearDaily();
  assert.equal(payload.facts.current_daily.points.length, 366);
  // A plain left-to-right accumulation of these 366 four-decimal days drifts off the
  // parent total by more than the reconciliation allowance, so the decoder has to sum
  // like the producer does.
  const naive = payload.facts.current_daily.points.reduce((sum, point) => sum + point.gsv, 0);
  assert.notEqual(naive, payload.facts.current.gsv);
  assert.ok(decodeCompetitionResultRef(payload));
  for (const gap of [0.001, 0.0001]) {
    const forged = fullLeapYearDaily();
    forged.facts.current_daily.points[200].gsv += gap;
    assert.equal(decodeCompetitionResultRef(forged), null, `fabricated leap-year gap ${gap}`);
  }
});

// 0.03125 is exactly representable and exactly the midpoint between the four-decimal values
// 0.0312 and 0.0313. Python rounds it to 0.0312 (ties to even) while Math.round and toFixed
// give 0.0313, so a decoder that approximates the producer's rounding, or that merely
// tolerates a neighbouring four-decimal value, accepts a delta the Python validator rejects.
const exactMidpointChannels = () => {
  const payload = structuredClone(funnelCases.major);
  const facts = payload.facts;
  const current = 1_000_000_000_000.0312, comparison = 1_000_000_000_000;
  const currentTotal = current * 2, comparisonTotal = comparison * 2;
  facts.current = { ...facts.current, gsv: currentTotal, order_count: 2, customer_count: 2 };
  facts.comparison = { ...facts.comparison, gsv: comparisonTotal, order_count: 2, customer_count: 2 };
  facts.difference = 0.0625;
  facts.change_ratio = (currentTotal - comparisonTotal) / comparisonTotal;
  facts.change_ratio_unavailable_reason = null;
  facts.current_daily = { ...facts.current_daily, points: facts.current_daily.points.map((point, index) => ({
    date: point.date, gsv: index === 4 ? currentTotal : 0, order_count: index === 4 ? 2 : 0 })) };
  facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'AVAILABLE', unavailable_reason: null, contributions: [
    { channel: 'CH_0', current_gsv: current, comparison_gsv: comparison, delta: 0.0312 },
    { channel: 'CH_1', current_gsv: current, comparison_gsv: comparison, delta: 0.0312 }] };
  facts.current_purchase_frequency = { ...facts.current_purchase_frequency, stages: [
    { minimum_orders: 1, customer_count: 2 }, { minimum_orders: 2, customer_count: 0 },
    { minimum_orders: 3, customer_count: 0 }] };
  return payload;
};

test('v5 rounds each channel difference like Python instead of accepting a neighbour', () => {
  const payload = exactMidpointChannels();
  const contributions = payload.facts.channel_bridge.contributions;
  // Sterbenz: the operands are within a factor of two, so the stored subtraction is exact.
  assert.equal(contributions[0].current_gsv - contributions[0].comparison_gsv, 0.03125);
  assert.equal(round4(0.03125), 0.0312);
  assert.equal(Number((0.03125).toFixed(4)), 0.0313, 'the naive JS rule disagrees on this tie');
  assert.ok(decodeCompetitionResultRef(payload), "the producer's own rounding must decode");
  for (const forged of [0.0313, 0.03121, 0.03119]) {
    const bad = structuredClone(payload);
    bad.facts.channel_bridge.contributions[0].delta = forged;
    bad.facts.channel_bridge.contributions[1].delta = 0.0625 - forged;
    // Every published total survives the swap, so no summation rule can catch it.
    assert.equal(bad.facts.channel_bridge.contributions.reduce((sum, item) => sum + item.delta, 0), 0.0625);
    assert.equal(decodeCompetitionResultRef(bad), null, `fabricated midpoint delta ${forged}`);
  }
});

// The decoder reproduces Python's round(x, 4) rather than approximating it, so the rounding
// itself is checked bit for bit against the interpreter the producer runs on. The corpus is
// bounded and deterministic: signed zeros, subnormals, extremes, exact four-decimal midpoints
// with both binary64 neighbours, and seeded bit patterns nobody picked by hand. The embedded
// version assertion makes a non-3.14 interpreter exit non-zero instead of silently agreeing
// with a different rounding rule.
const PYTHON_CANDIDATES = [process.env.FQ_CRM_PYTHON, 'python3.14', 'python3'].filter(Boolean);
// The repository root, resolved from this file rather than a hard-coded checkout path, so the
// oracle imports the very contract module under test instead of a copy of it.
const REPOSITORY_ROOT = fileURLToPath(new URL('../../../../../', import.meta.url));

const runPython = (script, input) => {
  let last = null;
  for (const [index, python] of PYTHON_CANDIDATES.entries()) {
    const run = spawnSync(python, ['-c', script, REPOSITORY_ROOT], { input, encoding: 'utf8',
      timeout: 30000, maxBuffer: 16 * 1024 * 1024, cwd: REPOSITORY_ROOT,
      env: { PATH: process.env.PATH, PYTHONPATH: REPOSITORY_ROOT, PYTHONNOUSERSITE: '1',
        PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1' } });
    last = run;
    if (run.error?.code === 'ENOENT' && index < PYTHON_CANDIDATES.length - 1) continue;
    break;
  }
  assert.equal(last.status, 0, `${last.error?.message ?? ''} ${last.stderr ?? ''}`.trim());
  return JSON.parse(last.stdout);
};

const ROUND4_ORACLE = String.raw`
import json, struct, sys
assert sys.version_info[:2] == (3, 14), sys.version
values = [struct.unpack('>d', bytes.fromhex(h))[0] for h in json.load(sys.stdin)]
print(json.dumps([struct.pack('>d', round(x, 4)).hex() for x in values]))
`;

test('round4 matches actual Python round(x, 4) bit for bit', () => {
  const view = new DataView(new ArrayBuffer(8));
  const bitsOf = value => { view.setFloat64(0, value); return view.getBigUint64(0); };
  const valueOf = bits => { view.setBigUint64(0, bits); return view.getFloat64(0); };
  const hex = value => bitsOf(value).toString(16).padStart(16, '0');
  const values = [0, -0, 0.03125, -0.03125, 0.03135, -0.03135, 0.0625, 100, -100, 100.00004,
    1_000_000_000_000.0312, 1_000_000_000_100, 1234567.8901, Number.MIN_VALUE, -Number.MIN_VALUE,
    Number.MAX_VALUE, -Number.MAX_VALUE];
  for (let i = -64; i <= 64; i++) {
    // The double nearest each decimal midpoint in the window, plus both of its binary64
    // neighbours. Only odd multiples of 2**-5 (0.03125, 0.09375, ...) are themselves exactly
    // representable midpoints; those are a subset here and get their tie direction checked.
    const tie = (2 * i + 1) / 20000;
    const bits = bitsOf(tie);
    values.push(tie, valueOf(bits - 1n), valueOf(bits + 1n));
  }
  // Genuine ties: x * 10000 is exactly a half-integer only when x is an odd multiple of
  // 2**-5, which is what makes the tie-break direction observable rather than incidental.
  const toward = (value, direction) => value > 0
    ? valueOf(bitsOf(value) + direction) : valueOf(bitsOf(value) - direction);
  for (let i = -129; i <= 129; i += 2) {
    const exact = i / 32;
    values.push(exact, -exact, toward(exact, 1n), toward(exact, -1n), toward(-exact, 1n), toward(-exact, -1n));
  }
  let seed = 0x2545f4914f6cdd1dn;
  const mask = (1n << 64n) - 1n;
  for (let i = 0; i < 2048; i++) {
    seed = (seed * 6364136223846793005n + 1442695040888963407n) & mask;
    const value = valueOf(seed);
    if (Number.isFinite(value)) values.push(value);
  }
  const oracle = runPython(ROUND4_ORACLE, JSON.stringify(values.map(hex)));
  assert.equal(oracle.length, values.length);
  const mismatches = [];
  for (const [index, value] of values.entries()) {
    if (hex(round4(value)) !== oracle[index]) {
      mismatches.push({ input: hex(value), decoder: hex(round4(value)), python: oracle[index] });
    }
  }
  assert.deepEqual(mismatches, [], 'round4 must equal Python round(x, 4) for every sampled value');
  assert.equal(round4(-0.03125), -0.0312);
});

// The period difference travels the same contract rule as each channel difference -
// Python requires difference == round(current - comparison, 4) - but the decoder used a
// whole-period window of 0.00011 instead, which accepts a neighbouring four-decimal value.
// Every schema version shares that line, so the regression runs against the real contract
// model for v1..v5 rather than a hand-written expectation.
const DIFFERENCE_ORACLE = String.raw`
import json, sys
from pydantic import ValidationError
sys.path.insert(0, sys.argv[1])
from backend.contracts.competition_computed import (CompetitionGsvFacts, CompetitionGsvFactsV2,
    CompetitionGsvFactsV3, CompetitionGsvFactsV4, CompetitionGsvFactsV5)
MODELS = {'v1': CompetitionGsvFacts, 'v2': CompetitionGsvFactsV2, 'v3': CompetitionGsvFactsV3,
          'v4': CompetitionGsvFactsV4, 'v5': CompetitionGsvFactsV5}
out = {}
for case in json.load(sys.stdin):
    try:
        MODELS[case['version']].model_validate(case['payload']['facts'])
        out[case['name']] = True
    except ValidationError:
        out[case['name']] = False
print(json.dumps(out))
`;

const differenceCases = () => {
  const fixtures = { v1: result, v2: unitCases.major, v3: dailyCases.major,
    v4: waterfallCases.major, v5: funnelCases.major };
  const cases = [];
  const add = (name, version, payload) => cases.push({ name, version, payload });
  const mutate = (base, change) => { const copy = structuredClone(base); change(copy); return copy; };
  const singleDay = (facts, total, orders) => {
    if (facts.current_daily) facts.current_daily = { ...facts.current_daily, points: facts.current_daily.points.map((point, index) => ({
      date: point.date, gsv: index === 4 ? total : 0, order_count: index === 4 ? orders : 0 })) };
  };
  const funnel = (facts, count) => {
    if (facts.current_purchase_frequency) facts.current_purchase_frequency = { ...facts.current_purchase_frequency,
      status: 'AVAILABLE', unavailable_reason: null, stages: [{ minimum_orders: 1, customer_count: count },
        { minimum_orders: 2, customer_count: 0 }, { minimum_orders: 3, customer_count: 0 }] };
  };
  for (const [version, fixture] of Object.entries(fixtures)) {
    const difference = fixture.facts.difference;
    add(`L_legal_${version}`, version, fixture);
    add(`F_plus_${version}`, version, mutate(fixture, x => { x.facts.difference = difference + 0.0001; }));
    add(`F_minus_${version}`, version, mutate(fixture, x => { x.facts.difference = difference - 0.0001; }));
    add(`F_tiny_${version}`, version, mutate(fixture, x => { x.facts.difference = difference + 0.00004; }));
    add(`F_null_${version}`, version, mutate(fixture, x => { x.facts.difference = null; }));
  }
  // A zero comparison period makes the honest difference round(100.00004, 4) == 100 while the
  // raw subtraction is 100.00004 itself, so a distance window passes the forgery for free.
  for (const version of Object.keys(fixtures)) {
    const build = forged => {
      const payload = structuredClone(fixtures[version]);
      const facts = payload.facts;
      Object.assign(facts.current, { gsv: 100.00004, order_count: 1, customer_count: 1 });
      Object.assign(facts.comparison, { gsv: 0, order_count: 0, customer_count: 0 });
      facts.difference = forged ? 100.00004 : 100;
      facts.change_ratio = null;
      facts.change_ratio_unavailable_reason = 'ZERO_COMPARISON_GSV';
      singleDay(facts, 100.00004, 1);
      if (facts.channel_bridge) facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'AVAILABLE',
        unavailable_reason: null, contributions: [{ channel: 'CH_RETAIL', current_gsv: 100.00004,
          comparison_gsv: 0, delta: 100 }] };
      funnel(facts, 1);
      return payload;
    };
    add(`Z_zero_legit_${version}`, version, build(false));
    add(`Z_zero_forged_${version}`, version, build(true));
  }
  // Exact midpoint: 0.03125 is exactly representable, so Python rounds it to 0.0312 (ties to
  // even) and 0.0626 - one published step away - must not pass as the period difference.
  for (const version of Object.keys(fixtures)) {
    const build = difference => {
      const payload = structuredClone(fixtures[version]);
      const facts = payload.facts;
      const current = 1_000_000_000_000.0312, comparison = 1_000_000_000_000;
      Object.assign(facts.current, { gsv: current * 2, order_count: 2, customer_count: 2 });
      Object.assign(facts.comparison, { gsv: comparison * 2, order_count: 2, customer_count: 2 });
      facts.difference = difference;
      facts.change_ratio = (current - comparison) / comparison;
      facts.change_ratio_unavailable_reason = null;
      singleDay(facts, current * 2, 2);
      if (facts.channel_bridge) facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'AVAILABLE',
        unavailable_reason: null, contributions: [
          { channel: 'CH_0', current_gsv: current, comparison_gsv: comparison, delta: 0.0312 },
          { channel: 'CH_1', current_gsv: current, comparison_gsv: comparison, delta: 0.0312 }] };
      funnel(facts, 2);
      return payload;
    };
    add(`M_midpoint_legit_${version}`, version, build(0.0625));
    add(`M_midpoint_forged_${version}`, version, build(0.0626));
  }
  // An unavailable calendar period publishes no difference at all, and that pre-check must
  // survive the tightening.
  for (const version of Object.keys(fixtures)) {
    const build = change => {
      const payload = structuredClone(fixtures[version]);
      const facts = payload.facts;
      Object.assign(facts.current, { through_date: null, gsv: null, order_count: 0, customer_count: 0 });
      facts.difference = null;
      facts.change_ratio = null;
      facts.change_ratio_unavailable_reason = 'PERIOD_UNAVAILABLE';
      if (facts.current_daily) facts.current_daily = { ...facts.current_daily, status: 'AVAILABLE',
        unavailable_reason: null, points: facts.current_daily.points.map(point => ({ date: point.date, gsv: null, order_count: 0 })) };
      if (facts.channel_bridge) facts.channel_bridge = { dimension: 'SALES_CHANNEL', status: 'UNAVAILABLE',
        unavailable_reason: 'PERIOD_UNAVAILABLE', contributions: [] };
      if (facts.current_purchase_frequency) facts.current_purchase_frequency = { ...facts.current_purchase_frequency,
        status: 'UNAVAILABLE', unavailable_reason: 'PERIOD_UNAVAILABLE', stages: [] };
      payload.completeness = 'EMPTY'; payload.row_count = 0; payload.page = null;
      payload.empty_reason = 'NO_CURRENT_MONTH_DATA';
      change(payload);
      return payload;
    };
    add(`E_unavailable_legit_${version}`, version, build(() => {}));
    add(`E_unavailable_forged_${version}`, version, build(payload => { payload.facts.difference = 105; }));
  }
  return cases;
};

test('v1-v5 judge the period difference by the same four-decimal rounding as its subtraction', () => {
  const cases = differenceCases();
  const oracle = runPython(DIFFERENCE_ORACLE, JSON.stringify(cases));
  const mismatches = [];
  let rejected = 0;
  for (const item of cases) {
    const python = oracle[item.name];
    const decoder = decodeCompetitionResultRef(item.payload) !== null;
    if (!python) rejected++;
    if (decoder !== python) mismatches.push(`${item.name}: python=${python} decoder=${decoder}`);
  }
  // A case whose untouched shape is not itself contract-valid would only prove that two
  // validators agree on garbage, so the accepted cases are what license the rejected ones.
  assert.deepEqual(mismatches, []);
  assert.equal(cases.length - rejected, 20, 'the constructed legitimate payloads must be accepted');
  assert.ok(rejected >= 25, 'the forged payloads must be rejected');
});
