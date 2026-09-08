/** Same-origin cockpit/analysis HTTP. Browser never sends backend bearer. */

export const ASSET_HTTP = 'CONNECTED';

export async function assetRequest(path, { method = 'GET', body, key, etag } = {}) {
  const headers = {};
  if (body !== undefined) headers['content-type'] = 'application/json';
  if (key) headers['idempotency-key'] = key;
  if (etag !== undefined && etag !== null) headers['if-match'] = String(etag);
  const response = await fetch(path, {
    method, credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let payload = null;
  try { payload = await response.json(); } catch { payload = null; }
  return { status: response.status, payload, etag: response.headers.get('etag') };
}

export async function probeAssetHttp() {
  try {
    const row = await assetRequest('/b0/assets');
    return row.status === 200 && row.payload?.http_api === ASSET_HTTP && row.payload?.cockpit === true;
  } catch {
    return false;
  }
}

export function decodeAssetError(payload) {
  const error = payload && typeof payload === 'object' ? payload.error : null;
  if (!error || typeof error !== 'object') return { code: 'UNAVAILABLE', message: '资产请求失败。' };
  const code = typeof error.code === 'string' && error.code ? error.code : 'UNAVAILABLE';
  const message = typeof error.message === 'string' && error.message ? error.message.slice(0, 200) : '资产请求失败。';
  return { code, message };
}

export function decodeHttpAnalysisList(payload) {
  if (!payload || !Array.isArray(payload.items)) return null;
  if (payload.http_api != null && payload.http_api !== ASSET_HTTP) return null;
  return payload.items.filter(row => row && row.http_api === ASSET_HTTP
    && typeof row.analysis_id === 'string' && typeof row.title === 'string' && typeof row.version === 'number');
}

export function decodeHttpDashboard(payload) {
  if (!payload || payload.http_api !== ASSET_HTTP || payload.schema_version !== 'analytics-cockpit/v1') return null;
  if (!Array.isArray(payload.cards) || typeof payload.dashboard_id !== 'string') return null;
  return payload;
}

export function addIntentKey(analysisId, analysisVersion, boardVersion) {
  if (typeof analysisId !== 'string' || !analysisId) return null;
  if (!Number.isInteger(analysisVersion) || analysisVersion < 1) return null;
  if (!Number.isInteger(boardVersion) || boardVersion < 1) return null;
  return `add-${analysisId}-v${analysisVersion}-b${boardVersion}`;
}

export function dashboardContainsAnalysis(payload, analysisId, version) {
  const cards = Array.isArray(payload?.cards) ? payload.cards : null;
  if (!Array.isArray(cards) || typeof analysisId !== 'string') return false;
  return cards.some(card => card?.analysis_ref?.analysis_id === analysisId
    && card?.analysis_ref?.version === version);
}

export function formatCard(card) {
  if (!card || card.source_status !== 'OK') {
    return {
      kind: 'error',
      card_id: card?.card_id ?? '',
      analysis_ref: card?.analysis_ref ?? null,
      layout: card?.layout ?? { x: 0, y: 0, w: 6, h: 4 },
      message: card?.error?.message || '该板块来源不可用。',
    };
  }
  const filters = card.snapshot?.resolved_filters;
  const facts = card.facts;
  const channels = Array.isArray(filters?.channel_ids) ? filters.channel_ids.join('+') : '';
  return {
    kind: 'ok',
    card_id: card.card_id,
    analysis_ref: card.analysis_ref,
    layout: card.layout,
    title: card.display_overrides?.title || '固定历史快照',
    days: facts?.observation_days,
    as_of: card.snapshot?.as_of,
    channels,
    run_id: card.snapshot?.run_id,
    limitations: card.limitations,
    totals: facts?.totals,
  };
}
