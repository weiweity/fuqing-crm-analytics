import test from 'node:test';
import assert from 'node:assert/strict';
import { DEMO_BOARD, DEMO_BOARD_FACTS, DEMO_BOARD_SPEC } from './demo-board.mjs';
import { parseBoardSpec } from './schema.mjs';
import { interpretBoard } from './interpret.mjs';
import { refreshFacts } from './refresh.mjs';
import { generateBoard } from './generate.mjs';

test('demo board is a valid BoardSpec that the cockpit store accepts', () => {
  const parsed = parseBoardSpec(DEMO_BOARD_SPEC);
  assert.equal(parsed.ok, true);
  const generated = generateBoard(DEMO_BOARD.spec, DEMO_BOARD.facts);
  assert.equal(generated.ok, true);
  assert.equal(generated.value.spec, DEMO_BOARD_SPEC);
});

test('every demo block is either bound to frozen facts or self-describing', () => {
  const view = interpretBoard(DEMO_BOARD_SPEC, DEMO_BOARD_FACTS);
  assert.equal(view.ok, true);
  const blocks = view.value.blocks;
  assert.ok(blocks.length >= 6);
  const free = new Set(['LINK', 'EVIDENCE']);
  for (const block of blocks) {
    if (free.has(block.kind)) continue;
    assert.equal(block.bind, 'bound', `${block.block_id} (${block.kind}) must bind a result`);
    assert.equal(block.source_result_id in DEMO_BOARD_FACTS, true);
  }
  const metric = blocks.find(block => block.kind === 'METRIC');
  assert.equal(metric.paint.headline, 180);
});

test('demo numbers are labelled synthetic and never invent decimals on refresh', () => {
  const titles = DEMO_BOARD_SPEC.blocks.filter(block => block.kind === 'METRIC').map(block => block.title);
  assert.ok(titles.every(title => title.includes('样例')));
  const evidence = DEMO_BOARD_SPEC.blocks.find(block => block.kind === 'EVIDENCE');
  assert.ok(evidence.chips.includes('SYNTHETIC'));
  const refreshed = refreshFacts(DEMO_BOARD_SPEC, DEMO_BOARD_FACTS);
  assert.equal(refreshed.ok, true);
  assert.deepEqual(refreshed.value, {
    demo_live: { current_gsv: 180, comparison_gsv: 150, difference: 30, change_ratio: 0.2 },
    demo_private: { current_gsv: 96, comparison_gsv: 84, difference: 12, change_ratio: 1 / 7 },
    demo_store: { current_gsv: 124, comparison_gsv: 126, difference: -2, change_ratio: -2 / 126 },
  });
  const unknown = refreshFacts(DEMO_BOARD_SPEC, {});
  assert.deepEqual(unknown.value, {});
});
