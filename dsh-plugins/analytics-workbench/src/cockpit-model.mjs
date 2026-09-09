/** Decode/display a private SNAPSHOT cockpit. No metric compute, no HTTP, no session. */
import { formatEmptyReason, formatFenYuan, formatRatioPercent } from './query-format.mjs';
import {
  canEndorse, decodeCompetitionBoardSpec, decodeCompetitionError, decodeCompetitionResultRef,
} from './client/competition-board/decode.mjs';
import { decodeActionDraft, decodeCandidateSet } from './client/competition-actions/transport.mjs';

export {
  canEndorse, decodeCompetitionBoardSpec, decodeCompetitionError, decodeCompetitionResultRef,
};
export { decodeActionDraft, decodeCandidateSet };

export const COCKPIT_SCHEMA = 'analytics-cockpit/v1';
export const FILTER_SCHEMA = 'analytics-cockpit-filters/v1';
export const VISUAL_TABLE = 'analytics-visual-table/v1';
export const QUERY_SCHEMA = 'analytics-channel-followup/v1';
export const JS_MAX_SAFE_INTEGER = 9007199254740991;
export const FINITE_MOCK = true;
export const HTTP_API = 'NOT_CONNECTED';

export const COPY = Object.freeze({
  heading: '我的驾驶舱',
  empty: '从已保存分析添加',
  snapshot: '历史快照',
  preview: '预览未保存，不会写入驾驶舱',
  save: '保存',
  undo: '撤销',
  add: '从已保存分析添加',
  copy: '复制板块',
  remove: '移除板块',
  aiEdit: '让 AI 修改这一块',
  noSession: '无活动会话、模型不可用时仍可查看已保存驾驶舱',
  synthetic: 'SYNTHETIC · 有限 mock，不是真实业务数据。',
  unauthorized: '驾驶舱不存在或当前身份不可见。',
  conflict: '请求、状态或版本已变化，请读取当前驾驶舱后核对。',
  cardError: '该板块无法识别或版本不支持；其他板块不受影响。',
  localFilterNote: '局部筛选仅作展示标注，SNAPSHOT 事实未重算。',
  http: 'HTTP/OpenAPI 未接通',
  finiteMock: 'finite mock',
  pinned: '固定历史快照',
});

export const COCKPIT_KEYBOARD = Object.freeze({
  add: { action: 'add', key: 'a', altKey: true, shiftKey: false, shortcut: 'Alt+A', label: 'Alt+A 从已保存分析添加' },
  copy: { action: 'copy', key: 'd', altKey: true, shiftKey: false, shortcut: 'Alt+D', label: 'Alt+D 复制板块' },
  remove: { action: 'remove', key: 'Backspace', altKey: true, shiftKey: false, shortcut: 'Alt+Backspace', label: 'Alt+Backspace 移除板块' },
});

export const AI_INTENTS = Object.freeze({
  'annotate-live': {
    instruction: '这一块只看直播，其他不动',
    display_overrides: { title: '直播渠道快照' },
    local_filters: { channel_ids: ['A'] },
  },
  'trend-enlarge': {
    instruction: '改成趋势图并放大',
    plugin_ref: { type: 'LINE', version: 'analytics-visual-line/v1' },
    layout_patch: { w: 12, h: 6 },
  },
});

