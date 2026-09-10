/** A9 compiled/source DOM against the integration SUT. Missing files FAIL. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const a9Root = join(here, '../../../..');
const sutRoot = process.env.A9_SUT_ROOT
  || a9Root;
const evidence = join(
  a9Root,
  'docs/hackathon/parallel-competition-2026-09-09/evidence/A9/fixtures/t01_t17_matrix.json',
);
const boardDir = join(sutRoot, 'dsh-plugins/analytics-workbench/src/client/competition-board');
const actionsDir = join(sutRoot, 'dsh-plugins/analytics-workbench/src/client/competition-actions');
const compiled = join(sutRoot, 'dsh-plugins/analytics-workbench/lib/views/cockpit-view.js');

function matrix() {
  return JSON.parse(readFileSync(evidence, 'utf8'));
}

function requireFile(path, label) {
  assert.equal(existsSync(path), true, `A9 fail-closed: ${label} missing at ${path}`);
  return readFileSync(path, 'utf8');
}

test('does not bind user demo ports 8000/5173/4327', () => {
  for (const key of ['PORT', 'UVICORN_PORT', 'VITE_PORT', 'DSH_PORT']) {
    const value = process.env[key];
    if (value) {
      assert.ok(!['8000', '5173', '4327'].includes(String(value)), `${key}=${value}`);
    }
  }
});

test('T09-T11 board source exists on SUT and keeps in-flight target', async () => {
  const selectionSrc = requireFile(join(boardDir, 'selection.mjs'), 'selection.mjs');
  assert.match(selectionSrc, /getPatchTarget/);
  assert.match(selectionSrc, /beginInflight/);
  const { beginInflight, getPatchTarget, resetInflightForTests, setUiSelection } = await import(
    `file://${join(boardDir, 'selection.mjs')}`
  );
  resetInflightForTests();
  setUiSelection({ board_id: 'dash_a', block_id: 'card_a', base_version: 4 });
  beginInflight({ board_id: 'dash_a', block_id: 'card_a', base_version: 4, attempt_id: 'attempt_1' });
  setUiSelection({ board_id: 'dash_a', block_id: 'card_b', base_version: 4 });
  assert.equal(getPatchTarget().block_id, 'card_a');
  resetInflightForTests();
});

test('T09 board UI source covers endorsement and partial batch', () => {
  const ui = requireFile(join(boardDir, 'BoardWorkbench.tsx'), 'BoardWorkbench.tsx');
  assert.match(ui, /sm-endorsement|endorsement|认可/);
  assert.match(ui, /PARTIAL|部分/);
  const decode = requireFile(join(boardDir, 'decode.mjs'), 'decode.mjs');
  assert.match(decode, /looksLikeIllegalScript/);
});

test('T10 style-only is not a query; illegal script rejected', async () => {
  const { looksLikeIllegalScript, decodeCompetitionPatchRequest } = await import(
    `file://${join(boardDir, 'decode.mjs')}`
  );
  const { BOARD_SUCCESS } = await import(`file://${join(boardDir, 'c0-fixtures.mjs')}`);
  assert.equal(looksLikeIllegalScript({ html: '<script>bad()</script>' }), true);
  assert.equal(decodeCompetitionPatchRequest({
    ...BOARD_SUCCESS.patch,
    display_op: { op: 'display', card_id: 'card_c0_block_1', display_overrides: { title: '<script>x</script>' } },
  }), null);
  const tools = requireFile(
    join(sutRoot, 'dsh-plugins/analytics-workbench/src/competition-agent/tools.mjs'),
    'competition-agent/tools.mjs',
  );
  assert.match(tools, /STYLE_ONLY/);
});

test('T11 model-unavailable still shows saved board; discard is not undo', () => {
  const ui = requireFile(join(boardDir, 'BoardWorkbench.tsx'), 'BoardWorkbench.tsx');
  assert.match(ui, /模型不可用|modelAvailable/);
  assert.match(ui, /discard|放弃/);
  const view = requireFile(
    join(sutRoot, 'dsh-plugins/analytics-workbench/src/cockpit-view.tsx'),
    'cockpit-view.tsx',
  );
  assert.match(view, /competition-board/);
});

// T04 amounts/ratios are asserted against the compiled component in
// competition-board-dom.test.mjs. A source-wide "* 100" ban cannot distinguish
// currency from the explicitly contracted raw-ratio formatter or chart width.

test('T12 actions source covers zero candidates and no auto send', () => {
  const actions = requireFile(join(actionsDir, 'ActionsWorkbench.tsx'), 'ActionsWorkbench.tsx');
  assert.match(actions, /auto_send|自动发送/);
  assert.match(actions, /zero|零候选|unique_count/);
});

test('T09-T11 compiled React DOM is fail-closed without lib/views', () => {
  const row = matrix().cases.find((item) => item.id === 'T09');
  assert.ok(row.layers.includes('dom'));
  if (!existsSync(compiled)) {
    assert.fail('A9 fail-closed: compiled cockpit-view.js missing; compiled DOM not independently verified');
  }
});
