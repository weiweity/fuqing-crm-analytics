/** Read-only admission check; never prompts a model, changes settings or restarts a host. */
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

export function localLaunch(value) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || !['127.0.0.1', '[::1]'].includes(url.hostname)
    || url.username || url.password || url.pathname !== '/' || !url.port) throw new Error('INVALID_LOCAL_LAUNCH');
  return url;
}

export async function boardModelPreflight(launchUrl, fetcher = fetch) {
  const url = localLaunch(launchUrl);
  const evidence = { schema_version: 'board-model-preflight/v1', origin: url.origin,
    checked_at: new Date().toISOString(), model_calls: 0, sessions_created: 0,
    settings_changed: false, host_restarted: false, transport_ready: false,
    model_execution: 'NOT_RUN', credentials_verified: false, checks: {} };
  const request = (path, options = {}) => fetcher(new URL(path, url.origin), {
    ...options, redirect: 'manual', signal: AbortSignal.timeout(20000),
  });
  try {
    const unauth = await request('/');
    evidence.checks.unauthenticated_status = unauth.status;
    await unauth.arrayBuffer();
    if (unauth.status !== 401) { evidence.reason = 'AUTH_FENCE_NOT_VERIFIED'; return evidence; }
    const exchange = await request(url.href);
    const cookie = exchange.headers.getSetCookie().map(value => value.split(';')[0]).join('; ');
    evidence.checks.exchange_status = exchange.status;
    await exchange.arrayBuffer();
    if (exchange.status !== 303 || !cookie) { evidence.reason = 'AUTH_EXCHANGE_FAILED'; return evidence; }
    async function call(method, payload) {
      const response = await request(`/api/${method}`, { method: 'POST',
        headers: { 'content-type': 'application/json', cookie },
        body: JSON.stringify({ type: 'client-request', rpcId: `preflight-${method}`, method, payload }) });
      const body = await response.text();
      let result;
      try { result = JSON.parse(body).result; } catch { /* Do not record raw response or exception text. */ }
      return { status: response.status, result };
    }
    const model = await call('session/modelCatalog', { args: {} });
    const catalog = model.result?.ok === true ? model.result.value : undefined;
    const selected = catalog?.default;
    evidence.checks.model_catalog_status = model.status;
    evidence.checks.default_model = selected && {
      provider: selected.provider, model: selected.model,
    };
    evidence.checks.default_route_available = model.status === 200 && typeof selected?.provider === 'string'
      && typeof selected?.model === 'string' && Array.isArray(catalog?.routableProviders)
      && catalog.routableProviders.includes(selected.provider);
    const board = await call('shine-mage-board', { operation: 'status', payload: {} });
    evidence.checks.board_status = board.status;
    evidence.checks.board_protocol_available = board.status === 200 && board.result?.ok === true
      && board.result.value?.protocol === 'board-browser/v1';
    evidence.checks.board_service_configured = evidence.checks.board_protocol_available
      && board.result.value?.configured === true;
    // A provider can advertise its route/models before credentials are configured.
    // This is not evidence that an authenticated model call or a board tool works.
    evidence.transport_ready = evidence.checks.default_route_available && evidence.checks.board_service_configured;
    evidence.reason = !evidence.checks.board_protocol_available ? 'BOARD_PROTOCOL_UNAVAILABLE'
      : !evidence.checks.board_service_configured ? 'BOARD_SERVICE_NOT_CONFIGURED'
      : !evidence.checks.default_route_available ? 'MODEL_ROUTE_UNAVAILABLE' : 'PREFLIGHT_ONLY';
    return evidence;
  } catch {
    evidence.reason = 'TRANSPORT_FAILED';
    return evidence;
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 4 || args[0] !== '--runtime' || args[2] !== '--output') {
    throw new Error('Usage: board-model-preflight.mjs --runtime /absolute/runtime --output /absolute/evidence.json');
  }
  const privateConfig = JSON.parse(await readFile(join(resolve(args[1]), 'browser-private.json'), 'utf8'));
  const result = await boardModelPreflight(privateConfig.launchUrl);
  await writeFile(resolve(args[3]), `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
  console.log(JSON.stringify(result));
  if (!result.transport_ready) process.exitCode = 2;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(() => { console.error('PREFLIGHT_INPUT_OR_OUTPUT_FAILED'); process.exitCode = 1; });
}
