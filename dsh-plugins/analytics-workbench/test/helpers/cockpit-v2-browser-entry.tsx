/** Disposable browser fixture: production components and clients, synthetic workspace only. */
import { createRoot } from 'react-dom/client';
import { LibraryCockpitPanel } from '../../src/client/cockpit-workspace.tsx';
import { createLibraryBoardClient } from '../../src/client/library-board-client.mjs';
import { createFreeHtmlLibraryStore } from '../../src/client/free-html-library/store.mjs';
import { createLivePageAdapters } from '../../src/client/free-html-library/live-adapters.mjs';
import { createCockpitDelivery } from '../../src/client/cockpit-delivery.mjs';

const themeSource = { subscribe: () => () => {}, getSnapshot: () => 'light' as const };
const files = {
  'native_session': {
    'weekly-review.html': `<!doctype html><html><head><title>九月经营回顾</title><style>
      body{margin:0;font:14px/1.7 "PingFang SC",sans-serif;color:#202020;background:#fff}
      main{max-width:920px;margin:auto;padding:48px 44px}.eyebrow{font-size:11px;letter-spacing:.12em;color:#888}
      h1{font-size:32px;line-height:1.35;font-weight:550;margin:18px 0}p{color:#666}
      .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin:36px 0;padding:24px 0;border-top:1px solid #eee;border-bottom:1px solid #eee}
      .metrics strong{display:block;font-size:28px;font-weight:500}.metrics small{color:#888}
      h2{font-size:18px;font-weight:500;margin-top:30px}.note{border-left:3px solid #f2642e;padding-left:18px}
      @media(max-width:500px){main{padding:28px 22px}h1{font-size:25px}.metrics{gap:12px}.metrics strong{font-size:22px}}
      </style><script>window.importConfig = {label: 'ordered'};</script><script src="setup.js"></script></head><body><main><div class="eyebrow">MONTHLY REVIEW / SYNTHETIC</div>
      <h1 data-shine-node="report_title">九月经营回顾</h1>
      <p data-shine-node="report_intro">从交付到行动，让本月的经营变化清晰可见。</p>
      <section class="metrics"><div><small>合成订单</small><strong>1,280</strong></div><div><small>合成渠道</small><strong>06</strong></div><div><small>合成覆盖</small><strong>92%</strong></div></section>
      <h2 data-shine-node="section_one">本周观察</h2><p class="note" data-shine-node="finding">渠道结构保持稳定，下一步核对新增客户的复购表现。</p>
      <h2 data-shine-node="section_two">本周观察</h2><p data-shine-node="next_step">记录关键变化，确认口径后再制定下一阶段行动。</p>
      <p><a href="#details">查看页内说明</a></p><p id="details">所有数字均为隔离测试样例，未绑定业务结果。</p></main></body></html>`,
    'weekly.csv': 'channel,orders\nsynthetic,1280\n',
    'summary.pdf': '%PDF synthetic fixture',
    'setup.js': "document.body.dataset.importOrder = window.importConfig.label;",
  },
  'other_session': { 'other.html': '<h1 data-shine-node="other">另一会话的交付</h1>' },
};
const controls = { failList: false, eof: true, readDelay: 0, loseConfirm: false, cancelFails: false };
const calls: Array<{ operation: string; payload: unknown }> = [];
let nativeMessages = 0;
const library = createLibraryBoardClient(async (_channel, operation, payload) => {
  calls.push({ operation, payload });
  const reply = await fetch('/fixture/board', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ operation, payload }) });
  return reply.json();
}, { editNative: async () => { nativeMessages++; } });
const adapters = createLivePageAdapters({ documentsHttp: { base: location.origin, fetchImpl: async (url: string, options: RequestInit) => {
  if (controls.cancelFails && url.endsWith('/cancel')) throw new Error('隔离取消失败');
  const reply = await fetch(url, options);
  if (controls.loseConfirm && url.endsWith('/confirm')) { controls.loseConfirm = false; await reply.text(); throw new Error('隔离：写入后回执丢失'); }
  return reply;
} } });
const pageStore = createFreeHtmlLibraryStore({ adapters });
const delivery = createCockpitDelivery({
  listDir: async (sessionId: string, path: string) => {
    if (controls.failList) throw new Error('isolated list failure');
    return { path, entries: Object.keys(files[sessionId as keyof typeof files] ?? {}).map(name => ({ name, type: 'file' })) };
  },
  read: async (sessionId: string, path: string) => {
    if (controls.readDelay) await new Promise(resolve => setTimeout(resolve, controls.readDelay));
    const text = (files[sessionId as keyof typeof files] as Record<string, string> | undefined)?.[path];
    return { text, eof: controls.eof };
  },
});
delivery.captureSource({ ids: ['older_session', 'native_session'], byId: {
  older_session: { id: 'older_session', retainedBy: {} },
  native_session: { id: 'native_session', retainedBy: { mainView: 1 } },
} });
Object.assign(window, { cockpitFixture: { library, pageStore, delivery, controls, calls,
  nativeMessages: () => nativeMessages, setMounted } });
const root = createRoot(document.getElementById('root')!);
function setMounted(mounted: boolean) { root.render(mounted ? <LibraryCockpitPanel library={library} pageStore={pageStore}
  delivery={delivery} themeSource={themeSource} initialSurface="pages" goConversation={() => { document.body.dataset.left = 'true'; }}
  openWorkspaceFile={product => { document.body.dataset.openedFile = String(product.path); }} /> : null); }
setMounted(true);
