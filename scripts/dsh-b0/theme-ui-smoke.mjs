/** Read-only presentation check after native seven-question verification.
 * Uses the already-authorized browse tab; restores media and viewport in finally.
 */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { resolve, join, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const [target, browse, tab, ...extra] = process.argv.slice(2);
assert.ok(target && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length,
  'Usage: node theme-ui-smoke.mjs <current-runtime> /absolute/browse <owned-tab-id>');
const runtime = resolve(target);
const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
assert.equal(runtime, current.runtime);
assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
const rows = () => db.prepare('SELECT run_id,status FROM runs ORDER BY rowid').all();
const before = rows();
assert.deepEqual(before.map(r => r.status), ['SUCCEEDED','SUCCEEDED','CANCELLED','SUCCEEDED','FAILED','FAILED','SUCCEEDED']);
const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 1024 * 1024 }).trim();
const data = expression => JSON.parse(b('js', expression));
const captureId = Date.now();
const report = { kind: 'B0_THEME_AND_NATIVE_CARDS', started_at: new Date().toISOString(), checks: [], screenshots: [], status: 'RUNNING' };
report.plugin_hashes = Object.fromEntries(await Promise.all(['index.js','tool.js','skills.js','client.js']
  .map(async name => [name, createHash('sha256').update(await readFile(join(current.plugin,'lib',name))).digest('hex')])));
function screenshot(name) {
  const path = join(runtime, `${name}-${captureId}.png`); b('screenshot', path); report.screenshots.push(path);
}
function contrast(fg, bg) {
  const luminance = value => value.match(/[\d.]+/g).slice(0,3).map(Number).map(x => x / 255)
    .map(x => x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4)
    .reduce((n,x,i) => n + x * [0.2126,0.7152,0.0722][i],0);
  const a = luminance(fg), c = luminance(bg);
  return (Math.max(a,c) + 0.05) / (Math.min(a,c) + 0.05);
}
try {
  b('tab',tab); assert.equal(b('url'),'http://127.0.0.1:4318/');
  if (data('Boolean(document.querySelector("dialog.analytics-b0-dialog")?.open)')) b('click','[data-testid="analytics-b0-close"]');
  // Native collapsed groups keep DOM children measurable. Require a genuinely
  // displayed result, not merely a hidden element's non-zero layout box.
  if (!data('Array.from(document.querySelectorAll(".analytics-b0-card")).at(-1)?.checkVisibility()')) {
    const calls = [...b('snapshot','-i').matchAll(/(@e\d+) \[button\] "1 tool call"/g)];
    assert.equal(calls.length,4); b('click',calls.at(-1)[1]);
  }
  for (const theme of ['light','dark']) {
    b('cdp','Emulation.setEmulatedMedia',JSON.stringify({ features: [
      { name: 'prefers-color-scheme', value: theme }, { name: 'prefers-reduced-motion', value: 'reduce' },
    ] }));
    for (const viewport of ['1440x1000','768x1024','390x844']) {
      b('viewport',viewport);
      b('js',`Array.from(document.querySelectorAll('.analytics-b0-card')).at(-1).scrollIntoView({block:'center',behavior:'instant'})`);
      const layout = data(`(()=>{const dock=document.querySelector('.analytics-b0-runs');const r=dock.getBoundingClientRect();const s=getComputedStyle(dock);return {scheme:getComputedStyle(document.documentElement).colorScheme,reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,viewport:innerWidth,pageOverflow:document.documentElement.scrollWidth>innerWidth,left:r.left,right:r.right,top:r.top,overflow:dock.scrollWidth>dock.clientWidth+1,bg:s.backgroundColor,fg:s.color,animation:s.animationName,transition:s.transitionDuration,cards:Array.from(document.querySelectorAll('.analytics-b0-card')).map(e=>({overflow:e.scrollWidth>e.clientWidth+1,text:e.textContent,visible:e.checkVisibility(),rect:e.getBoundingClientRect().toJSON()}))}})()`);
      assert.equal(layout.scheme,theme); assert.equal(layout.reduced,true);
      assert.equal(layout.pageOverflow,false); assert.equal(layout.overflow,false);
      assert.ok(layout.left >= 0 && layout.right <= layout.viewport);
      assert.equal(layout.cards.length,4); assert.ok(layout.cards.every(c => !c.overflow && c.text.includes('25%')));
      const latest = layout.cards.at(-1);
      assert.equal(latest.visible,true); assert.ok(latest.rect.top >= 74 && latest.rect.bottom <= layout.top);
      assert.ok(latest.rect.left >= 0 && latest.rect.right <= layout.viewport);
      assert.equal(layout.animation,'none'); assert.equal(layout.transition,'0s');
      layout.contrast = contrast(layout.fg,layout.bg); assert.ok(layout.contrast >= 4.5);
      screenshot(`native-cards-${theme}-${viewport}`);
      report.checks.push({ theme, viewport, ...layout });
    }
    b('viewport','1440x1000'); b('click','[data-testid="analytics-b0-open"]');
    const asset = data(`(()=>{const d=document.querySelector('dialog.analytics-b0-dialog');const s=getComputedStyle(d);return {bg:s.backgroundColor,fg:s.color,secondary:getComputedStyle(d.querySelector('small')).color,animation:s.animationName,transition:s.transitionDuration,logo:getComputedStyle(d.querySelector('.analytics-b0-logo')).aspectRatio}})()`);
    asset.primary_contrast = contrast(asset.fg,asset.bg); asset.secondary_contrast = contrast(asset.secondary,asset.bg);
    assert.ok(asset.primary_contrast >= 4.5 && asset.secondary_contrast >= 4.5);
    assert.equal(asset.logo,'249 / 45'); assert.equal(asset.animation,'none'); assert.equal(asset.transition,'0s');
    screenshot(`asset-theme-${theme}`); report.checks.push({ theme, asset });
    b('click','[data-testid="analytics-b0-close"]');
  }
  assert.deepEqual(rows(),before); report.new_business_runs = 0; report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL'; report.error = String(error.message).slice(0,1000); process.exitCode = 1;
} finally {
  try {
    if (data('Boolean(document.querySelector("dialog.analytics-b0-dialog")?.open)')) b('click','[data-testid="analytics-b0-close"]');
    b('cdp','Emulation.setEmulatedMedia','{"features":[]}'); b('viewport','1440x1000');
    report.emulation_restored = true;
  } catch { report.emulation_restored = false; report.status = 'FAIL'; process.exitCode = 1; }
  db.close(); report.completed_at = new Date().toISOString();
  const path = join(runtime,`theme-ui-${Date.now()}.json`);
  await writeFile(path,JSON.stringify(report,null,2)+'\n',{ flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ status: report.status, error: report.error, checks: report.checks.length,
    screenshots: report.screenshots, emulation_restored: report.emulation_restored, report_path: path }));
}
