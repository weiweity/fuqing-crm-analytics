export const QUERY_CANCEL_COPY: {
  readonly submitting: string;
  readonly accepted: string;
  readonly error: string;
};
export function sessionCancelEnvelope(sessionId: string, rpcId: string): {
  type: 'client-request';
  rpcId: string;
  method: 'session/cancel';
  payload: { args: { request: { sessionId: string } } };
};
export function classifyCancelOutcome(response: { status?: number; body?: unknown; network?: boolean } | null): 'accepted' | 'error';
