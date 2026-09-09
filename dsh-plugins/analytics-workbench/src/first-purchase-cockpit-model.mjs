/** Decode/display a private first-purchase SNAPSHOT cockpit. No metric compute, no HTTP. */
import { formatEmptyReason, formatRatioPercent } from './query-format.mjs';
import { COCKPIT_CSS, COCKPIT_KEYBOARD } from './cockpit-model.mjs';

export { COCKPIT_CSS, COCKPIT_KEYBOARD };

export const COCKPIT_SCHEMA = 'analytics-first-purchase-cockpit/v1';
export const FILTER_SCHEMA = 'analytics-first-purchase-cockpit-filters/v1';
export const FINITE_MOCK = true;
export const HTTP_API = 'NOT_CONNECTED';

export const COPY = Object.freeze({
  heading: '我的首购驾驶舱',
  empty: '从已保存首购分析添加',
  snapshot: '历史快照',
  preview: '预览未保存，不会写入驾驶舱',
  save: '保存',
  undo: '撤销',
  add: '从已保存分析添加',
  copy: '复制板块',
  remove: '移除板块',
  noSession: '无活动会话、模型不可用时仍可查看已保存驾驶舱',
  synthetic: 'SYNTHETIC · 有限 mock，不是真实业务数据。',
  unauthorized: '驾驶舱不存在或当前身份不可见。',
  cardError: '该板块无法识别或版本不支持；其他板块不受影响。',
  http: 'HTTP/OpenAPI 未接通',
  finiteMock: 'finite mock',
  pinned: '固定历史快照',
});

const OPAQUE = /^[A-Za-z0-9_.:-]{1,128}$/;
const ANALYSIS_ID = /^analysis_[A-Za-z0-9_.:-]{1,118}$/;

export function decodeDashboard(value) {
  if (!value || typeof value !== 'object' || value.schema_version !== COCKPIT_SCHEMA) return null;
  if (value.visibility !== 'PRIVATE' || value.finite_mock !== true || value.http_api !== HTTP_API) return null;
  if (!Array.isArray(value.cards)) return null;
  return value;
}

export function decodeDashboardList(value) {
  if (!Array.isArray(value)) return null;
  return value.every(item => item?.schema_version === COCKPIT_SCHEMA && typeof item.dashboard_id === 'string')
    ? value : null;
}

export function buildCockpitView({
  dashboard = null,
  list = null,
  error = null,
  sessionId = null,
  modelAvailable = false,
  selectedCardId = null,
} = {}) {
  const decoded = dashboard == null ? null : decodeDashboard(dashboard);
  const items = list == null ? null : decodeDashboardList(list);
  const base = {
    heading: COPY.heading,
    sessionId: sessionId ?? null,
    modelAvailable: modelAvailable === true,
    keyboard: COCKPIT_KEYBOARD,
    http: COPY.http,
    noSession: COPY.noSession,
  };
  if (error && (error.status === 403 || error.status === 404)) {
    return { ...base, kind: 'error', message: COPY.unauthorized };
  }
  if (dashboard != null && decoded == null) {
    return { ...base, kind: 'error', message: COPY.cardError };
  }
  if (decoded) {
    const cards = decoded.cards.map(card => {
      if (card.source_status === 'UNAVAILABLE' || !OPAQUE.test(card.card_id || '')) {
        return { kind: 'error', card_id: card.card_id ?? null, message: COPY.cardError, affected: false };
      }
      if (!ANALYSIS_ID.test(card.analysis_ref?.analysis_id || '')) {
        return { kind: 'error', card_id: card.card_id, message: COPY.cardError, affected: false };
      }
      const conversion = card.facts?.products?.[0]
        ? formatRatioPercent(card.facts.products[0].finished_conversion_ratio)
        : '—';
      const empty = formatEmptyReason(card.facts?.products?.[0]?.empty_reason ?? null) || { code: null, text: '' };
      return {
        kind: 'ok',
        card_id: card.card_id,
        title: card.display_overrides?.title || COPY.snapshot,
        badge: COPY.pinned,
        plugin: card.plugin_ref?.type || 'TABLE',
        selected: selectedCardId === card.card_id,
        affected: Array.isArray(decoded.affected_card_ids) && decoded.affected_card_ids.includes(card.card_id),
        layout: card.layout,
        condition: `N=${card.facts?.observation_days ?? ''}`,
        totals: `成熟 ${card.facts?.cohort_mature_count ?? 0} · 正装转化 ${conversion}`,
        empty,
        evidence: `run ${card.snapshot?.run_id ?? ''}`,
        localFilterNote: null,
      };
    });
    return {
      ...base,
      kind: 'board',
      preview: decoded.preview === true,
      version: decoded.version,
      previewHint: decoded.preview ? COPY.preview : null,
      cards,
      synthetic: COPY.synthetic,
    };
  }
  if (items && items.length === 0) return { ...base, kind: 'empty', message: COPY.empty };
  if (items) {
    return {
      ...base,
      kind: 'list',
      items: items.map(item => ({
        dashboard_id: item.dashboard_id,
        title: item.title,
        version: item.version,
        summary: `${item.card_count} 个板块`,
      })),
    };
  }
  return { ...base, kind: 'empty', message: COPY.empty };
}