const OPAQUE = /^[A-Za-z0-9_.:-]{1,128}$/;
const SHA = /^[0-9a-f]{64}$/;
const RFC3339 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
const ANALYSIS_ID = /^analysis_[A-Za-z0-9_.:-]{1,118}$/;
const DASHBOARD_KEYS = Object.freeze([
  'schema_version', 'dashboard_id', 'version', 'title', 'owner_id', 'visibility', 'cards',
  'global_filters', 'created_at', 'preview', 'persisted', 'affected_card_ids', 'finite_mock', 'http_api',
]);
const LIST_KEYS = Object.freeze([
  'schema_version', 'dashboard_id', 'version', 'title', 'visibility', 'card_count', 'finite_mock', 'http_api',
]);
const CARD_KEYS = Object.freeze([
  'card_id', 'plugin_ref', 'analysis_ref', 'data_mode', 'layout', 'display_overrides',
  'filter_mapping', 'local_filters', 'snapshot', 'facts', 'filter_hash', 'limitations',
  'effective_spec_hash', 'freshness',
]);
const PLUGIN_KEYS = Object.freeze(['type', 'version']);
const ANALYSIS_REF_KEYS = Object.freeze(['analysis_id', 'version']);
const LAYOUT_KEYS = Object.freeze(['x', 'y', 'w', 'h']);
const SNAPSHOT_KEYS = Object.freeze([
  'run_id', 'evidence_digest', 'resolved_filters', 'data_snapshot_ref', 'as_of',
]);
const FILTER_KEYS = Object.freeze([
  'schema_version', 'query_id', 'query_version', 'metric_id', 'metric_version', 'data_version',
  'hash_version', 'cohort_window_kind', 'resolved_cohort_start', 'resolved_cohort_end',
  'observation_days', 'data_snapshot_ref', 'as_of', 'timezone', 'channel_ids', 'cohort_ref',
  'product_ids', 'exclude_low_price', 'comparison', 'permission_scope', 'data_digest', 'filter_hash',
]);
const COUNT_KEYS = Object.freeze([
  'channel_mature_cohort_count', 'channel_immature_count', 'channel_repeat_count',
  'channel_cross_channel_count', 'channel_repeat_ratio', 'channel_cross_channel_ratio',
  'channel_window_net_paid_minor', 'channel_empty_reason',
]);
const FACT_KEYS = Object.freeze([
  'display_name', 'currency', 'amount_unit', 'amount_precision', 'observation_days', 'channels', 'totals',
]);
const GLOBAL_KEYS = Object.freeze(['schema_version', 'channel_ids']);
const PLUGIN_TYPES = Object.freeze({
  TABLE: 'analytics-visual-table/v1',
  LINE: 'analytics-visual-line/v1',
  BAR: 'analytics-visual-bar/v1',
  METRIC: 'analytics-visual-metric/v1',
  EVIDENCE: 'analytics-visual-evidence/v1',
});

const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const opaque = value => typeof value === 'string' && OPAQUE.test(value);
const sha256 = value => typeof value === 'string' && SHA.test(value);
const rfc3339 = value => typeof value === 'string' && RFC3339.test(value);
const count = value => typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= JS_MAX_SAFE_INTEGER;
const ratio = value => value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1);
const net = value => value === null || count(value);
const days = value => value === 30 || value === 60 || value === 90;
const channels = value => Array.isArray(value) && value.every(item => item === 'A' || item === 'B')
  && new Set(value).size === value.length;

export function isB0BusinessFixture(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const schema = value.schema_version;
  if (schema === 'analytics-b0/v1' || schema === 'analytics-run-b0/v1') return true;
  if (Object.hasOwn(value, 'repeat_rate') || Object.hasOwn(value, 'repeat_customers')) return true;
  if (value.customers === 100 && value.repeat_customers === 25) return true;
  return isB0BusinessFixture(value.result) || isB0BusinessFixture(value.facts)
    || isB0BusinessFixture(value.snapshot);
}

function decodeCounts(value, channelId) {
  if (!exact(value, channelId ? ['channel_id', ...COUNT_KEYS] : COUNT_KEYS)
    && !(channelId && exact(value, [...COUNT_KEYS, 'channel_id']))) return null;
  if (channelId && value.channel_id !== 'A' && value.channel_id !== 'B') return null;
  const mature = value.channel_mature_cohort_count;
  if (!count(mature) || !count(value.channel_immature_count) || !count(value.channel_repeat_count)
    || !count(value.channel_cross_channel_count) || !ratio(value.channel_repeat_ratio)
    || !ratio(value.channel_cross_channel_ratio) || !net(value.channel_window_net_paid_minor)) return null;
  if (value.channel_repeat_count > mature || value.channel_cross_channel_count > value.channel_repeat_count) return null;
  if (mature === 0) {
    if (value.channel_repeat_count !== 0 || value.channel_cross_channel_count !== 0) return null;
    if (value.channel_repeat_ratio !== null || value.channel_cross_channel_ratio !== null) return null;
    if (value.channel_window_net_paid_minor !== null) return null;
    if (value.channel_empty_reason !== 'EMPTY_MATURE_COHORT') return null;
    return value;
  }
  if (value.channel_empty_reason !== null) return null;
  if (value.channel_repeat_ratio === null || value.channel_cross_channel_ratio === null) return null;
  if (value.channel_window_net_paid_minor === null) return null;
  return value;
}

