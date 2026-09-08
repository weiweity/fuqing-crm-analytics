/** Browser driver for native-query-assets. Real worker SQL; no console-fetch substitute. */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { join, resolve, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseComposer, waitUntil } from './native-state-smoke.mjs';
import { QUESTIONS, QUERY_CARD_EXPECT, QUERY_SESSION_IDS, cardShowsQuery } from './query-scenario.mjs';

const invoked = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (!invoked) { /* imported by unit tests */ }
else await main();

async function main() {
  const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
  const [namedRuntime, browse, tab, ...extra] = process.argv.slice(2);
  assert.ok(isAbsolute(namedRuntime ?? '') && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length,
    'Usage: node native-query-assets-smoke.mjs /absolute/current-runtime /absolute/browse <owned-tab-id>');
  const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
  const runtime = resolve(namedRuntime);
  assert.equal(current.runtime, runtime);
  assert.equal(current.verificationScenario, 'native-query-assets');
  const config = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
  assert.ok(Array.isArray(config.asset_capabilities));
  const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 4 * 1024 * 1024 });
  const js = expression => b('js', expression).trim();
  const data = expression => JSON.parse(js(expression));
  const report = { kind: 'QUERY_NATIVE_ASSETS', runtime, started_at: new Date().toISOString(), tests: [], screenshots: [] };
  const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
  const analyses = new DatabaseSync(join(runtime, 'analyses/analyses.sqlite3'), { readOnly: true });
  const boards = new DatabaseSync(join(runtime, 'cockpit/cockpit.sqlite3'), { readOnly: true });
  const counts = () => ({
    runs: db.prepare('SELECT count(*) AS n FROM runs').get().n,
    workers: db.prepare('SELECT count(*) AS n FROM worker_executions').get().n,
    analyses: analyses.prepare('SELECT count(*) AS n FROM analyses').get().n,
    dashboards: boards.prepare('SELECT count(*) AS n FROM dashboards').get().n,
    idempotency: boards.prepare('SELECT count(*) AS n FROM idempotency').get().n,
  });
  async function waitFor(check, milliseconds = 60000) {
    const ok = await waitUntil(check, { budgetMs: milliseconds });
    if (!ok) throw new Error('native-query-assets deadline expired');
  }
  function screenshot(name) {
    const path = join(runtime, `${name}.png`);
    b('screenshot', path);
    report.screenshots.push(path);
  }
  function check(name, fn) {
    fn();
    report.tests.push({ name, status: 'PASS' });
  }
  function expandTools() {
    for (let i = 0; i < 8; i++) {
      const match = b('snapshot', '-i').match(/(@e\d+) \[button\] "\d+ tool calls?"(?! \[expanded\])/);
      if (!match) return;
      b('click', match[1]);
    }
  }
  function cardState() {
    return data(`({
      cards: [...document.querySelectorAll('.analytics-query-card,[data-testid="analytics-query-tool-result"]')].map(e => e.textContent),
      days: [...document.querySelectorAll('[data-observation-days]')].map(e => e.getAttribute('data-observation-days')),
    })`);
  }
  function clickTestId(testId) {
    const present = js(`Boolean(document.querySelector('[data-testid="${testId}"]'))`);
    assert.equal(present, 'true', `missing visible control ${testId}`);
    try {
      b('click', `[data-testid="${testId}"]`);
    } catch {
      js(`document.querySelector('[data-testid="${testId}"]').click()`);
    }
  }
  async function sendWhenReady(text) {
    await waitFor(() => parseComposer(b('snapshot', '-i')).readyToFill);
    const before = parseComposer(b('snapshot', '-i'));
    assert.ok(before.readyToFill && before.inputRef && before.sendRef, 'Native composer not ready');
    b('fill', before.inputRef, text);
    await waitFor(() => parseComposer(b('snapshot', '-i')).sendEnabled);
    const after = parseComposer(b('snapshot', '-i'));
    assert.ok(after.sendEnabled && after.sendRef, 'Native send control is not enabled');
    b('click', after.sendRef);
  }

  b('tab', tab);
  b('goto', 'http://127.0.0.1:4318/');
  b('viewport', '1440x1000');
  await waitFor(() => data('Boolean(document.querySelector("[data-testid=\\"analytics-b0-open\\"]"))'));

  check('fixed-entry-opens-empty-board', () => {
    b('click', '[data-testid="analytics-b0-open"]');
    assert.equal(data('document.querySelector("[data-testid=\\"analytics-b0-dialog\\"]")?.getAttribute("data-http")'), 'CONNECTED');
    assert.ok(js('document.querySelector("[data-testid=\\"analytics-cockpit-empty\\"]")?.textContent')?.includes('从已保存分析添加'));
    assert.doesNotMatch(js('document.querySelector("[data-testid=\\"analytics-b0-dialog\\"]")?.innerText ?? ""'), /25%/);
    screenshot('assets-empty-board');
    b('click', '[data-testid="analytics-b0-close"]');
  });

  const before = counts();
  await sendWhenReady(QUESTIONS[0]);
  await waitFor(() => db.prepare("SELECT count(*) AS n FROM runs WHERE status='SUCCEEDED'").get().n >= 1, 90000);
  await waitFor(() => {
    expandTools();
    return data('Boolean(document.querySelector("[data-testid=\\"analytics-query-tool-result\\"]"))');
  }, 90000);
  check('visible-query-card-is-n30', () => {
    assert.equal(cardShowsQuery(cardState(), QUERY_CARD_EXPECT[30]), true);
  });

  clickTestId('analytics-query-save-button');
  await waitFor(() => counts().analyses >= 1, 30000);
  clickTestId('analytics-query-join-button');
  await waitFor(() => counts().dashboards >= 1 && counts().idempotency >= 1, 30000);
  check('save-and-join-use-visible-controls', () => {
    const after = counts();
    assert.ok(after.analyses >= 1, 'save did not persist an analysis');
    assert.ok(after.dashboards >= 1, 'join did not persist a dashboard version');
    assert.ok(after.runs >= before.runs);
  });

  b('click', '[data-testid="analytics-b0-open"]');
  await waitFor(() => js('document.querySelector("[data-testid=\\"analytics-cockpit-grid\\"]")') !== '');
  const beforeCopy = counts();
  const copy = js('Boolean(document.querySelector("[data-action=\\"copy\\"]"))');
  assert.equal(copy, 'true', 'copy control missing on saved board');
  js('document.querySelector("[data-action=\\"copy\\"]").click()');
  await waitFor(() => js('document.querySelector("[data-testid=\\"analytics-cockpit-preview\\"]")') !== '');
  check('copy-preview-does-not-write', () => {
    const afterPreview = counts();
    assert.equal(afterPreview.dashboards, beforeCopy.dashboards);
    assert.equal(afterPreview.idempotency, beforeCopy.idempotency);
    assert.equal(afterPreview.runs, beforeCopy.runs);
  });
  clickTestId('analytics-cockpit-save');
  await waitFor(() => counts().dashboards > beforeCopy.dashboards, 30000);
  screenshot('assets-joined-board');
  b('click', '[data-testid="analytics-b0-close"]');

  const afterSave = counts();
  report.counts = { before, afterSave, sessions: [...QUERY_SESSION_IDS], questions: QUESTIONS };
  report.card_visible = cardShowsQuery(cardState(), QUERY_CARD_EXPECT[30]);
  assert.equal(report.card_visible, true);
  await writeFile(join(runtime, 'native-query-assets-report.json'), JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
  assert.equal(current.verificationScenario, 'native-query-assets');
}
