import test from 'node:test';
import assert from 'node:assert/strict';
import { proposeAsk, proposeAskLocal, titleFromAsk } from './ask.mjs';
import { confirmPatch, createCanvasState, selectBlock, setAsk } from './canvas-state.mjs';
import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from './fixture.mjs';

function selectedAsk(ask) {
  let state = createCanvasState(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS).value;
  state = selectBlock(state, 'b3').value;
  return setAsk(state, ask).value;
}

test('titleFromAsk reads quoted 本月渠道占比', () => {
  assert.equal(titleFromAsk('把标题改成「本月渠道占比」'), '本月渠道占比');
});

test('proposeAskLocal stages set_title and does not write version', () => {
  const got = proposeAskLocal(selectedAsk('本月渠道占比'));
  assert.equal(got.ok, true);
  assert.equal(got.value.spec.version, 1);
  assert.equal(got.value.pending_patch.op, 'set_title');
  assert.equal(got.value.pending_patch.title, '本月渠道占比');
});

test('proposeAskLocal set_metric_ref from 换成零售 GSV', () => {
  const got = proposeAskLocal(selectedAsk('口径换成零售 GSV'));
  assert.equal(got.ok, true);
  assert.equal(got.value.pending_patch.op, 'set_metric_ref');
  assert.equal(got.value.pending_patch.metric_ref, 'retail_gsv');
  assert.equal(got.value.spec.version, 1);
});

test('proposeAskLocal refuses facts questions and does not invent numbers', () => {
  const got = proposeAskLocal(selectedAsk('本月 GSV 是多少'));
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'ASK_FACTS');
});

test('proposeAsk refreshes only the selected block facts from results', async () => {
  const got = await proposeAsk(selectedAsk('本月 GSV 是多少'), {
    fetchImpl: async () => Response.json({
      items: [{
        result_id: 'r1',
        facts: { current: { gsv: 410 }, comparison: { gsv: 305 }, difference: 105 },
      }],
    }),
    resultsPath: '/api/v1/analytics/competition/results',
  });
  assert.equal(got.ok, true);
  assert.equal(got.refreshed, true);
  assert.equal(got.value.pending_patch, null);
  assert.equal(got.value.spec.version, 1);
  assert.equal(got.value.facts.r1.current_gsv, 410);
});

test('proposeAskLocal set_layout from 布局 0 0 6 4', () => {
  const got = proposeAskLocal(selectedAsk('布局 0 0 6 4'));
  assert.equal(got.ok, true);
  assert.equal(got.value.pending_patch.op, 'set_layout');
  assert.deepEqual(got.value.pending_patch.layout, { x: 0, y: 0, w: 6, h: 4 });
});

test('proposeAsk HTTP patch for another block is refused', async () => {
  const got = await proposeAsk(selectedAsk('本月渠道占比'), {
    fetchImpl: async () => Response.json({
      patch: { block_id: 'b1', base_version: 1, op: 'set_title', title: '偷改' },
    }),
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'ASK_BLOCK');
});

test('proposeAskLocal set_kind LINE from 加一块折线', () => {
  const got = proposeAskLocal(selectedAsk('加一块折线'));
  assert.equal(got.ok, true);
  assert.equal(got.value.pending_patch.op, 'set_kind');
  assert.equal(got.value.pending_patch.kind, 'LINE');
  assert.equal(got.value.spec.version, 1);
});

test('proposeAsk HTTP 500 is fail-closed and does not write', async () => {
  const got = await proposeAsk(selectedAsk('本月渠道占比'), {
    fetchImpl: async () => new Response('no', { status: 500 }),
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'ASK_HTTP');
});

test('proposeAsk HTTP illegal patch is refused', async () => {
  const got = await proposeAsk(selectedAsk('本月渠道占比'), {
    fetchImpl: async () => Response.json({ op: 'invent_sql', block_id: 'b3', base_version: 1 }),
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'ASK_PATCH');
});

test('proposeAsk HTTP legal PATCH is pending until confirmPatch', async () => {
  const staged = await proposeAsk(selectedAsk('本月渠道占比'), {
    fetchImpl: async () => Response.json({
      patch: { block_id: 'b3', base_version: 1, op: 'set_title', title: '本月渠道占比' },
    }),
  });
  assert.equal(staged.ok, true);
  assert.equal(staged.value.spec.version, 1);
  const written = confirmPatch(staged.value);
  assert.equal(written.value.spec.version, 2);
  assert.equal(written.value.spec.blocks.find((b) => b.block_id === 'b3').title, '本月渠道占比');
});
