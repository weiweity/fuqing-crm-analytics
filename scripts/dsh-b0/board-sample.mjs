/** UI-B06 transport specimen, NOT a business run resolver or old BI adapter.
 * One immutable synthetic condition envelope; no query, model, storage or IO.
 */
import { createHash } from 'node:crypto';

export const BOARD_SAMPLE_PATH = '/b0/board-sample?ref=b0-condition-specimen-v1';
export const BOARD_SAMPLE = Object.freeze({
  schema_version: 'ui-b06-condition-specimen/v1',
  answer_mode: 'NOT_EXECUTED', data_source: 'SYNTHETIC_CONTRACT_ONLY',
  source_ref: 'fixture-no-business-run', return_path: '/',
  query_ref: { id: 'contract-only-channel-repeat', version: 1 },
  metric_refs: [{ id: 'contract-only-repeat-n-days', version: 1 }],
  filters: {
    schema_version: 'filter-specimen/v1',
    cohort_window: { mode: 'FIXED', start: '2026-01-01', end: '2026-02-01', end_exclusive: true },
    resolved_cohort_start: '2026-01-01T00:00:00+08:00',
    resolved_cohort_end: '2026-02-01T00:00:00+08:00',
    observation_days: 90,
    data_snapshot_ref: { id: 'synthetic-contract-snapshot', version: 1 },
    as_of: '2026-09-01T00:00:00+08:00', timezone: 'Asia/Shanghai',
    channel_ids: ['synthetic-channel-a'], product_ids: [], cohort_ref: null,
    exclude_low_price: false, comparison: { mode: 'NONE' },
  },
  facts: null, evidence_digest: null,
  limitations: ['Only condition roundtrip is demonstrated; these dates do not describe the B0 query fixture.',
    'No mature denominator, business run, approval, old private BI or business result is claimed.'],
});
// Nested objects are immutable too: this is a fixed specimen, not an editor.
function freeze(value) { if (value && typeof value === 'object') { for (const child of Object.values(value)) freeze(child); Object.freeze(value); } }
freeze(BOARD_SAMPLE);
export const BOARD_SAMPLE_DIGEST = createHash('sha256').update(JSON.stringify(BOARD_SAMPLE)).digest('hex');
export function resolveBoardSample(rawPath) {
  return rawPath === BOARD_SAMPLE_PATH ? structuredClone(BOARD_SAMPLE) : null;
}
const escape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
export function boardSampleHtml() {
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/svg+xml" href="/favicon.svg"><title>伸美 · B0 条件往返样例</title>
<style>body{font:16px/1.65 system-ui;margin:24px auto;padding:0 20px;max-width:850px;color:CanvasText;background:Canvas;color-scheme:light dark}a{display:inline-block;padding:10px 4px;min-height:24px}a:focus-visible{outline:2px solid currentColor;outline-offset:3px}pre{padding:16px;border:1px solid;white-space:pre-wrap;overflow-wrap:anywhere}small{overflow-wrap:anywhere}</style>
<h1>标准看板 · B0 条件往返样例</h1><p><strong>CONTRACT ONLY / SYNTHETIC / 未执行查询</strong></p>
<p>这是独立 HTML 接缝样例，不加载旧 Vue App、Pinia 或 useFilterSync。旧筛选不会覆盖下列条件；不是旧私有 BI，也不是当前聊天的计算结果。</p>
<a data-testid="b0-board-return" href="/">返回原生工作台</a>
<p>只传固定样例引用；不接收任意返回地址、条件覆盖、文件路径或凭据。返回后由原生插件选择本工作区已登记的主会话。</p>
<h2>完整条件与来源</h2><small data-testid="b0-board-digest">${BOARD_SAMPLE_DIGEST}</small>
<pre data-testid="b0-board-context">${escape(JSON.stringify(BOARD_SAMPLE, null, 2))}</pre>
<p>无事实数值、分母或经营批准。真正的 run → 同条件标准 BI 解析器留在 E-T4；不以这个样例代替。</p></html>`;
}
