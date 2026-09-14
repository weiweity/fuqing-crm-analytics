/** Isolated browser harness: production canvas/client + real native RPC; not the full DSH shell. */
import { createRoot } from 'react-dom/client';
import { LibraryCockpitPanel } from '../../src/client/library-workspace.tsx';
import { createLibraryBoardClient } from '../../src/client/library-board-client.mjs';
import { callBoardConnection } from '../../src/board-spec/connection-call.mjs';

let counter = 0;
const call = async (channel: string, operation: string, payload: unknown, signal?: AbortSignal) => {
  const rpcId = `browser-layout-${++counter}`;
  const response = await fetch(`${channel}/${operation}`, { method: 'POST', signal,
    credentials: 'same-origin', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ type: 'client-request', rpcId, method: operation, payload }) });
  if (!response.ok) throw new Error(`隔离服务 HTTP ${response.status}`);
  const body = await response.json();
  if (body.rpcId !== rpcId || body.type !== 'server-response') throw new Error('RPC 回执不匹配');
  return body.result;
};
const library = createLibraryBoardClient((channel, operation, payload, signal) => callBoardConnection({ call }, channel, operation, payload, signal));
createRoot(document.getElementById('root')!).render(<>
  <p style={{ padding: '12px 20px', margin: 0 }}>隔离合成布局验收 · 真实插件画布 / 原生 RPC / SQLite · 非完整 DSH 外壳、无模型调用</p>
  <LibraryCockpitPanel library={library} themeSource={{ subscribe: () => () => {}, getSnapshot: () => 'light' }}
    goConversation={() => { /* This harness deliberately contains no imitation of native conversation. */ }} />
  <details><summary>隔离手势事件证据</summary><pre id="gesture-events" /></details>
</>);
const trace: string[] = [];
let recording = false;
for (const type of ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'gotpointercapture', 'lostpointercapture']) {
  window.addEventListener(type, event => {
    const pointer = event as PointerEvent;
    if (type === 'pointerdown') recording = Boolean((event.target as Element)?.closest?.('[data-layout-mode]'));
    if (!recording) return;
    trace.push(`${type}: id=${pointer.pointerId} buttons=${pointer.buttons} trusted=${pointer.isTrusted} target=${(event.target as Element)?.tagName}`);
    if (trace.length > 15) trace.shift();
    const output = document.getElementById('gesture-events'); if (output) output.textContent = trace.join('\n');
  }, true);
}
window.addEventListener('pagehide', () => library.dispose(), { once: true });