function decodeResolvedFilters(value) {
  if (!exact(value, FILTER_KEYS)) return null;
  if (value.schema_version !== QUERY_SCHEMA || value.query_id !== 'channel_first_observed_followup'
    || value.query_version !== 'channel-followup-query/v1'
    || value.metric_id !== 'channel_first_observed_n_day_repeat'
    || value.metric_version !== 'channel-followup-metric/v1'
    || value.data_version !== 'synthetic-channel-followup-data/v1'
    || value.hash_version !== 'channel-followup-filter-hash/v1'
    || value.cohort_window_kind !== 'FIXED' || !days(value.observation_days)
    || value.data_snapshot_ref !== 'synthetic-channel-followup-v1' || value.timezone !== 'Asia/Shanghai'
    || !rfc3339(value.resolved_cohort_start) || !rfc3339(value.resolved_cohort_end) || !rfc3339(value.as_of)
    || !channels(value.channel_ids) || value.channel_ids.length === 0
    || value.cohort_ref !== null || !Array.isArray(value.product_ids) || value.product_ids.length !== 0
    || value.exclude_low_price !== false || value.comparison !== null
    || !opaque(value.permission_scope) || !sha256(value.data_digest) || !sha256(value.filter_hash)) return null;
  return value;
}

function decodeFacts(value, observationDays, channelIds) {
  if (!exact(value, FACT_KEYS) || value.display_name !== '首次观察到的渠道 / N日二单率'
    || value.currency !== 'CNY' || value.amount_unit !== 'minor' || value.amount_precision !== 'integer_fen'
    || value.observation_days !== observationDays || !Array.isArray(value.channels)) return null;
  const totals = decodeCounts(value.totals);
  if (!totals) return null;
  const ids = [];
  for (const row of value.channels) {
    const decoded = decodeCounts(row, true);
    if (!decoded || ids.includes(decoded.channel_id)) return null;
    ids.push(decoded.channel_id);
  }
  if (ids.length !== channelIds.length || ids.some(id => !channelIds.includes(id))) return null;
  return value;
}

function decodeLayout(value) {
  if (!exact(value, LAYOUT_KEYS)) return null;
  const { x, y, w, h } = value;
  if (![x, y, w, h].every(item => Number.isInteger(item))) return null;
  if (x < 0 || y < 0 || y > 240 || w < 2 || h < 2 || w > 12 || h > 12 || x + w > 12) return null;
  return value;
}

export function decodeCockpitCard(value) {
  if (isB0BusinessFixture(value) || !exact(value, CARD_KEYS)) return null;
  if (!opaque(value.card_id) || value.data_mode !== 'SNAPSHOT' || value.freshness !== 'PINNED'
    || !exact(value.plugin_ref, PLUGIN_KEYS) || !Object.hasOwn(PLUGIN_TYPES, value.plugin_ref.type)
    || value.plugin_ref.version !== PLUGIN_TYPES[value.plugin_ref.type]
    || !exact(value.analysis_ref, ANALYSIS_REF_KEYS) || !ANALYSIS_ID.test(value.analysis_ref.analysis_id)
    || !Number.isInteger(value.analysis_ref.version) || value.analysis_ref.version < 1
    || !decodeLayout(value.layout)
    || (Object.keys(value.display_overrides).length !== 0
      && !(exact(value.display_overrides, ['title']) && typeof value.display_overrides.title === 'string'))
    || Object.keys(value.filter_mapping).length !== 0
    || (Object.keys(value.local_filters).length !== 0
      && !(exact(value.local_filters, ['channel_ids']) && channels(value.local_filters.channel_ids)
        && value.local_filters.channel_ids.length > 0))
    || !exact(value.snapshot, SNAPSHOT_KEYS) || !opaque(value.snapshot.run_id)
    || !sha256(value.snapshot.evidence_digest) || !sha256(value.filter_hash) || !sha256(value.effective_spec_hash)
    || value.snapshot.data_snapshot_ref !== 'synthetic-channel-followup-v1' || !rfc3339(value.snapshot.as_of)
    || !Array.isArray(value.limitations) || value.limitations.length < 1
    || value.limitations.some(item => typeof item !== 'string' || !item)) return null;
  const filters = decodeResolvedFilters(value.snapshot.resolved_filters);
  if (!filters || filters.filter_hash !== value.filter_hash || filters.as_of !== value.snapshot.as_of) return null;
  const facts = decodeFacts(value.facts, filters.observation_days, filters.channel_ids);
  if (!facts) return null;
  return value;
}

