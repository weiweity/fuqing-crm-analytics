/** Query-card cancel submit helpers. No new protocol; maps existing RPC envelope. */

export const QUERY_CANCEL_COPY = Object.freeze({
  submitting: '正在提交取消…',
  accepted: '取消请求已受理',
  error: '取消未完成，可重试',
});

export function sessionCancelEnvelope(sessionId, rpcId) {
  return {
    type: 'client-request',
    rpcId,
    method: 'session/cancel',
    payload: { args: { request: { sessionId } } },
  };
}

export function classifyCancelOutcome(response) {
  if (!response || response.network === true) return 'error';
  const status = response.status;
  if (!Number.isInteger(status) || status < 200 || status >= 300) return 'error';
  const body = response.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)) return 'error';
  const result = body.result;
  if (!result || typeof result !== 'object' || result.ok !== true) return 'error';
  return 'accepted';
}
