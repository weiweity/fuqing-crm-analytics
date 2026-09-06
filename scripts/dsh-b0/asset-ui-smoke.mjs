/** Uses the already-authorized browse skill, not another browser engine.
 * Current isolated runtime only; no prompt, SQL, real data, or business write.
 * Title and synthetic old-filter preferences are restored in finally.
 */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { resolve, join, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { BOARD_SAMPLE, BOARD_SAMPLE_PATH, BOARD_SAMPLE_DIGEST } from './board-sample.mjs';
import { TITLE_STORAGE_KEY } from '../../dsh-plugins/analytics-workbench/src/model.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const [target, browse, tab, ...extra] = process.argv.slice(2);
assert.ok(target && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length,
  'Usage: node asset-ui-smoke.mjs <current-runtime> /absolute/browse <owned-tab-id>');
const runtime = resolve(target);
const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
assert.equal(runtime, current.runtime);
assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
const runCount = () => db.prepare('SELECT COUNT(*) AS n FROM runs').get().n;
const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 1024 * 1024 });
const js = expression => b('js', expression).trim();
const data = expression => JSON.parse(js(expression));
const control = id => `[data-testid="${id}"]`;
const click = id => b('click', control(id));
const text = id => js(`document.querySelector(${JSON.stringify(control(id))})?.textContent`);
const report = { kind: 'B0_ASSET_UI_SEAMS', started_at: new Date().toISOString(), tests: [], screenshots: [], status: 'RUNNING' };
report.plugin_hashes = Object.fromEntries(await Promise.all(['index.js', 'tool.js', 'skills.js', 'client.js']
  .map(async name => [name, createHash('sha256').update(await readFile(join(current.plugin, 'lib', name))).digest('hex')])));