export function decodeCockpit(value) {
  if (isB0BusinessFixture(value) || !exact(value, DASHBOARD_KEYS)) return null;
  if (value.schema_version !== COCKPIT_SCHEMA || !opaque(value.dashboard_id)
    || !Number.isInteger(value.version) || value.version < 1
    || typeof value.title !== 'string' || !value.title || value.title.length > 120
    || !opaque(value.owner_id) || value.visibility !== 'PRIVATE'
    || !exact(value.global_filters, GLOBAL_KEYS) || value.global_filters.schema_version !== FILTER_SCHEMA
    || !Array.isArray(value.global_filters.channel_ids) || value.global_filters.channel_ids.length !== 0
    || !Array.isArray(value.cards) || value.cards.length > 20
    || !rfc3339(value.created_at) || typeof value.preview !== 'boolean' || typeof value.persisted !== 'boolean'
    || !Array.isArray(value.affected_card_ids) || value.affected_card_ids.some(id => !opaque(id))
    || value.finite_mock !== true || value.http_api !== HTTP_API) return null;
  const cards = value.cards.map(card => {
    const decoded = decodeCockpitCard(card);
    if (decoded) return { ok: true, card: decoded };
    const cardId = card && typeof card === 'object' && typeof card.card_id === 'string' ? card.card_id : null;
    return { ok: false, card_id: cardId, error: COPY.cardError };
  });
  return { ...value, cards };
}

export function decodeCockpitList(value) {
  if (!Array.isArray(value) || value.length > 1) return null;
  const items = [];
  for (const row of value) {
    if (isB0BusinessFixture(row) || !exact(row, LIST_KEYS) || row.schema_version !== COCKPIT_SCHEMA
      || !opaque(row.dashboard_id) || !Number.isInteger(row.version) || row.version < 1
      || typeof row.title !== 'string' || !row.title || row.visibility !== 'PRIVATE'
      || !Number.isInteger(row.card_count) || row.card_count < 0 || row.finite_mock !== true
      || row.http_api !== HTTP_API) return null;
    items.push(row);
  }
  return items;
}

export function matchCockpitKeyboard(event) {
  if (!event || typeof event.key !== 'string') return null;
  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  for (const binding of Object.values(COCKPIT_KEYBOARD)) {
    if (key === binding.key && Boolean(event.altKey) === binding.altKey
      && Boolean(event.shiftKey) === binding.shiftKey) return binding.action;
  }
  return null;
}

function formatCardFacts(card) {
  const totals = card.facts.totals;
  const repeat = formatRatioPercent(totals.channel_repeat_ratio);
  const paid = formatFenYuan(totals.channel_window_net_paid_minor);
  const empty = formatEmptyReason(totals.channel_empty_reason);
  return {
    totals: `成熟 ${totals.channel_mature_cohort_count} / 二单 ${totals.channel_repeat_count} · 二单率 ${repeat} · 净支付 ${paid}`,
    empty,
    condition: `N=${card.facts.observation_days} · as_of ${card.snapshot.as_of}`,
    evidence: `run ${card.snapshot.run_id} · digest ${card.snapshot.evidence_digest}`,
  };
}

