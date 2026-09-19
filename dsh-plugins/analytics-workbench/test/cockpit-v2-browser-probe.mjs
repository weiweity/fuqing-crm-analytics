/**
 * Explicit real-browser + real FastAPI/SQLite probe. Synthetic files and owned random ports.
 * No DSH shell, model, live service or production credentials. Run after build.
 * B0_BUILD_UPSTREAM, FQ_B0_PYTHON, COCKPIT_PLAYWRIGHT and COCKPIT_CHROMIUM are explicit existing tools.
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { join, resolve } from 'node:path';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { handleBoardBrowserCall } from '../src/board-spec/browser-api.mjs';

const root = fileURLToPath(new URL('../../..', import.meta.url));
const plugin = join(root, 'dsh-plugins/analytics-workbench');
const evidence = resolve(process.env.COCKPIT_EVIDENCE_DIR ?? join(root, '.context/checks/cockpit-v2-codex/browser'));
await mkdir(evidence, { recursive: true });
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(root, '.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const esbuild = createRequire(web.resolve('vite/package.json'))('esbuild');
await esbuild.build({ absWorkingDir: plugin, entryPoints: ['test/helpers/cockpit-v2-browser-entry.tsx'],
  outfile: join(plugin, 'lib/cockpit-v2-browser.js'), bundle: true, platform: 'browser', format: 'esm',
  alias: { react: web.resolve('react').replace(/\/index\.js$/, ''), 'react-dom': web.resolve('react-dom').replace(/\/index\.js$/, '') },
  jsx: 'automatic', target: 'es2022', loader: { '.css': 'empty' }, logLevel: 'silent' });
const javascript = await readFile(join(plugin, 'lib/cockpit-v2-browser.js'));
const child = spawn(process.env.FQ_B0_PYTHON ?? 'python3.14', ['-m', 'backend.tests.library_board_http_probe', '--cockpit-v2'],
  { cwd: root, env: { PATH: process.env.PATH, PYTHONPATH: root, PYTHONNOUSERSITE: '1', PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1' }, stdio: ['pipe','pipe','pipe'] });
const terminal = new Promise(resolve => { child.once('exit', (code, signal) => resolve({ code, signal })); child.once('error', error => resolve({ error: error.message })); });
let stderr = '';
child.stderr.on('data', data => { stderr += data; });
let browser, server, readyTimer;
const results = [], errors = [], screenshots = [];
const check = (name, detail = '') => { results.push({ name, status: 'PASS', detail }); process.stdout.write('PASS ' + name + '\n'); };
try {
  const lines = createInterface({ input: child.stdout });
  const ready = await Promise.race([
    new Promise((resolve, reject) => lines.once('line', line => { try { resolve(JSON.parse(line)); } catch (error) { reject(error); } })),
    terminal.then(result => { throw new Error('HTTP stopped ' + JSON.stringify(result) + stderr); }),
    new Promise((_, reject) => { readyTimer = setTimeout(() => reject(new Error('HTTP readiness timeout')), 15000); }),
  ]).finally(() => { clearTimeout(readyTimer); lines.close(); });
  assert.equal(ready.contains_real_data, false);
  process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:' + ready.port;
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-native-board-integration-token';
  const headers = { authorization: 'Bearer ' + process.env.COMPETITION_HTTP_TOKEN, 'content-type': 'application/json' };
  const backend = async (path, body, key) => {
    const response = await fetch(process.env.COMPETITION_HTTP_BASE + path, { method: body === undefined ? 'GET' : 'POST',
      headers: { ...headers, ...(key ? { 'idempotency-key': key } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    const value = await response.json(); assert.ok(response.ok, JSON.stringify(value)); return value;
  };
  const prefix = '/api/v1/analytics/board-spec';
  const generated = await backend(prefix + '/previews', { title: '渠道复盘 · 合成看板', session_id: 'native_session', blocks: [
    { block_id: 'note', title: '本周经营观察', kind: 'TEXT', props: { content: '渠道结构保持稳定。先核对口径，再决定下一步行动。' }, layout: { x: 0, y: 0, w: 7, h: 6 } },
    { block_id: 'plan', title: '接下来做什么', kind: 'TEXT', props: { content: '1. 核对新增客户\n2. 观察渠道变化\n3. 记录验证结论' }, layout: { x: 7, y: 0, w: 5, h: 6 } },
  ] });
  const board = await backend(prefix + '/previews/' + generated.preview_id + '/confirm', {}, 'browser-seed');
  const readBody = async req => { const chunks = []; for await (const chunk of req) chunks.push(chunk); return Buffer.concat(chunks); };
  server = createServer((req, res) => { void (async () => {
    const origin = 'http://127.0.0.1:' + server.address().port;
    const path = new URL(req.url, origin).pathname;
    if (req.headers.host !== new URL(origin).host || (req.headers.origin && req.headers.origin !== origin)) { res.writeHead(403); res.end(); return; }
    if (path === '/') { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end('<!doctype html><html lang="zh"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>驾驶舱 V2 · 隔离合成验收</title><style>html,body,#root{height:100%;margin:0}body{overflow:hidden}#fixture-label{position:fixed;bottom:4px;right:8px;z-index:100;font:10px sans-serif;color:#999;pointer-events:none}</style></head><body><div id="root"></div><span id="fixture-label">隔离 synthetic · 本地候选</span><script type="module" src="/fixture.js"></script></body></html>'); return; }
    if (path === '/fixture.js') { res.writeHead(200, { 'content-type': 'text/javascript' }); res.end(javascript); return; }
    if (path === '/fixture/board' && req.method === 'POST') {
      const { operation, payload } = JSON.parse(await readBody(req));
      const reply = await handleBoardBrowserCall(operation, payload);
      res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(reply)); return;
    }
    if (path.startsWith('/api/v1/analytics/page-documents/')) {
      const body = await readBody(req);
      const response = await fetch(process.env.COMPETITION_HTTP_BASE + req.url, { method: req.method,
        headers: { ...headers, ...(req.headers['idempotency-key'] ? { 'idempotency-key': req.headers['idempotency-key'] } : {}) },
        ...(body.length ? { body } : {}) });
      res.writeHead(response.status, { 'content-type': 'application/json' }); res.end(await response.text()); return;
    }
    res.writeHead(404); res.end();
  })().catch(error => { res.writeHead(500); res.end(JSON.stringify({ error: { message: error.message } })); }); });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const origin = 'http://127.0.0.1:' + server.address().port;
  const { chromium } = createRequire(import.meta.url)(process.env.COCKPIT_PLAYWRIGHT);
  browser = await chromium.launch({ executablePath: process.env.COCKPIT_CHROMIUM, headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => errors.push(error.message));
  const shot = async name => { const path = join(evidence, name + '.png'); await page.screenshot({ path, fullPage: true }); screenshots.push(path); };
  const idle = () => page.waitForFunction(() => !window.cockpitFixture.library.getSnapshot().busy && !window.cockpitFixture.pageStore.getSnapshot().busy && document.querySelector('main')?.getAttribute('aria-busy') === 'false');
  const click = async testid => { await page.getByTestId(testid).click(); await idle(); };
  await page.goto(origin);
  await page.getByTestId('library-html-preview').waitFor(); await idle();
  assert.equal(await page.evaluate(() => window.cockpitFixture.delivery.getSessionId()), 'native_session');
  await shot('01-cabinet-1440');
  check('来源会话、产物扫描与 HTML 只读预览');
  await page.evaluate(() => window.cockpitFixture.setMounted(false));
  await page.getByTestId('library-workspace').waitFor({ state: 'detached' });
  await page.evaluate(() => window.cockpitFixture.setMounted(true));
  await page.getByTestId('library-html-preview').waitFor(); await idle();
  await page.frameLocator('[data-testid="library-html-preview"]').locator('[data-shine-node="report_title"]').waitFor();
  check('原始 HTML 在宿主卸载/重入后按同一会话路径重新读取');
  await click('html-import-start');
  await page.getByTestId('html-import-preview').waitFor();
  await page.frameLocator('[data-testid="library-html-preview"]').locator('body[data-import-order="ordered"]').waitFor();
  check('HTML 入库保留内联配置和相对脚本的执行顺序');
  assert.equal((await backend('/api/v1/analytics/page-documents/pages')).items.length, 0);
  await shot('02-import-preview');
  await page.getByRole('button', { name: '确认保存副本', exact: true }).click(); await idle();
  const imported = await page.evaluate(() => window.cockpitFixture.pageStore.getSnapshot().current);
  assert.equal(imported.version, 1); assert.equal(imported.origin_path, 'weekly-review.html');
  check('入库仅在显式确认后写入，保留来源');
  const nativePreview = await backend(prefix + '/previews', { title: '原生新预览', session_id: 'native_session', blocks: [
    { block_id: 'native', title: '原生候选', kind: 'TEXT', props: { content: '可见的新看板' }, layout: { x: 0, y: 0, w: 6, h: 5 } },
  ] });
  await page.evaluate(() => window.cockpitFixture.setMounted(false));
  await page.getByTestId('library-workspace').waitFor({ state: 'detached' });
  await page.evaluate(id => window.cockpitFixture.library.openPreview(id), nativePreview.preview_id);
  await page.evaluate(() => window.cockpitFixture.setMounted(true));
  await page.getByTestId('library-preview-banner').waitFor(); await idle();
  assert.equal(await page.getByTestId('library-html-preview').count(), 0);
  await click('library-cancel');
  await page.locator('[data-kind="html"] button').filter({ hasText: '已保存页面' }).click(); await idle();
  check('原生新看板预览覆盖旧 HTML 选择，可显示并取消');
  await click('cockpit-edit-btn');
  const frame = page.frameLocator('[data-testid="library-html-preview"]');
  await frame.locator('[data-shine-node="section_two"]').click();
  await page.getByTestId('html-replacement').fill('下一阶段行动');
  await shot('03-html-selection-1440');
  await frame.locator('[data-shine-node="section_two"][data-cockpit-selected]').waitFor();
  assert.equal(await frame.locator('[data-shine-node="section_two"]').evaluate(node => getComputedStyle(node).outlineStyle), 'solid');
  for (const width of [1280, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 }); await page.waitForTimeout(100);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await shot('03-html-editor-' + width);
    if (width === 390) {
      await page.getByRole('button', { name: '画布预览', exact: true }).click();
      assert.equal(await page.getByTestId('library-html-preview').isVisible(), true);
      const frameMetrics = await page.getByTestId('library-html-preview').evaluate(node => ({ width: node.getBoundingClientRect().width, parent: node.parentElement.getBoundingClientRect().width }));
      const contentMetrics = await frame.locator('body').evaluate(node => ({ viewport: innerWidth, content: document.documentElement.scrollWidth, padding: getComputedStyle(node.querySelector('main')).padding }));
      process.stdout.write('Mobile frame ' + JSON.stringify({ frameMetrics, contentMetrics }) + '\n');
      assert.ok(frameMetrics.width <= frameMetrics.parent + 1, 'iframe fits its canvas');
      assert.ok(contentMetrics.content <= contentMetrics.viewport + 1, 'responsive HTML content fits the iframe');
      await frame.locator('body').evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.waitForTimeout(150); // Let the formerly hidden iframe composite at its new width.
      await shot('03-html-canvas-390');
      await page.getByRole('button', { name: '编辑设置', exact: true }).click();
      assert.equal(await page.getByTestId('html-replacement').inputValue(), '下一阶段行动');
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  if (await page.getByRole('button', { name: '产物列表', exact: true }).isVisible()) await page.getByRole('button', { name: '产物列表', exact: true }).click();
  check('HTML 持续选中框与窄屏画布/属性切换，输入保持不丢失');

  await click('html-preview-patch');
  await page.getByRole('button', { name: '取消预览', exact: true }).click(); await idle();
  assert.equal((await backend('/api/v1/analytics/page-documents/pages/' + imported.page_id)).spec.version, 1);
  check('重复文字按节点定位，取消预览不写版本');
  await frame.locator('[data-shine-node="section_two"]').click();
  await page.getByTestId('html-replacement').fill('下一阶段行动');
  await click('html-preview-patch'); await click('html-confirm');
  let stored = (await backend('/api/v1/analytics/page-documents/pages/' + imported.page_id)).spec;
  assert.equal(stored.version, 2); assert.match(stored.package.html, /section_one[^>]*>本周观察/); assert.match(stored.package.html, /section_two[^>]*>下一阶段行动/);
  check('HTML 精确替换、确认、独立连接重读落盘');
  await page.reload(); await idle();
  await page.locator('[data-kind="html"] button').filter({ hasText: '已保存页面' }).click(); await idle();
  assert.equal(await page.evaluate(() => window.cockpitFixture.pageStore.getSnapshot().current.version), 2);
  await page.getByRole('button', { name: '版本历史', exact: true }).click(); await idle();
  await page.locator('.cockpit-history-row').filter({ hasText: '版本 1' }).getByRole('button').click(); await idle();
  await click('html-confirm');
  assert.equal((await backend('/api/v1/analytics/page-documents/pages/' + imported.page_id)).spec.version, 3);
  check('浏览器重建 store 恢复持久化页面，回退保存为新版本');
  if (await page.getByTestId('cockpit-sidebar-close').isVisible()) await page.getByTestId('cockpit-sidebar-close').click();
  await click('cockpit-edit-btn');
  await frame.locator('[data-shine-node="report_title"]').click();
  await page.getByTestId('html-replacement').fill('回执丢失后的标题');
  await click('html-preview-patch');
  await page.evaluate(() => { window.cockpitFixture.controls.loseConfirm = true; });
  await click('html-confirm');
  assert.equal(await page.evaluate(() => window.cockpitFixture.pageStore.getSnapshot().confirmationUncertain), true);
  assert.equal(await page.locator('[data-kind="board"] button').isDisabled(), true);
  assert.equal(await page.getByRole('button', { name: '取消预览', exact: true }).isDisabled(), true);
  await shot('04-uncertain-receipt');
  await click('html-confirm');
  assert.equal((await backend('/api/v1/analytics/page-documents/pages/' + imported.page_id)).spec.version, 4);
  check('已落盘但丢回执：锁定切换、同幂等键重试只写一个版本');
  await frame.locator('[data-shine-node="report_title"]').click();
  await page.getByTestId('html-replacement').fill('这次放弃');
  await click('sm-cockpit-back');
  await page.getByTestId('leave-prompt').waitFor();
  await click('leave-stay');
  assert.equal(await page.getByTestId('html-replacement').inputValue(), '这次放弃');
  await click('sm-cockpit-back'); await click('leave-discard');
  assert.equal(await page.locator('body').getAttribute('data-left'), 'true');
  check('文本未保存离开保护：留下保留输入，放弃只丢本次修改');
  await page.locator('[data-kind="board"] button').click(); await idle();
  await click('cockpit-edit-btn');
  await page.getByRole('button', { name: '选择组件 本周经营观察', exact: true }).click(); await idle();
  assert.equal(await page.evaluate(() => window.cockpitFixture.nativeMessages()), 0);
  await page.getByTestId('board-title-input').fill('重点经营观察');
  await click('board-preview-patch');
  const canceledId = await page.evaluate(() => window.cockpitFixture.library.getSnapshot().preview.preview_id);
  await click('library-cancel');
  assert.equal((await backend(prefix + '/previews/' + canceledId)).status, 'CANCELLED');
  check('看板点选不发消息，字段预览取消清理实际服务端候选');
  await page.getByTestId('board-title-input').fill('重点经营观察');
  await page.locator('.cockpit-board-form textarea').fill('属性补丁经过客户端、RPC 与真实 HTTP。');
  await page.getByLabel(/^对齐方式/).selectOption('center');
  await click('board-preview-patch'); await shot('05-board-field-preview'); await click('library-confirm');
  assert.equal((await backend(prefix + '/boards/' + board.spec.board_id)).spec.version, 2);
  const editedBlock = (await backend(prefix + '/boards/' + board.spec.board_id)).spec.blocks[0];
  assert.equal(editedBlock.props.content, '属性补丁经过客户端、RPC 与真实 HTTP。');
  assert.equal(editedBlock.props.align, 'center');
  assert.equal(editedBlock.title, '重点经营观察');
  check('看板正文与对齐属性经 RPC 入库，同类型 PATCH 保留其他字段');
  await click('layout-start');
  await page.locator('[data-layout-mode="resize"]').first().focus();
  await page.keyboard.press('ArrowDown');
  await click('layout-preview'); await click('library-confirm');
  assert.equal((await backend(prefix + '/boards/' + board.spec.board_id)).spec.version, 3);
  await page.getByRole('button', { name: '查看版本历史', exact: true }).click(); await idle();
  await page.locator('.cockpit-history-row').filter({ hasText: '版本 1' }).getByRole('button').click(); await idle();
  await click('library-confirm');
  assert.equal((await backend(prefix + '/boards/' + board.spec.board_id)).spec.version, 4);
  check('看板字段保存、键盘布局、历史回退');
  await page.getByRole('button', { name: '选择组件 本周经营观察', exact: true }).click(); await idle();
  await page.locator('.cockpit-board-form textarea').fill('冲突草稿不可覆盖其他写入');
  await click('board-preview-patch');
  const conflictId = await page.evaluate(() => window.cockpitFixture.library.getSnapshot().preview.preview_id);
  const externalBoard = await backend(prefix + '/boards/' + board.spec.board_id + '/patch-preview', {
    base_version: 4, block_id: 'note', changes: { props: { content: '另一客户端的已保存内容' } },
  });
  await backend(prefix + '/previews/' + externalBoard.preview_id + '/confirm', {}, 'board-external-cas');
  await click('library-confirm'); await click('library-inspect-confirmation');
  assert.equal(await page.evaluate(() => window.cockpitFixture.library.getSnapshot().confirmationUncertain), true);
  await shot('06-board-confirm-conflict');
  await click('library-cancel');
  assert.equal((await backend(prefix + '/previews/' + conflictId)).status, 'CANCELLED');
  assert.equal((await backend(prefix + '/boards/' + board.spec.board_id)).spec.version, 5);
  await page.evaluate(() => window.cockpitFixture.library.refresh()); await idle();
  assert.equal(await page.evaluate(() => window.cockpitFixture.library.getSnapshot().saved.spec.version), 5);
  check('真实看板确认 409 后可安全取消并恢复最新版本，不覆盖其他写入');
  for (const width of [1440, 1280, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.waitForTimeout(100);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no document overflow at ' + width);
    await shot('06-board-' + width);
  }
  check('1440 / 1280 / 1024 / 390，缩放 100%，页面无横向挤出');
  await page.setViewportSize({ width: 1440, height: 1000 });
  if (!await page.getByRole('button', { name: '刷新产物', exact: true }).isVisible()) await page.getByRole('button', { name: '产物列表', exact: true }).click();
  await page.evaluate(() => { window.cockpitFixture.controls.failList = true; });
  await page.getByRole('button', { name: '刷新产物', exact: true }).click(); await idle();
  await page.getByText('会话文件读取失败。已保存产物仍可使用。', { exact: true }).waitFor();
  await shot('07-list-error');
  await page.evaluate(() => { window.cockpitFixture.controls.failList = false; window.cockpitFixture.delivery.setSessionId('other_session'); });
  await page.getByText('other.html', { exact: true }).first().waitFor();
  await page.waitForFunction(() => window.cockpitFixture.delivery.getSnapshot().status === 'ready');
  assert.equal(await page.locator('[data-kind="html"] button').filter({ hasText: 'weekly-review.html 工作区' }).count(), 0);
  check('列表失败可恢复，切会话不保留旧会话文件');
  await page.locator('[data-kind="html"] button').filter({ hasText: '已保存页面' }).click(); await idle();
  await click('cockpit-edit-btn');
  await frame.locator('[data-shine-node="report_title"]').click();
  await page.getByTestId('html-replacement').fill('冲突时保留输入');
  const beforeConflict = (await backend('/api/v1/analytics/page-documents/pages/' + imported.page_id)).spec;
  const external = await backend('/api/v1/analytics/page-documents/pages/' + imported.page_id + '/patch-preview', { base_version: beforeConflict.version, package: beforeConflict.package });
  await backend('/api/v1/analytics/page-documents/previews/' + external.preview_id + '/confirm', {}, 'browser-external-cas');
  await click('html-preview-patch');
  assert.equal(await page.evaluate(() => window.cockpitFixture.pageStore.getSnapshot().preview), null);
  assert.equal(await page.getByTestId('html-replacement').inputValue(), '冲突时保留输入');
  assert.ok(await page.getByTestId('library-message').innerText());
  await shot('08-html-conflict');
  await click('sm-cockpit-back'); await click('leave-discard');
  await page.locator('[data-kind="html"] button').filter({ hasText: '已保存页面' }).click(); await idle();
  assert.equal(await page.evaluate(() => window.cockpitFixture.pageStore.getSnapshot().current.version), beforeConflict.version + 1);
  check('真实 CAS 冲突保留输入，放弃后重新打开最新版本');
  await page.evaluate(() => { window.cockpitFixture.controls.eof = false; });
  await page.locator('[data-kind="html"] button').filter({ hasText: 'other.html' }).click(); await idle();
  assert.equal(await page.getByTestId('library-html-preview').count(), 0);
  await page.getByText('文件未能完整读取，请刷新后重试。', { exact: false }).waitFor();
  check('未读到 eof 的工作区文件不冒充完整预览或允许入库');
  await page.evaluate(() => window.cockpitFixture.delivery.setSessionId(null));
  await page.getByText('尚未选择来源会话。回到对话后再打开驾驶舱。', { exact: true }).waitFor();
  await shot('09-no-session');
  check('无来源会话显示明确状态，已保存内容仍可用');

  assert.deepEqual(errors, []);
  check('浏览器无未处理异常');
} catch (error) {
  results.push({ name: 'probe', status: 'FAIL', detail: error.stack });
  process.stderr.write(error.stack + '\n');
  if (browser) { const page = browser.contexts()[0]?.pages()[0]; if (page) { await page.screenshot({ path: join(evidence, 'failure.png'), fullPage: true }); await writeFile(join(evidence, 'failure.txt'), await page.locator('body').innerText()); } }
  process.exitCode = 1;
} finally {
  await browser?.close();
  if (server) { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
  child.stdin.end();
  const kill = setTimeout(() => child.kill('SIGTERM'), 12000);
  const stopped = await terminal; clearTimeout(kill);
  if (stopped.code !== 0) { results.push({ name: 'owned HTTP cleanup', status: 'FAIL', detail: stderr }); process.exitCode = 1; }
  await writeFile(join(evidence, 'results.json'), JSON.stringify({ results, errors, screenshots, full_dsh_shell: 'NOT_RUN', real_model: 'NOT_RUN', contains_real_data: false }, null, 2));
}
