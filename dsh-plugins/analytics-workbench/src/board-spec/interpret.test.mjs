import test from 'node:test';
import assert from 'node:assert/strict';
import { interpretBoard } from './interpret.mjs';
import { applyPatch } from './schema.mjs';
import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from './fixture.mjs';

test('interpretBoard paints METRIC/BAR/LINE from bound facts without inventing numbers', () => {
  const got = interpretBoard(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  assert.equal(got.ok, true);
  const metric = got.value.blocks.find((b) => b.block_id === 'b1');
  assert.equal(metric.bind, 'bound');
  assert.equal(metric.paint.headline, 400);
  const bar = got.value.blocks.find((b) => b.block_id === 'b2');
  assert.deepEqual(bar.paint.series, [
    { label: '对比期', value: 300 },
    { label: '本期', value: 400 },
  ]);
  const line = got.value.blocks.find((b) => b.block_id === 'b3');
  assert.equal(line.paint.series[1].value, 400);
});

test('interpretBoard TABLE copies facts only', () => {
  const got = interpretBoard(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  const table = got.value.blocks.find((b) => b.block_id === 'b4');
  assert.equal(table.paint.rows[0].value, 400);
  assert.equal(table.paint.rows[2].value, 100);
});

test('interpretBoard EVIDENCE passes chips', () => {
  const got = interpretBoard(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  const ev = got.value.blocks.find((b) => b.block_id === 'b5');
  assert.deepEqual(ev.paint.chips, ['digest', '期间', '筛选']);
});

test('interpretBoard html_sandbox does not execute or echo markup', () => {
  const dirty = {
    ...BOARD_SPEC_FIXTURE,
    blocks: [{
      block_id: 'h1',
      kind: 'html_sandbox',
      title: 'x',
      html: '<script>window.parent.steal()</script>',
    }],
  };
  const got = interpretBoard(dirty, {});
  assert.equal(got.ok, true);
  assert.equal(got.value.blocks[0].paint.sandbox, true);
  assert.equal(got.value.blocks[0].paint.parent_dom, false);
  assert.equal(got.value.blocks[0].paint.model_sql, false);
  assert.equal('html' in got.value.blocks[0].paint, false);
});

test('interpretBoard LINK exposes url only', () => {
  const got = interpretBoard(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  const link = got.value.blocks.find((b) => b.block_id === 'b7');
  assert.equal(link.paint.url, 'https://example.invalid/feishu/doc/channel');
});

test('missing source_result_id is unbound and has no headline 0', () => {
  const spec = {
    board_id: 'b',
    version: 1,
    blocks: [{ block_id: 'm', kind: 'METRIC', title: 'x' }],
  };
  const got = interpretBoard(spec, BOARD_SPEC_FACTS);
  assert.equal(got.value.blocks[0].bind, 'unbound');
  assert.equal(got.value.blocks[0].paint.headline, null);
});

test('unknown result id is missing_result not a fabricated 0%', () => {
  const spec = {
    board_id: 'b',
    version: 1,
    blocks: [{ block_id: 'm', kind: 'METRIC', title: 'x', source_result_id: 'nope' }],
  };
  const got = interpretBoard(spec, BOARD_SPEC_FACTS);
  assert.equal(got.value.blocks[0].bind, 'missing_result');
  assert.equal(got.value.blocks[0].paint.headline, null);
});

test('invalid spec is not interpreted', () => {
  const got = interpretBoard({ board_id: 'b', version: 1, blocks: [{ block_id: 'z', kind: 'PIE' }] });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'SPEC_KIND');
});

test('applyPatch then interpret shows new title still bound to r1', () => {
  const patched = applyPatch(BOARD_SPEC_FIXTURE, {
    block_id: 'b3',
    base_version: 1,
    op: 'set_title',
    title: '本月渠道占比',
  });
  assert.equal(patched.ok, true);
  const got = interpretBoard(patched.value, BOARD_SPEC_FACTS);
  const line = got.value.blocks.find((b) => b.block_id === 'b3');
  assert.equal(line.title, '本月渠道占比');
  assert.equal(line.source_result_id, 'r1');
  assert.equal(line.paint.series[1].value, 400);
});
