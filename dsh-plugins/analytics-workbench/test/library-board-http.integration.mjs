/** Explicit full-backend integration; needs built plugin and Python 3.14 with CRM import closure.
 * Real tool SDK + native authenticated RPC + FastAPI + SQLite. No model/browser claim.
 * Kept separate from minimal B0 source discovery, which runs before plugin build.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';
import { mountNativeBoardBridge } from './helpers/native-board-bridge.mjs';
import { createLibraryBoardClient } from '../src/client/library-board-client.mjs';

const root = fileURLToPath(new URL('../../..', import.meta.url));
const plugin = join(root, 'dsh-plugins/analytics-workbench');

test('registered diagnosis → generate → native confirmation → layout/rollback → selected edits → reopen', { timeout: 60000 }, async t => {
  const python = process.env.FQ_B0_PYTHON ?? 'python3.14';
  const processEnv = { PATH: process.env.PATH, PYTHONPATH: root, PYTHONNOUSERSITE: '1', PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1' };
  const child = spawn(python, ['-m', 'backend.tests.library_board_http_probe', '--known-money-unit'], { cwd: root, env: processEnv, stdio: ['pipe', 'pipe', 'pipe'] });
  const terminal = new Promise(resolve => { child.once('exit', (code, signal) => resolve({ code, signal })); child.once('error', error => resolve({ error: error.message })); });
  let stderr = ''; child.stderr.on('data', data => { if (stderr.length < 10000) stderr += data; });
  t.after(async () => {
    child.stdin.end();
    const timer = setTimeout(() => child.kill('SIGTERM'), 12000);
    const result = await terminal; clearTimeout(timer);
    assert.deepEqual(result, { code: 0, signal: null }, stderr);
  });
  const lines = createInterface({ input: child.stdout });
  let readyTimer;
  const ready = await Promise.race([
    new Promise((resolve, reject) => { lines.once('line', line => { try { resolve(JSON.parse(line)); } catch (error) { reject(error); } }); }),
    terminal.then(result => { throw new Error(`synthetic HTTP stopped before ready: ${JSON.stringify(result)} ${stderr}`); }),
    new Promise((_, reject) => { readyTimer = setTimeout(() => reject(new Error('synthetic HTTP readiness deadline')), 15000); }),
  ]).finally(() => { clearTimeout(readyTimer); lines.close(); });
  assert.equal(ready.contains_real_data, false);
  const keys = ['COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN', 'B0_RUNTIME_FAMILY'];
  const previous = keys.map(key => [key, process.env[key]]);
  t.after(() => previous.forEach(([key, value]) => { if (value === undefined) delete process.env[key]; else process.env[key] = value; }));
  process.env.COMPETITION_HTTP_BASE = `http://127.0.0.1:${ready.port}`;
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-native-board-integration-token';
  process.env.B0_RUNTIME_FAMILY = 'competition_growth';
  const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(root, '.context/dsh-b0/upstream'));
  const load = path => import(pathToFileURL(join(upstream, path, 'lib/index.js')).href);
  const { Context } = await load('vendor/cordis');
  const { mountAgentLoopTestDependencies } = await load('packages/test-support/agent-loop-testkit');
  const { default: SkillRegistry } = await load('packages/skill/skill');
  const ctx = new Context(); t.after(() => ctx.fiber.dispose());
  await mountAgentLoopTestDependencies(ctx); await ctx.plugin(SkillRegistry);
  const built = await import(pathToFileURL(join(plugin, 'lib/skills.js')).href);
  await ctx.plugin(built);
  const agents = new Map(), outcomes = []; let callNumber = 0;
  const execute = async (name, args, session = 'native_session') => {
    if (!agents.has(session)) agents.set(session, { session: { id: session } });
    const outcome = await ctx.tools.execute({ name, arguments: args, agent: agents.get(session),
      callId: `integration_call_${++callNumber}`, signal: new AbortController().signal });
    assert.equal(outcome.isError, false, JSON.stringify(outcome)); outcomes.push(outcome);
    return outcome.value;
  };
  const empty = await execute('competition_board_catalog', {}); assert.deepEqual(empty.results, []);
  const computation = await execute('competition_growth_step', { request_id: 'integration_query', capability_id: 'diag.gsv', condition_mode: 'EXPLICIT',
    condition: { metric_type: 'GSV', timezone: 'Asia/Shanghai',
      current_period: { start_date: '2026-08-01', end_date: '2026-08-31', end_bound: 'INCLUSIVE_CALENDAR_DAY' },
      comparison_period: { start_date: '2025-08-01', end_date: '2025-08-31', end_bound: 'INCLUSIVE_CALENDAR_DAY' },
      comparison_mode: 'YOY_SAME_PERIOD', sales_scope: { kind: 'ALL' }, history_scope: { kind: 'ALL' },
      sample_mode: 'INCLUDE', sample_channel_ids: null } });
  assert.equal(computation.execution_mode, 'COMPUTED_SYNTHETIC');
  const catalogue = await execute('competition_board_catalog', {});
  assert.equal(catalogue.results.length, 1);
  const resultId = catalogue.results[0].result_id;
  assert.notEqual(resultId, catalogue.results[0].run_id);
  assert.deepEqual((await execute('competition_board_catalog', {}, 'other_session')).results, []);
  assert.ok(catalogue.results[0].supported_components.includes('LINE'));
  assert.ok(catalogue.results[0].supported_components.includes('WATERFALL'));
  assert.ok(catalogue.results[0].supported_components.includes('FUNNEL'));
  const initialProps = {
    TEXT: { content: '说明不是核验事实' },
    PROCESS: { nodes: [{ id: 'review', label: '核对', owner: '分析师', detail: '' }, { id: 'accept', label: '确认', owner: '', detail: '' }],
      edges: [{ from: 'review', to: 'accept', label: '通过' }] },
    TIMELINE: { events: [{ id: 'meeting', date: '2026-09-13', label: '讨论', detail: '' }] },
  };
  const blocks = catalogue.catalog.components.map(({ kind, ...definition }, index) => ({
    block_id: `block_${kind}`, kind, title: `合成 ${kind}`, library_version: catalogue.catalog.library_version,
    ...(definition.requires_result ? { source_result_id: resultId } : {}), props: initialProps[kind] ?? {},
    layout: { x: 0, y: index * 10, ...definition.default_size },
  }));
  // R-1: reproduce the two historical payload defects, preserving FUNNEL.
  const bridge = await mountNativeBoardBridge(); t.after(() => bridge.close());
  const readOrCancel = async (operation, payload = {}) => {
    const reply = await bridge.call('/shine-mage-board', operation, payload);
    assert.equal(reply.ok, true, JSON.stringify(reply));
    return reply.value;
  };
  const tableArgs = { title: 'R-1 属性', blocks: [structuredClone(blocks.find(block => block.kind === 'TABLE'))] };
  tableArgs.blocks[0].props.show_values = true;
  const invalid = await execute('competition_board_generate', tableArgs, 'r1_refused');
  assert.equal(invalid.error.code, 'COMPONENT_PROPERTY');
  assert.match(invalid.error.message, /TABLE.*show_values/);
  assert.equal(invalid.error.details.phase, 'preflight');
  // Exercise the registered SDK guard, with a harmless counter as the shell.
  const { defineTool } = await load('packages/core/tools');
  let shellExecutions = 0;
  ctx.tools.register(defineTool({ name: 'bash', description: 'Isolated counter; never runs a command.', parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: () => [{ type: 'text', text: 'isolated counter' }] },
    execute: async () => { shellExecutions++; return {}; } }));
  const blocked = await ctx.tools.execute({ name: 'bash', arguments: {}, agent: agents.get('r1_refused'),
    callId: 'r1_blocked_shell', signal: new AbortController().signal });
  assert.equal(blocked.isError, true); assert.match(JSON.stringify(blocked), /method boundary/);
  assert.equal(shellExecutions, 0);
  await execute('bash', {}, 'ordinary_native_turn'); assert.equal(shellExecutions, 1);
  const geometry = { LINE: { x: 6, y: 4, w: 6, h: 7 }, FUNNEL: { x: 0, y: 10, w: 6, h: 6 }, TABLE: { x: 6, y: 10, w: 6, h: 6 } };
  const overlapArgs = { title: 'R-1 布局', blocks: Object.entries(geometry).map(([kind, layout]) => ({
    ...structuredClone(blocks.find(block => block.kind === kind)), layout,
  })) };
  const overlapResult = await execute('competition_board_generate', overlapArgs);
  assert.equal(overlapResult.error.code, 'COMPONENT_OVERLAP');
  assert.match(overlapResult.error.message, /blocks\[2\].*blocks\[0\]/);
  const rawPreview = async args => fetch(`${process.env.COMPETITION_HTTP_BASE}/api/v1/analytics/board-spec/previews`, {
    method: 'POST', headers: { authorization: `Bearer ${process.env.COMPETITION_HTTP_TOKEN}`, 'content-type': 'application/json' },
    body: JSON.stringify({ ...args, session_id: 'native_session' }),
  });
  for (const args of [tableArgs, overlapArgs]) {
    const response = await rawPreview(args);
    assert.equal(response.status, 422, 'backend must still reject the original invalid payload');
    await response.json();
  }
  delete tableArgs.blocks[0].props.show_values;
  overlapArgs.blocks[2].layout.y = 11;
  for (const args of [tableArgs, overlapArgs]) {
    const result = await execute('competition_board_generate', args);
    assert.equal(result.status, 'PREVIEW_READY'); assert.equal(result.published, false);
    const pending = await readOrCancel('preview', { preview_id: result.preview_id });
    assert.equal(pending.status, 'PENDING');
    assert.deepEqual(pending.snapshot.spec.blocks.map(block => block.kind), args.blocks.map(block => block.kind));
    if (args === overlapArgs) assert.equal(pending.snapshot.facts_by_result_id[resultId].funnel.stages.length, 3);
    await readOrCancel('cancel', { preview_id: result.preview_id });
  }
  assert.deepEqual((await readOrCancel('list')).items, [], 'invalid and cancelled drafts never become saved heads');
  assert.equal((await execute('competition_board_catalog', {})).results.length, 1, 'configuration recovery reuses the same computed result');
  const draft = await execute('competition_board_generate', { title: '真实链路合成看板', blocks });
  assert.equal(draft.status, 'PREVIEW_READY'); assert.equal(draft.published, false);
  assert.deepEqual(outcomes.at(-1).meta, draft, 'real native dispatch must project canonical preview to tool-card metadata');
  const editRequests = [];
  const ui = createLibraryBoardClient(bridge.call, { editNative: async context => { editRequests.push(context); } }); t.after(() => ui.dispose());
  await ui.refresh(); assert.deepEqual(ui.getSnapshot().boards, []);
  await ui.openPreview(draft.preview_id); assert.equal(ui.getSnapshot().preview?.preview_id, draft.preview_id);
  await ui.confirm();
  const v1 = ui.getSnapshot().saved; assert.ok(v1, ui.getSnapshot().message);
  assert.equal(v1.spec.version, 1); assert.equal(v1.spec.blocks.length, catalogue.catalog.components.length);
  assert.equal(v1.facts_by_result_id[resultId].scalar.value, 140);
  assert.equal(v1.facts_by_result_id[resultId].scalar.unit, 'CNY 元');
  assert.deepEqual(v1.facts_by_result_id[resultId].waterfall, { unit: 'CNY 元',
    start: { label: '对比期 GSV', value: 135 }, end: { label: '本期 GSV', value: 140 },
    contributions: [{ label: 'CH_RETAIL', value: 0 }, { label: 'CH_SAMPLE', value: 5 }] });
  assert.equal(v1.facts_by_result_id[resultId].series.ordered, false, 'BAR remains a dual-window comparison');
  const daily = v1.facts_by_result_id[resultId].time_series;
  assert.equal(daily.ordered, true); assert.equal(daily.unit, 'CNY 元'); assert.equal(daily.points.length, 31);
  assert.equal(daily.points.reduce((total, point) => total + point.value, 0), 140);
  assert.deepEqual(daily.points[9], { label: '2026-08-10', value: 40 });
  // Real layout previews share the same server validation/confirmation path.
  ui.beginLayout(); ui.updateLayout(blocks[0].block_id, { x: 3, y: 0, w: 5, h: 5 });
  assert.deepEqual(ui.getSnapshot().saved, v1);
  await ui.previewLayout(); assert.equal(ui.getSnapshot().preview?.operation, 'LAYOUT', ui.getSnapshot().message);
  await ui.cancel();
  assert.deepEqual(ui.getSnapshot().saved, v1);
  ui.beginLayout(); ui.updateLayout(blocks[0].block_id, { x: 3, y: 0, w: 5, h: 5 });
  await ui.previewLayout(); await ui.confirm();
  const v2 = ui.getSnapshot().saved; assert.equal(v2.spec.version, 2); assert.deepEqual(v2.facts_by_result_id, v1.facts_by_result_id);
  assert.deepEqual(v2.spec.blocks[0].layout, { x: 3, y: 0, w: 5, h: 5 });
  assert.deepEqual(v2.spec.blocks.slice(1), v1.spec.blocks.slice(1));
  await ui.loadHistory(); assert.deepEqual(ui.getSnapshot().history.map(row => row.version), [2, 1]);
  await ui.rollback(1); assert.equal(ui.getSnapshot().saved.spec.version, 2); await ui.confirm();
  assert.equal(ui.getSnapshot().saved.spec.version, 3); assert.deepEqual(ui.getSnapshot().saved.spec.blocks, v1.spec.blocks);
  const reopened = createLibraryBoardClient(bridge.call); t.after(() => reopened.dispose());
  await reopened.refresh(); await reopened.openBoard(v1.spec.board_id);
  assert.deepEqual(reopened.getSnapshot().saved, ui.getSnapshot().saved);
  assert.equal((await execute('competition_board_catalog', {})).results.length, 1, 'generation/style/layout/rollback must not query again');
  const displayChanges = {
    FUNNEL: { show_values: false, show_rates: true, rate_basis: 'first' },
    WATERFALL: { show_values: false, show_table: false },
    LINE: { show_points: true, line_style: 'dashed', show_legend: false },
    METRIC: { value_format: 'compact', show_comparison: false }, BAR: { orientation: 'vertical', show_values: false },
    TABLE: { page_size: 5 }, EVIDENCE: { expanded: true, summary: '核对这份证据' }, TEXT: { content: '原生 AI 工具修改的说明', align: 'center' },
    PROCESS: { nodes: [{ id: 'review', label: '核对口径', owner: '分析师', detail: '' },
      { id: 'accept', label: '确认', owner: '老板', detail: '先预览再确认' }] },
    TIMELINE: { events: [{ id: 'meeting', date: '2026-09-14', label: '讨论', detail: '' },
      { id: 'review', date: '2026-09-14', label: '同日复核', detail: '规划说明，不是已核验事件' }] },
  };
  const select = async blockId => {
    await ui.beginEdit(blockId);
    const context = ui.getSnapshot().editContext;
    assert.ok(context, ui.getSnapshot().message); assert.equal(context.block_id, blockId);
    assert.equal(editRequests.at(-1).edit_context_id, context.edit_context_id);
    return context;
  };
  for (const [kind, props] of Object.entries(displayChanges)) {
    const before = ui.getSnapshot().saved, blockId = `block_${kind}`;
    let context = await select(blockId);
    const read = await execute('competition_board_edit_context', { edit_context_id: context.edit_context_id });
    assert.equal(read.block_id, blockId); assert.equal(read.base_version, before.spec.version);
    const wrong = await execute('competition_board_edit', { edit_context_id: context.edit_context_id, changes: { props } }, 'other_session');
    assert.equal(wrong.status, 'REFUSED'); assert.equal(wrong.error.code, 'NOT_FOUND');
    let proposal = await execute('competition_board_edit', { edit_context_id: context.edit_context_id, changes: { props } });
    assert.equal(proposal.status, 'PREVIEW_READY', JSON.stringify(proposal));
    assert.deepEqual(outcomes.at(-1).meta, proposal, 'PATCH must reach the native tool-card metadata too');
    await ui.openPreview(proposal.preview_id, context.edit_context_id); await ui.cancel();
    assert.deepEqual(ui.getSnapshot().saved, before);
    const late = await execute('competition_board_edit', { edit_context_id: context.edit_context_id, changes: { props } });
    assert.equal(late.status, 'REFUSED'); assert.equal(late.error.code, 'EDIT_CANCELLED');
    context = await select(blockId);
    proposal = await execute('competition_board_edit', { edit_context_id: context.edit_context_id, changes: { props } });
    await ui.openPreview(proposal.preview_id, context.edit_context_id); await ui.confirm();
    const after = ui.getSnapshot().saved;
    assert.equal(after.spec.version, before.spec.version + 1, ui.getSnapshot().message);
    assert.deepEqual(after.spec.blocks.filter(block => block.block_id !== blockId), before.spec.blocks.filter(block => block.block_id !== blockId));
    const changed = after.spec.blocks.find(block => block.block_id === blockId);
    for (const [key, value] of Object.entries(props)) assert.deepEqual(changed.props[key], value);
    assert.deepEqual(after.facts_by_result_id, before.facts_by_result_id);
  }
  assert.equal((await execute('competition_board_catalog', {})).results.length, 1, 'display and planning edits do not query again');
  const beforeDataEdit = ui.getSnapshot().saved;
  const context = await select('block_LINE');
  const queried = await execute('competition_growth_step', { request_id: 'selected-date-change', capability_id: 'diag.gsv', condition_mode: 'EXPLICIT',
    condition_patch: {
      current_period: { start_date: '2026-08-01', end_date: '2026-08-15', end_bound: 'INCLUSIVE_CALENDAR_DAY' },
      comparison_period: { start_date: '2025-08-01', end_date: '2025-08-15', end_bound: 'INCLUSIVE_CALENDAR_DAY' },
    } });
  assert.equal(queried.execution_mode, 'COMPUTED_SYNTHETIC');
  const afterQuery = await execute('competition_board_catalog', {});
  assert.equal(afterQuery.results.length, 2);
  const newResult = afterQuery.results.find(row => row.result_id !== resultId); assert.ok(newResult);
  const changedData = await execute('competition_board_edit', { edit_context_id: context.edit_context_id,
    changes: { source_result_id: newResult.result_id, title: '8 月上半月 GSV' } });
  assert.equal(changedData.status, 'PREVIEW_READY', JSON.stringify(changedData));
  await ui.openPreview(changedData.preview_id, context.edit_context_id); await ui.confirm();
  const afterDataEdit = ui.getSnapshot().saved;
  assert.deepEqual(afterDataEdit.spec.blocks.filter(block => block.kind !== 'LINE'), beforeDataEdit.spec.blocks.filter(block => block.kind !== 'LINE'));
  assert.equal(afterDataEdit.spec.blocks.find(block => block.kind === 'LINE').source_result_id, newResult.result_id);
  assert.equal(afterDataEdit.facts_by_result_id[newResult.result_id].time_series.points.length, 15);
  assert.deepEqual(afterDataEdit.facts_by_result_id[resultId], beforeDataEdit.facts_by_result_id[resultId]);
  await reopened.openBoard(v1.spec.board_id);
  assert.deepEqual(reopened.getSnapshot().saved, afterDataEdit);
  const funnelContext = await select('block_FUNNEL');
  const funnelEdit = await execute('competition_board_edit', { edit_context_id: funnelContext.edit_context_id,
    changes: { source_result_id: newResult.result_id, title: '上半月购买频次' } });
  assert.equal(funnelEdit.status, 'PREVIEW_READY', JSON.stringify(funnelEdit));
  await ui.openPreview(funnelEdit.preview_id, funnelContext.edit_context_id);
  assert.deepEqual(ui.getSnapshot().saved, afterDataEdit, 'data edit remains unpublished until confirmation');
  await ui.confirm();
  const afterFunnelEdit = ui.getSnapshot().saved;
  assert.deepEqual(afterFunnelEdit.spec.blocks.filter(block => block.kind !== 'FUNNEL'), afterDataEdit.spec.blocks.filter(block => block.kind !== 'FUNNEL'));
  assert.equal(afterFunnelEdit.spec.blocks.find(block => block.kind === 'FUNNEL').source_result_id, newResult.result_id);
  const updatedFunnel = afterFunnelEdit.facts_by_result_id[newResult.result_id].funnel;
  assert.match(updatedFunnel.cohort_label, /2026-08-01–2026-08-15/);
  assert.deepEqual(updatedFunnel.stages.map(stage => stage.count), newResult.facts.current_purchase_frequency.stages.map(stage => stage.customer_count));
  assert.deepEqual(afterFunnelEdit.facts_by_result_id[resultId], beforeDataEdit.facts_by_result_id[resultId]);
  assert.equal((await execute('competition_board_catalog', {})).results.length, 2, 'same new result serves both LINE and FUNNEL');
  await reopened.openBoard(v1.spec.board_id);
  assert.deepEqual(reopened.getSnapshot().saved, afterFunnelEdit);
  await ui.rollback(3); await ui.confirm();
  assert.deepEqual(ui.getSnapshot().saved.spec.blocks, v1.spec.blocks);
  assert.deepEqual(ui.getSnapshot().saved.facts_by_result_id, v1.facts_by_result_id);
});