const oldFilterKey = 'b0-synthetic-legacy-filter-sentinel';
let savedPrefs, paused = false;
async function check(name, action) { report.active_test = name; await action(); report.tests.push({ name, status: 'PASS' }); delete report.active_test; }
function screenshot(name) {
  const path = join(runtime, `${name}.png`);
  b('screenshot', path); report.screenshots.push(path);
}
function openAsset() {
  if (!data('Boolean(document.querySelector("dialog.analytics-b0-dialog")?.open)')) click('analytics-b0-open');
  assert.equal(data('document.querySelector("dialog.analytics-b0-dialog").open'), true);
}
try {
  assert.equal(runCount(), 0, 'Run asset smoke before the fixed native seven-question FIFO');
  b('tab', tab); b('goto', 'http://127.0.0.1:4318/'); b('viewport', '1440x1000');
  savedPrefs = data(`({title:localStorage.getItem(${JSON.stringify(TITLE_STORAGE_KEY)}),oldFilter:localStorage.getItem(${JSON.stringify(oldFilterKey)})})`);
  await check('original-brand-slots-and-favicon', async () => {
    assert.equal(data('document.querySelectorAll(".analytics-b0-mark").length'), 1);
    const asset = data(`Promise.all(['/b0/brand/logo.png','/favicon.svg'].map(async p=>({path:p,status:(await fetch(p)).status})))`);
    assert.ok(asset.every(row => row.status === 200));
    assert.equal(js('new URL(document.querySelector("link[rel=icon]").href).pathname'), '/favicon.svg');
  });
  openAsset();
  const originalTitle = text('analytics-b0-title');
  await check('native-no-session-and-model-unavailable-assets', async () => {
    click('analytics-b0-detach');
    assert.ok(text('analytics-b0-selection').includes('当前无活动会话'));
    assert.equal(data('document.querySelectorAll(".analytics-b0-runs").length'), 0);
    const command = execFileSync('ps', ['-p', String(current.supervisorPid), '-o', 'args='], { encoding: 'utf8' });
    assert.match(command, /scripts\/dsh-b0\/serve\.mjs --python/);
    const baseline = await fetch('http://127.0.0.1:4319/unavailable-probe', { signal: AbortSignal.timeout(1500) });
    assert.equal(baseline.status, 404); await baseline.body?.cancel();
    process.kill(current.supervisorPid, 'SIGSTOP'); paused = true;
    try {
      await assert.rejects(fetch('http://127.0.0.1:4319/unavailable-probe', { signal: AbortSignal.timeout(500) }));
      assert.ok(text('analytics-b0-selection').includes('当前无活动会话'));
      assert.equal(text('analytics-b0-title'), originalTitle);
      const cells = data('Array.from(document.querySelectorAll(".analytics-b0-dialog tbody td")).map(e=>e.textContent)');
      assert.deepEqual(cells, ['100', '25', '25%']);
      screenshot('asset-no-session-model-unavailable');
    } finally { process.kill(current.supervisorPid, 'SIGCONT'); paused = false; }
    click('analytics-b0-close');
    assert.equal(data('document.querySelectorAll(".analytics-b0-runs").length'), 1);
    assert.equal(js('document.activeElement?.getAttribute("data-testid")'), 'analytics-b0-open');
  });
  await check('preview-is-local-apply-and-refresh-restore-title-only', async () => {
    openAsset(); b('fill', control('analytics-b0-title-input'), 'B0 键盘与恢复样例');
    click('analytics-b0-preview'); assert.equal(text('analytics-b0-title'), originalTitle);
    assert.ok(text('analytics-b0-preview-panel').includes('B0 键盘与恢复样例'));
    click('analytics-b0-apply');
    const saved = data(`JSON.parse(localStorage.getItem(${JSON.stringify(TITLE_STORAGE_KEY)}))`);
    assert.deepEqual(saved, { schema_version: 'analytics-b0-ui/v1', title: 'B0 键盘与恢复样例' });
    b('reload'); openAsset(); assert.equal(text('analytics-b0-title'), 'B0 键盘与恢复样例');
  });
  await check('unsaved-exit-is-explicit-and-focus-returns', async () => {
    b('fill', control('analytics-b0-title-input'), '未应用，不应保存'); b('press', 'Escape');
    assert.equal(data('document.querySelector("dialog.analytics-b0-dialog").open'), true);
    assert.ok(text('analytics-b0-close-confirm').includes('放弃本次修改'));
    const snapshot = b('snapshot', '-i');
    const discard = snapshot.match(/(@e\d+) \[button\] "放弃草稿并返回"/);
    assert.ok(discard); b('click', discard[1]);
    assert.equal(data('document.querySelector("dialog.analytics-b0-dialog").open'), false);
    assert.equal(js('document.activeElement?.getAttribute("data-testid")'), 'analytics-b0-open');
    openAsset(); assert.equal(js('document.querySelector("#analytics-b0-draft").value'), 'B0 键盘与恢复样例');
  });
  await check('three-viewports-touch-targets-and-keyboard-trap', async () => {
    report.viewports = [];
    for (const size of ['1440x1000', '768x1024', '390x844']) {
      report.active_viewport = size;
      b('viewport', size);
      const layout = data(`(()=>{const d=document.querySelector('dialog.analytics-b0-dialog');const r=d.getBoundingClientRect();return {viewport:innerWidth,width:r.width,left:r.left,right:r.right,overflow:d.scrollWidth>d.clientWidth+1,controls:Array.from(d.querySelectorAll('button,input,a')).filter(e=>!e.disabled).map(e=>({label:e.textContent||e.getAttribute('aria-label')||'input',height:e.getBoundingClientRect().height})),logo:getComputedStyle(d.querySelector('.analytics-b0-logo')).aspectRatio}})()`);
      assert.equal(layout.overflow, false); assert.ok(layout.left >= 0 && layout.right <= layout.viewport);
      assert.ok(layout.controls.every(c => c.height >= 44), JSON.stringify(layout.controls));
      assert.equal(layout.logo, '249 / 45');
      for (let step = 0; step < layout.controls.length + 2; step++) {
        b('press', 'Tab');
        assert.equal(data('document.querySelector("dialog.analytics-b0-dialog").contains(document.activeElement)'), true);
        assert.ok(Number.parseFloat(js('getComputedStyle(document.activeElement).outlineWidth')) >= 2);
      }
      for (let step = 0; step < layout.controls.length + 2; step++) {
        b('press', 'Shift+Tab');
        assert.equal(data('document.querySelector("dialog.analytics-b0-dialog").contains(document.activeElement)'), true);
      }
      js('document.querySelector("dialog.analytics-b0-dialog").scrollTop=0');
      screenshot(`asset-${size}`); report.viewports.push(layout);
    }
    delete report.active_viewport;
  });
  await check('complete-condition-roundtrip-refresh-history-and-old-filter-isolation', async () => {
    b('viewport', '1440x1000');
    js(`localStorage.setItem(${JSON.stringify(oldFilterKey)},JSON.stringify({channel:'OLD_CHANNEL',date:'1999-01-01,1999-02-01',observation_days:30}))`);
    click('analytics-b0-board-sample');
    assert.equal(b('url').trim(), 'http://127.0.0.1:4318' + BOARD_SAMPLE_PATH);
    const assertBoard = () => {
      assert.deepEqual(JSON.parse(text('b0-board-context')), BOARD_SAMPLE);
      assert.equal(text('b0-board-digest'), BOARD_SAMPLE_DIGEST);
      assert.equal(data('document.scripts.length'), 0);
      assert.equal(data('document.documentElement.scrollWidth > innerWidth'), false);
    };
    assertBoard(); b('reload'); assertBoard();
    click('b0-board-return'); openAsset();
    assert.equal(text('analytics-b0-title'), 'B0 键盘与恢复样例');
    b('back'); assertBoard(); b('forward'); openAsset();
    assert.equal(text('analytics-b0-title'), 'B0 键盘与恢复样例');
    click('analytics-b0-close');
    assert.equal(runCount(), 0);
    // Test the same reference without the synthetic legacy state too.
    js(`localStorage.removeItem(${JSON.stringify(oldFilterKey)})`);
    b('goto', 'http://127.0.0.1:4318' + BOARD_SAMPLE_PATH); assertBoard(); screenshot('board-condition-roundtrip');
    click('b0-board-return');
  });
  assert.equal(runCount(), 0); report.business_runs_created = 0; report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL'; report.error = String(error.message).slice(0, 1000); process.exitCode = 1;
} finally {
  if (paused) process.kill(current.supervisorPid, 'SIGCONT');
  if (savedPrefs) {
    try {
      b('goto', 'http://127.0.0.1:4318/');
      for (const [key, value] of [[TITLE_STORAGE_KEY, savedPrefs.title], [oldFilterKey, savedPrefs.oldFilter]]) {
        js(value === null ? `localStorage.removeItem(${JSON.stringify(key)})` : `localStorage.setItem(${JSON.stringify(key)},${JSON.stringify(value)})`);
      }
      b('reload'); b('viewport', '1440x1000'); report.ui_preferences_restored = true;
    } catch { report.ui_preferences_restored = false; report.status = 'FAIL'; process.exitCode = 1; }
  }
  db.close(); report.completed_at = new Date().toISOString();
  const path = join(runtime, `asset-ui-${Date.now()}.json`);
  await writeFile(path, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ status: report.status, error: report.error, tests: report.tests, screenshots: report.screenshots,
    ui_preferences_restored: report.ui_preferences_restored, report_path: path }));
}
