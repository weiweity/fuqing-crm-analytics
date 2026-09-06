/** Offline compiled-component DOM evidence. Not a native session/event journey. */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { join, resolve, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CARD_CASES, loadCardHarness } from '../../dsh-plugins/analytics-workbench/test/tool-card-harness.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const [browse, tab, ...extra] = process.argv.slice(2);
assert.ok(isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length,
  'Usage: node tool-card-dom-smoke.mjs /absolute/browse <owned-blank-tab-id>');
const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 4 * 1024 * 1024 });
b('tab', tab);
assert.equal(b('url').trim(), 'about:blank', 'Refuse to overwrite a nonblank page');
const harness = await loadCardHarness();
const output = await mkdtemp(join(root, '.context/dsh-b0/tool-card-dom-'));
const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>B0 工具卡组件状态核验</title><style>
${harness.css}
body { margin:0; background:#f5f6f8; color:#182331; font-family:system-ui,sans-serif; }
main { max-width:1000px; margin:auto; padding:16px; }
h1 { font-size:20px; } h2 { font-size:14px; margin:0 0 8px; }
.case { margin:12px 0; padding:12px; background:white; border:1px solid #d4dbe4; border-radius:10px; }
</style><main><h1>B0 工具卡 · 8 种组件状态</h1>
<p>COMPONENT DOM / SYNTHETIC / NO RUNTIME<br>真实编译组件与样式，非原生会话故障链路。</p>
${CARD_CASES.map(row => `<section class="case" id="${row.id}"><h2>${row.label}</h2>${harness.render(row.block)}</section>`).join('\n')}
</main></html>`;
const page = join(output, 'index.html');
await writeFile(page, html);
const report = { kind: 'B0_COMPILED_COMPONENT_DOM', started_at: new Date().toISOString(),
  client_sha256: harness.client_sha256, native_session: false, synthetic: true, output, viewports: [] };
try {
  b('load-html', page);
  for (const viewport of ['1440x1200', '390x844']) {
    b('viewport', viewport);
    const checks = JSON.parse(b('js', `JSON.stringify((() => {
      const cases = ${JSON.stringify(CARD_CASES.map(({id, expected, success}) => ({id, expected, success})))};
      return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
        interactive: document.querySelectorAll('button,a,input,textarea,script,img').length,
        successCards: document.querySelectorAll('[data-testid="analytics-b0-tool-result"]').length,
        states: cases.map(row => {
          const section = document.getElementById(row.id);
          section.scrollIntoView({block:'center'});
          const card = section.lastElementChild, rect = card.getBoundingClientRect(), style = getComputedStyle(card);
          return { id:row.id, text:section.innerText.includes(row.expected),
            visible:rect.width > 0 && rect.height > 0 && rect.top < innerHeight && rect.bottom > 0 && style.display !== 'none' && style.visibility !== 'hidden',
            fits: rect.left >= 0 && rect.right <= innerWidth && card.scrollWidth <= card.clientWidth,
            correctRole: row.success ? !card.hasAttribute('role') : card.getAttribute('role') === 'status' };
        }) };
    })())`).trim());
    assert.equal(checks.width, Number(viewport.split('x')[0]));
    assert.ok(checks.scrollWidth <= checks.width, 'Horizontal page overflow');
    assert.equal(checks.interactive, 0); assert.equal(checks.successCards, 1);
    assert.equal(checks.states.length, 8);
    for (const state of checks.states) for (const key of ['text', 'visible', 'fits', 'correctRole']) assert.equal(state[key], true, `${viewport}/${state.id}/${key}`);
    b('js', 'window.scrollTo(0,0)');
    const screenshot = join(output, `${viewport}.png`);
    b('screenshot', screenshot);
    report.viewports.push({ viewport, checks, screenshot });
  }
  report.status = 'PASS';
} catch (error) { report.status = 'FAIL'; report.error = error.message; throw error; }
finally {
  report.finished_at = new Date().toISOString();
  await writeFile(join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
}
