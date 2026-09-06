/** Read-only native UI projection. Refresh cannot create or replay a prompt. */
const schema = 'analytics-run-b0/v1';
const statuses = new Set(['QUEUED', 'RUNNING', 'NEEDS_INPUT', 'SUCCEEDED', 'FAILED', 'CANCELLING', 'CANCELLED', 'UNKNOWN']);
const phases = new Set(['ACCEPTED', 'PLANNING', 'EXECUTING', 'FINALIZING']);
const runId = value => typeof value === 'string' && /^run_[a-f0-9]{32}$/.test(value);

export async function loadRunView(fetcher, sessionId, signal) {
  async function get(path) {
    const response = await fetcher(path, { method: 'GET', credentials: 'same-origin', cache: 'no-store', signal, redirect: 'error' });
    if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'ACCESS_LOST' : 'READ_UNAVAILABLE');
    return response.json();
  }
  const context = await get('/b0/context');
  if (context.session_id !== sessionId || context.conversation?.schema_version !== schema
    || !Array.isArray(context.conversation.run_ids) || context.conversation.run_ids.length > 128
    || !context.conversation.run_ids.every(runId)) throw new Error('INVALID_RUN_VIEW');
  const runs = await Promise.all(context.conversation.run_ids.slice(-3).map(async id => {
    const row = await get(`/b0/runs/${id}`);
    if (row.schema_version !== schema || row.run_id !== id || row.conversation_id !== context.conversation.conversation_id
      || !statuses.has(row.status) || !phases.has(row.phase) || !Number.isInteger(row.version) || row.version < 1
      || !Number.isInteger(row.diagnostics?.tool_steps_used) || row.diagnostics.tool_steps_used < 0 || row.diagnostics.tool_steps_used > 8) {
      throw new Error('INVALID_RUN_VIEW');
    }
    return row;
  }));
  return { ready: context.ready === true, runs };
}