export function buildCockpitView({
  dashboard = null,
  list = null,
  error = null,
  sessionId = null,
  modelAvailable = false,
  selectedCardId = null,
} = {}) {
  const base = {
    heading: COPY.heading,
    sessionRequired: false,
    modelRequired: false,
    sessionId: sessionId ?? null,
    modelAvailable: modelAvailable === true,
    httpConnected: false,
    keyboard: COCKPIT_KEYBOARD,
    http: COPY.http,
    noSession: COPY.noSession,
    finiteMock: true,
  };
  if (error && (error.status === 403 || error.status === 404)) {
    return { ...base, kind: 'error', message: COPY.unauthorized };
  }
  if (error && error.status === 409) {
    return { ...base, kind: 'error', message: COPY.conflict };
  }
  const decoded = dashboard == null ? null : decodeCockpit(dashboard);
  if (dashboard != null && decoded == null) {
    return { ...base, kind: 'error', message: '结果无法识别或版本不支持；不推断分析成功。' };
  }
  if (decoded) {
    const cards = decoded.cards.map(item => {
      if (!item.ok) {
        return {
          kind: 'error',
          card_id: item.card_id,
          message: COPY.cardError,
          affected: false,
        };
      }
      const card = item.card;
      const facts = formatCardFacts(card);
      const title = card.display_overrides.title || COPY.snapshot;
      return {
        kind: 'ok',
        card_id: card.card_id,
        title,
        plugin: card.plugin_ref.type,
        badge: COPY.pinned,
        layout: card.layout,
        selected: selectedCardId === card.card_id,
        affected: decoded.affected_card_ids.includes(card.card_id),
        localFilterNote: Object.keys(card.local_filters).length ? COPY.localFilterNote : null,
        ...facts,
      };
    });
    return {
      ...base,
      kind: decoded.cards.length === 0 ? 'empty-board' : 'board',
      title: decoded.title,
      version: decoded.version,
      dashboardId: decoded.dashboard_id,
      preview: decoded.preview === true,
      persisted: decoded.persisted === true,
      message: decoded.cards.length === 0 ? COPY.empty : null,
      previewHint: decoded.preview ? COPY.preview : null,
      cards,
      addLabel: COPY.add,
      copyLabel: COPY.copy,
      removeLabel: COPY.remove,
      saveLabel: COPY.save,
      undoLabel: COPY.undo,
      aiLabel: COPY.aiEdit,
      synthetic: COPY.synthetic,
    };
  }
  const items = list == null ? null : decodeCockpitList(list);
  if (items && items.length === 0) {
    return { ...base, kind: 'empty', message: COPY.empty };
  }
  if (items) {
    return {
      ...base,
      kind: 'list',
      items: items.map(row => ({
        dashboard_id: row.dashboard_id,
        title: row.title,
        version: row.version,
        summary: `${row.card_count} 个板块 · ${COPY.pinned}`,
      })),
    };
  }
  return { ...base, kind: 'empty', message: COPY.empty };
}

export const COMPETITION_COPY = Object.freeze({
  endorse: '认可结果',
  confirm: '确认成板',
  board: '可编辑看板',
  actions: '人群行动',
  discardPreview: '放弃预览不等于撤销已保存版本',
  conflict: '409 保留本地草案，重读后再保存',
  modelDown: '模型不可用时仍可查看已存板并手动编辑',
  zero: '零候选不得伪造建议名单',
  expired: '规则或来源变更后草稿过期；文案变更不过期',
  noSend: '不自动发送',
});

export const COCKPIT_CSS = `
.analytics-cockpit-grid { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:12px; }
.analytics-cockpit-card { min-height:44px; }
.analytics-cockpit-card[data-card-error="1"] { border-style:dashed; }
.analytics-cockpit-card[data-affected="1"] { outline:2px dashed currentColor; outline-offset:2px; }
@media (max-width:768px) {
  .analytics-cockpit-grid { grid-template-columns:1fr; }
  .analytics-cockpit-card { grid-column:1 / -1 !important; grid-row:auto !important; }
}
@media (max-width:390px) {
  .analytics-cockpit-grid { grid-template-columns:1fr; }
}
`;

