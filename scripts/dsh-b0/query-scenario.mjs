/** Finite native-query wire script. Mock never fabricates SQL results or journals. */
import { QUERY_TOOL_NAME, decodeQueryRequest } from '../../dsh-plugins/analytics-workbench/src/query-model.mjs';
import { QUERY_SESSION_IDS } from '../../dsh-plugins/analytics-workbench/src/initial-session.mjs';

export { QUERY_TOOL_NAME, QUERY_SESSION_IDS };
export const SCENARIO = 'native-query';
export const QUESTIONS = Object.freeze([
  '合成渠道后续购买第一问：首次观察窗口 2026-06-01 至 2026-09-01，观察 30 日。',
  '合成渠道后续购买第二问：同一窗口，观察 60 日。',
]);

export function queryRequest(observationDays) {
  return {
    schema_version: 'analytics-channel-followup/v1',
    query_id: 'channel_first_observed_followup',
    query_version: 'channel-followup-query/v1',
    metric_id: 'channel_first_observed_n_day_repeat',
    metric_version: 'channel-followup-metric/v1',
    cohort_window: { kind: 'FIXED', start_date: '2026-06-01', end_date: '2026-09-01' },
    observation_days: observationDays,
    data_snapshot_ref: 'synthetic-channel-followup-v1',
    timezone: 'Asia/Shanghai',
    channel_ids: [],
    cohort_ref: null,
    product_ids: [],
    exclude_low_price: false,
    comparison: null,
  };
}

const fast = Object.freeze({ chunkSize: 32, chunkDelayMs: 0 });

export function queryMockScript() {
  const wrap = '合成查询完成：数字来自真实 worker SQL，不是模型编造，不能当作真实经营结论。';
  return [
    { sequence: ['tool_call_success'], toolName: QUERY_TOOL_NAME,
      toolArguments: JSON.stringify(queryRequest(30)), successText: wrap, ...fast },
    { sequence: ['success'], successText: wrap, ...fast },
    { sequence: ['tool_call_success'], toolName: QUERY_TOOL_NAME,
      toolArguments: JSON.stringify(queryRequest(60)), successText: wrap, ...fast },
    { sequence: ['success'], successText: wrap, ...fast },
  ];
}

export function assertQueryRequest(value, observationDays) {
  const decoded = decodeQueryRequest(value);
  return Boolean(decoded && decoded.observation_days === observationDays
    && decoded.cohort_window.start_date === '2026-06-01'
    && decoded.cohort_window.end_date === '2026-09-01');
}

/** Visible card facts from the G2 hand goldens. Driver never treats DB success as the card. */
export const QUERY_CARD_EXPECT = Object.freeze({
  30: Object.freeze({ days: 30, repeat: 5, mature: 9, yuan: '1100.00 元' }),
  60: Object.freeze({ days: 60, repeat: 6, mature: 9, yuan: '1150.00 元' }),
});

export function bindListedSessions(items, allowedIds) {
  if (!Array.isArray(items) || !Array.isArray(allowedIds) || items.length !== allowedIds.length) return null;
  const ids = items.map(item => item?.sessionId).filter(Boolean);
  if (new Set(ids).size !== allowedIds.length) return null;
  if (!allowedIds.every(id => ids.includes(id)) || ids.some(id => !allowedIds.includes(id))) return null;
  return allowedIds.map(id => {
    const item = items.find(row => row.sessionId === id);
    const title = typeof item.projections?.values?.title === 'string' ? item.projections.values.title : '';
    return { sessionId: id, blank: item.blank === true, title };
  });
}

export function sessionSwitchPlan(listed, currentId, targetId) {
  if (!Array.isArray(listed) || listed.length !== 2) return { action: 'reject', reason: 'expected-exactly-two' };
  const target = listed.find(row => row.sessionId === targetId);
  if (!target || !listed.some(row => row.sessionId === currentId)) {
    return { action: 'reject', reason: 'unregistered-target' };
  }
  if (currentId === targetId) return { action: 'noop', target };
  if (target.blank) {
    const otherBlanks = listed.filter(row => row.blank && row.sessionId !== currentId);
    if (otherBlanks.length !== 1 || otherBlanks[0].sessionId !== targetId) {
      return { action: 'reject', reason: 'blank-not-unique-other' };
    }
    return { action: 'new-session-button', target };
  }
  if (!target.title || target.title === target.sessionId) {
    return { action: 'reject', reason: 'missing-visible-title' };
  }
  return { action: 'treeitem', title: target.title, target };
}

export function parseTreeitemRef(snapshot, title) {
  if (typeof title !== 'string' || !title || title.startsWith('session-')) return null;
  const escaped = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = String(snapshot ?? '').match(new RegExp(`(@e\\d+) \\[treeitem[^\\]]*\\] "${escaped}"`));
  return match?.[1] ?? null;
}

export function parseNewSessionButtonRef(snapshot) {
  const text = String(snapshot ?? '');
  const patterns = [
    /(@e\d+) \[button\] "New session"(?: \[disabled\])?/,
    /(@e\d+) \[button\] "New Session"(?: \[disabled\])?/,
    /(@e\d+) \[button\] "新会话"(?: \[disabled\])?/,
    /(@e\d+) \[button\] "在.+中新建会话"/,
    /(@e\d+) \[button\] "New session in [^"]+"/,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1];
  }
  return null;
}

export function cardShowsQuery(ui, expect) {
  const cards = Array.isArray(ui?.cards) ? ui.cards : [];
  const text = cards.join('\n');
  const days = Array.isArray(ui?.days) ? ui.days : [];
  return cards.length > 0 && days.includes(String(expect.days))
    && text.includes(`N=${expect.days}`) && text.includes(String(expect.repeat))
    && text.includes(expect.yuan) && (!expect.runId || text.includes(expect.runId))
    && (!expect.stepId || text.includes(expect.stepId));
}

export function cardHasForeignDays(ui, days) {
  const cards = Array.isArray(ui?.cards) ? ui.cards : [];
  const listed = Array.isArray(ui?.days) ? ui.days : [];
  return listed.includes(String(days)) || cards.some(text => String(text).includes(`N=${days}`));
}

export function sessionReadyWithoutForeign(ui, sessionId, foreignDays) {
  return ui?.session === sessionId && !cardHasForeignDays(ui, foreignDays);
}
