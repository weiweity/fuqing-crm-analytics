import type { Agent } from '@deepseek-ai/dsh-agent';

export async function loadRunContext(agent: Agent | undefined, requestId: string | undefined,
  unitId: string, packageDigest: string, signal: AbortSignal, resource: string | null = null): Promise<Record<string, unknown>> {
  signal.throwIfAborted();
  const token = process.env.B0_RUNTIME_TOKEN;
  if (!token || !agent || agent.id !== process.env.B0_SESSION_ID || !requestId) throw new Error('B0 context has no bound native request');
  const response = await fetch('http://127.0.0.1:4315/internal/native/run-context', {
    method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body: JSON.stringify({ session_id: agent.id, request_id: requestId, unit_id: unitId, package_digest: packageDigest, resource }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(3000)]), redirect: 'error',
  });
  if (!response.ok) { await response.body?.cancel(); throw new Error('B0 kernel refused current context or budget'); }
  // Enforce a streaming bound, not response.text() followed by a late size test.
  const reader = response.body?.getReader();
  if (!reader) throw new Error('B0 context has no body');
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 65536) { await reader.cancel(); throw new Error('B0 context exceeds bound'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const context = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (context.schema_version !== 'analytics-b0-runtime-context/v1' || context.session_id !== agent.id
    || context.request_id !== requestId || context.versions?.method_package_digest !== packageDigest
    || context.run_status !== 'RUNNING' || context.contains_real_data !== false
    || context.approval_state !== 'NOT_AVAILABLE_IN_B0' || context.memory_authority !== 'NONE') throw new Error('B0 context contract mismatch');
  signal.throwIfAborted();
  return context;
}
