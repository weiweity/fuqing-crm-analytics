/** Host-only bounded transport. Credentials never belong in the library browser bundle. */
export const BOARD_HTTP_PREFIX = '/api/v1/analytics/board-spec';
const failure = (code, message, status = 503) => ({ ok: false, error: { code, message, details: { status } } });

export function boardServerConfigured() {
  return Boolean(process.env.COMPETITION_HTTP_BASE && process.env.COMPETITION_HTTP_TOKEN);
}

function configuredOrigin() {
  const parsed = new URL(process.env.COMPETITION_HTTP_BASE);
  if (parsed.protocol !== 'http:' || !['127.0.0.1', '[::1]'].includes(parsed.hostname)
    || !parsed.port || ['4327', '8000', '5173'].includes(parsed.port)
    || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) {
    throw new Error('unsupported board service origin');
  }
  return parsed.origin;
}

async function boundedJson(response) {
  if (!response.body) throw new Error('missing response');
  const reader = response.body.getReader();
  let size = 0;
  const parts = [];
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 2_200_000) throw new Error('response limit');
      parts.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}

export async function boardServerRequest(path, { method = 'GET', body, key, signal } = {}) {
  signal?.throwIfAborted();
  if (!boardServerConfigured()) return failure('NOT_CONNECTED', '看板服务尚未配置，未生成或保存看板。');
  // Routes are internal identifiers, never a generic URL proxy. Query values may
  // be encoded, but path traversal (including percent-encoded dots) cannot pass.
  if (typeof path !== 'string' || !/^\/[A-Za-z0-9_/-]+(?:\?[^#\\\s]*)?$/.test(path)
    || path.startsWith('//') || !['GET', 'POST'].includes(method)) return failure('INVALID_REQUEST', '不支持的看板请求。', 400);
  let origin;
  try { origin = configuredOrigin(); }
  catch { return failure('NOT_CONNECTED', '看板服务配置不符合隔离规则。'); }
  const deadline = AbortSignal.any([AbortSignal.timeout(5000), ...(signal ? [signal] : [])]);
  try {
    const response = await fetch(`${origin}${BOARD_HTTP_PREFIX}${path}`, {
      method, redirect: 'error', signal: deadline,
      headers: { authorization: `Bearer ${process.env.COMPETITION_HTTP_TOKEN}`,
        ...(body === undefined ? {} : { 'content-type': 'application/json' }),
        ...(key ? { 'idempotency-key': key } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const value = await boundedJson(response);
    if (!response.ok) {
      const code = value?.error?.code;
      const message = value?.error?.message;
      return failure(typeof code === 'string' && /^[A-Z0-9_]{1,80}$/.test(code) ? code : 'SERVICE_ERROR',
        typeof message === 'string' && message.length <= 2000 ? message : '看板服务拒绝了本次请求。', response.status);
    }
    if (value === null || typeof value !== 'object') return failure('INVALID_RESPONSE', '看板响应不符合合同。');
    return { ok: true, value };
  } catch {
    signal?.throwIfAborted();
    // A lost confirmation reply is UNKNOWN, never automatic retry or local success.
    return failure(deadline.aborted ? 'TIMEOUT' : 'TRANSPORT_ERROR',
      '未取得看板服务的有效回执；保留当前内容。确认保存可用同一幂等键重试。');
  }
}
