import test from 'node:test';
import assert from 'node:assert/strict';
import { interpretBoard } from './interpret.mjs';
import { refreshFacts, refreshFactsFromTransport } from './refresh.mjs';
import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from './fixture.mjs';

test('refreshFacts rebinds r1 400 from the catalog', () => {
  const got = refreshFacts(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  assert.equal(got.ok, true);
  assert.equal(got.value.r1.current_gsv, 400);
  const view = interpretBoard(BOARD_SPEC_FIXTURE, got.value);
  const metric = view.value.blocks.find((b) => b.block_id === 'b1');
  assert.equal(metric.paint.headline, 400);
});

test('refreshFacts with a new catalog value updates the headline', () => {
  const got = refreshFacts(BOARD_SPEC_FIXTURE, {
    r1: { current_gsv: 450, comparison_gsv: 300, difference: 150, change_ratio: 0.5 },
  });
  const view = interpretBoard(BOARD_SPEC_FIXTURE, got.value);
  assert.equal(view.value.blocks.find((b) => b.block_id === 'b1').paint.headline, 450);
});

test('refreshFacts omits missing ids so interpret stays unbound not 0%', () => {
  const got = refreshFacts(BOARD_SPEC_FIXTURE, {});
  assert.equal(got.ok, true);
  assert.equal(got.value.r1, undefined);
  const view = interpretBoard(BOARD_SPEC_FIXTURE, got.value);
  const metric = view.value.blocks.find((b) => b.block_id === 'b1');
  assert.equal(metric.bind, 'missing_result');
  assert.equal(metric.paint.headline, null);
});

test('refreshFactsFromTransport HTTP 500 does not invent numbers', async () => {
  const got = await refreshFactsFromTransport(BOARD_SPEC_FIXTURE, {
    fetchImpl: async () => new Response('no', { status: 500 }),
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'FACTS_HTTP');
});
