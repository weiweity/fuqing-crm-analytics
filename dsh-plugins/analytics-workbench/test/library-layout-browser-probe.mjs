/** Explicit, owned, disposable synthetic browser probe. No real data or model credentials. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mountNativeBoardBridge } from './helpers/native-board-bridge.mjs';
import { mountBoardFaultProxy } from './helpers/board-fault-proxy.mjs';

const root = fileURLToPath(new URL('../../..', import.meta.url));
const plugin = join(root, 'dsh-plugins/analytics-workbench');
assert.ok(process.argv.slice(2).length <= 1 && process.argv.slice(2).every(arg => ['--structured', '--waterfall', '--funnel', '--failures'].includes(arg)), 'Only one of --structured / --waterfall / --funnel / --failures is supported');
const structured = process.argv.includes('--structured');
const waterfall = process.argv.includes('--waterfall');
const funnel = process.argv.includes('--funnel');
const failures = process.argv.includes('--failures');
const python = process.env.FQ_B0_PYTHON;
assert.ok(python?.startsWith('/'), 'FQ_B0_PYTHON must identify the authorized absolute interpreter');
const child = spawn(python, ['-m', 'backend.tests.library_board_http_probe', ...(waterfall ? ['--waterfall-scenario'] : funnel ? ['--funnel-scenario'] : [])], { cwd: root,
  env: { PATH: process.env.PATH, PYTHONPATH: root, PYTHONNOUSERSITE: '1', PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1' },
  stdio: ['pipe', 'pipe', 'pipe'] });
const terminal = new Promise(resolve => { child.once('exit', (code, signal) => resolve({ code, signal })); child.once('error', error => resolve({ error: error.message })); });
let stderr = '', bridge, faultProxy;
child.stderr.on('data', data => { if (stderr.length < 6000) stderr += data; });
try {
  const lines = createInterface({ input: child.stdout }); let timer;
  const ready = await Promise.race([
    new Promise((resolve, reject) => lines.once('line', line => { try { resolve(JSON.parse(line)); } catch (error) { reject(error); } })),
    terminal.then(() => { throw new Error('isolated Python stopped before ready'); }),
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('readiness timeout')), 15000); }),
  ]).finally(() => { clearTimeout(timer); lines.close(); });
  assert.equal(ready.contains_real_data, false);
  const serviceOrigin = `http://127.0.0.1:${ready.port}`;
  faultProxy = failures ? await mountBoardFaultProxy(serviceOrigin) : null;
  process.env.COMPETITION_HTTP_BASE = faultProxy?.origin ?? serviceOrigin;
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-native-board-integration-token';
  const web = createRequire(join(root, '.context/dsh-b0/upstream/apps/web/package.json'));
  const esbuild = createRequire(web.resolve('vite/package.json'))('esbuild');
  const output = await esbuild.build({ absWorkingDir: plugin, entryPoints: ['test/helpers/library-browser-entry.tsx'],
    bundle: true, write: false, format: 'esm', platform: 'browser', target: 'es2022', jsx: 'automatic',
    alias: { react: dirname(web.resolve('react/package.json')), 'react-dom': dirname(web.resolve('react-dom/package.json')) },
    define: { 'process.env.NODE_ENV': '"production"' }, logLevel: 'silent' });
  bridge = await mountNativeBoardBridge({ isolatedBrowserEntry: true,
    indexHtml: '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>隔离布局验收</title></head><body style="margin:0"><div id="root"></div><script type="module" src="/canvas.js"></script></body></html>',
    assets: { '/canvas.js': { type: 'text/javascript; charset=utf-8', body: output.outputFiles[0].contents },
      '/b0/brand/outfit.ttf': { type: 'font/ttf', body: await readFile(join(root, 'frontend-vue3/src/assets/fonts/Outfit-Variable.ttf')) } } });
  let resultBlocks;
  if (waterfall || funnel) {
    const computed = await fetch(`${process.env.COMPETITION_HTTP_BASE}/api/v1/analytics/competition/diagnosis/step`, {
      method: 'POST', headers: { authorization: `Bearer ${process.env.COMPETITION_HTTP_TOKEN}`, 'content-type': 'application/json' },
      body: JSON.stringify({ request_id: funnel ? 'funnel_browser' : 'waterfall_browser', capability_id: 'diag.gsv', condition_mode: 'EXPLICIT', session_id: 'native_session',
        condition: { metric_type: 'GSV', timezone: 'Asia/Shanghai',
          current_period: { start_date: '2026-08-01', end_date: '2026-08-31', end_bound: 'INCLUSIVE_CALENDAR_DAY' },
          comparison_period: { start_date: '2025-08-01', end_date: '2025-08-31', end_bound: 'INCLUSIVE_CALENDAR_DAY' },
          comparison_mode: 'YOY_SAME_PERIOD', sales_scope: { kind: 'ALL' }, history_scope: { kind: 'ALL' }, sample_mode: 'INCLUDE', sample_channel_ids: null } }) });
    assert.equal(computed.status, 200);
    const result = (await computed.json()).result;
    assert.equal(funnel ? result.facts.current_purchase_frequency.status : result.facts.channel_bridge.status, 'AVAILABLE');
    if (funnel) assert.deepEqual(result.facts.current_purchase_frequency.stages.map(stage => stage.customer_count), [3, 2, 1]);
    resultBlocks = [{ block_id: funnel ? 'funnel' : 'waterfall', kind: funnel ? 'FUNNEL' : 'WATERFALL',
      title: funnel ? '本期购买频次漏斗（合成）' : '销售渠道 GSV 变化（合成）',
      source_result_id: result.result_id, props: {}, layout: { x: 0, y: 0, w: 12, h: 12 } },
      { block_id: 'note', kind: 'TEXT', title: '数据与能力边界', props: { content: funnel
        ? '同一范围内的去重购买客户，至少1/2/3笔有效订单；不是访客转化、历史首购或营销因果归因。当前为隔离合成数据，不是业务结论。'
        : '同口径订单净額差，不是营销因果归因。当前为隔离合成数据；不是业务结论。' },
        layout: { x: 0, y: 12, w: 12, h: 4 } }];
  }
  const response = await fetch(`${process.env.COMPETITION_HTTP_BASE}/api/v1/analytics/board-spec/previews`, {
    method: 'POST', headers: { authorization: `Bearer ${process.env.COMPETITION_HTTP_TOKEN}`, 'content-type': 'application/json' },
    body: JSON.stringify({ title: funnel ? '人群漏斗组件验收' : waterfall ? '贡献瀑布组件验收' : structured ? '结构化规划组件验收' : '隔离布局验证看板', session_id: 'native_session', blocks: resultBlocks ?? (structured ? [
      { block_id: 'process', kind: 'PROCESS', title: '试点评审流程（规划）', props: {
        nodes: [{ id: 'review', label: '核对数据口径', owner: '分析师' }, { id: 'decide', label: '讨论试点方案', owner: '老板' },
          { id: 'refine', label: '补充证据再评审', owner: '运营' }],
        edges: [{ from: 'review', to: 'decide', label: '证据齐全' }, { from: 'review', to: 'refine', label: '仍有缺口' },
          { from: 'refine', to: 'review', label: '返回核对' }, { from: 'decide', to: 'decide', label: '继续讨论' }],
      }, layout: { x: 0, y: 0, w: 6, h: 20 } },
      { block_id: 'timeline', kind: 'TIMELINE', title: '评审日程（规划）', props: {
        events: [{ id: 'start', date: '2026-09-13', label: '开始整理口径' },
          { id: 'review', date: '2026-09-14', label: '团队评审', detail: '这是隔离验收的合成规划，不是实际企业排期。' },
          { id: 'same', date: '2026-09-14', label: '同日记录异议和待补证据，保留完整的长内容说明' },
          { id: 'end', date: '2026-09-23', label: '计划复盘' }],
      }, layout: { x: 6, y: 0, w: 6, h: 20 } },
    ] : [
      { block_id: 'note', kind: 'TEXT', title: '可自由移动的说明', library_version: 'board-components/v1', props: { content: '拖动或缩放本组件。所有调整先进入草稿，确认后才持久化。' }, layout: { x: 0, y: 0, w: 6, h: 5 } },
      { block_id: 'neighbour', kind: 'TEXT', title: '保持不变的组件', library_version: 'board-components/v1', props: { content: '用于验证碰撞和指定范围：另一块的移动不得改变这里。' }, layout: { x: 6, y: 0, w: 6, h: 5 } },
    ]) }) });
  assert.equal(response.status, 201);
  const preview = await response.json();
  const confirmed = await bridge.call('/shine-mage-board', 'confirm', { preview_id: preview.preview_id, key: 'isolated-browser-seed' });
  assert.equal(confirmed.ok, true);
  console.log(JSON.stringify({ url: `${bridge.origin}/__isolated_browser__`, contains_real_data: false,
    board_id: confirmed.value.spec.board_id, scope: 'production canvas + native RPC + SQLite; no full shell or model' }));
  const commands = createInterface({ input: process.stdin });
  try {
    if (failures) console.log('FAULT_COMMANDS: fault confirm-before | fault confirm-after | fault get | fault list | inspect | empty line closes');
    await Promise.race([new Promise((resolve, reject) => {
      let pending = Promise.resolve();
      commands.on('line', line => {
        pending = pending.then(async () => {
          if (!line.trim()) { resolve(); return; }
          assert.ok(failures, 'commands require --failures');
          if (line.startsWith('fault ')) {
            faultProxy.arm(line.slice(6).trim()); console.log(JSON.stringify({ evidence: 'fault_armed', mode: faultProxy.audit().armed }));
          } else {
            assert.equal(line.trim(), 'inspect');
            const direct = async path => {
              const response = await fetch(`${serviceOrigin}/api/v1/analytics/board-spec${path}`, {
                headers: { authorization: `Bearer ${process.env.COMPETITION_HTTP_TOKEN}` } });
              assert.equal(response.status, 200); return response.json();
            };
            const id = confirmed.value.spec.board_id;
            console.log(JSON.stringify({ evidence: 'fault_service_readback', snapshot: await direct(`/boards/${id}`),
              history: await direct(`/boards/${id}/versions`), transport: faultProxy.audit() }));
          }
        }).catch(reject);
      });
      commands.once('close', () => pending.then(resolve, reject));
      process.once('SIGTERM', resolve); process.once('SIGINT', resolve);
    }), terminal.then(() => { throw new Error('owned Python exited while browser probe was active'); })]);
  } finally { commands.close(); }
} finally {
  try {
    if (bridge) {
      const saved = await bridge.call('/shine-mage-board', 'list', {});
      if (saved.ok) for (const board of saved.value.items) {
        const readback = await bridge.call('/shine-mage-board', 'get', { board_id: board.board_id });
        if (readback.ok) console.log(JSON.stringify({ evidence: 'final_server_readback', snapshot: readback.value }));
      }
    }
  } catch { console.error('FINAL_SERVER_READBACK_UNAVAILABLE'); }
  try { try { await bridge?.close(); } finally { await faultProxy?.close(); } }
  finally {
    child.stdin.end();
    const timer = setTimeout(() => child.kill('SIGTERM'), 12000);
    const result = await terminal; clearTimeout(timer);
    process.stdin.pause();
    assert.deepEqual(result, { code: 0, signal: null }, stderr);
    console.log('ISOLATED_BROWSER_PROBE_CLOSED');
  }
}