function escapeText(value) {
  return String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

export function renderCockpitHtml(view) {
  const session = view.sessionId ?? '';
  const model = view.modelAvailable ? '1' : '0';
  const keys = view.keyboard;
  const attrs = `class="analytics-b0-dialog analytics-cockpit" data-testid="analytics-cockpit-view" data-kind="${view.kind}" data-session="${session}" data-model="${model}" data-http="NOT_CONNECTED" data-finite-mock="1" data-keyboard-add="${keys.add.shortcut}" data-keyboard-copy="${keys.copy.shortcut}" data-keyboard-remove="${keys.remove.shortcut}"`;
  if (view.kind === 'error') {
    return `<div ${attrs} role="status"><h2>${escapeText(view.heading)}</h2><p>${escapeText(view.message)}</p><small>${escapeText(COPY.noSession)}</small></div>`;
  }
  if (view.kind === 'empty' || view.kind === 'empty-board') {
    const version = view.version ? ` data-version="${view.version}"` : '';
    return `<div ${attrs}${version}><h2>${escapeText(view.heading)}</h2><p data-testid="analytics-cockpit-empty">${escapeText(view.message)}</p><p>${escapeText(view.noSession)}</p><button type="button" data-action="add" aria-keyshortcuts="${keys.add.shortcut}">${escapeText(COPY.add)}</button><small>${escapeText(view.http)}</small></div>`;
  }
  if (view.kind === 'list') {
    const rows = view.items.map(item => `<li data-dashboard-id="${escapeText(item.dashboard_id)}"><strong>${escapeText(item.title)}</strong> · v${item.version}<br/>${escapeText(item.summary)}</li>`).join('');
    return `<div ${attrs}><h2>${escapeText(view.heading)}</h2><p>${escapeText(view.noSession)}</p><ul data-testid="analytics-cockpit-list">${rows}</ul><small>${escapeText(view.http)}</small></div>`;
  }
  const preview = view.preview ? `<p class="analytics-b0-preview" data-testid="analytics-cockpit-preview">${escapeText(COPY.preview)}</p>` : '';
  const cards = view.cards.map(card => {
    if (card.kind === 'error') {
      return `<article class="analytics-b0-card analytics-cockpit-card" data-card-id="${escapeText(card.card_id ?? '')}" data-card-error="1" role="status">${escapeText(COPY.cardError)}</article>`;
    }
    const empty = card.empty?.code ? ` · <abbr title="${escapeText(card.empty.code)}">${escapeText(card.empty.text)}</abbr>` : '';
    const note = card.localFilterNote ? `<p>${escapeText(card.localFilterNote)}</p>` : '';
    const style = `grid-column:${card.layout.x + 1} / span ${card.layout.w};grid-row:${card.layout.y + 1} / span ${card.layout.h}`;
    return `<article class="analytics-b0-card analytics-query-card analytics-cockpit-card" data-card-id="${escapeText(card.card_id)}" data-card-error="0" data-affected="${card.affected ? '1' : '0'}" data-plugin="${escapeText(card.plugin)}" style="${style}"><h3>${escapeText(card.title)}</h3><p>${escapeText(card.badge)} · ${escapeText(card.plugin)}</p><p>${escapeText(card.condition)}</p><p>${escapeText(card.totals)}${empty}</p><small>${escapeText(card.evidence)}</small>${note}<p><button type="button" data-action="copy" data-card-id="${escapeText(card.card_id)}" aria-keyshortcuts="${keys.copy.shortcut}">${escapeText(COPY.copy)}</button> <button type="button" data-action="remove" data-card-id="${escapeText(card.card_id)}" aria-keyshortcuts="${keys.remove.shortcut}">${escapeText(COPY.remove)}</button> <button type="button" data-action="ai_edit" data-card-id="${escapeText(card.card_id)}">${escapeText(COPY.aiEdit)}</button></p></article>`;
  }).join('');
  return `<div ${attrs} data-version="${view.version}" data-preview="${view.preview ? '1' : '0'}"><h2>${escapeText(view.heading)}</h2><p>${escapeText(view.noSession)}</p>${preview}<div class="analytics-b0-actions"><button type="button" data-action="add" aria-keyshortcuts="${keys.add.shortcut}">${escapeText(COPY.add)}</button> <button type="button" data-action="save"${view.preview ? '' : ' disabled'}>${escapeText(COPY.save)}</button> <button type="button" data-action="undo">${escapeText(COPY.undo)}</button></div><div class="analytics-cockpit-grid" data-testid="analytics-cockpit-grid">${cards}</div><small>${escapeText(view.synthetic)} ${escapeText(view.http)}</small></div>`;
}
