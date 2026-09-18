/** Isolated free-page HTTP launcher. Owns its loopback port, never 6677.

 Spawns one Python uvicorn process that mounts create_page_app with an explicit
 page_state_dir (small SQLite) and an explicit PageResultAccess, plus the CORS
 the 6677-served browser page needs to reach this cross-origin base. The
 launcher exits when the supervisor asks it to stop; it never touches the
 archived business DuckDB and never signals foreign listeners.
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { repoRoot } from './paths.mjs';

const SERVER = join(repoRoot, 'scripts/dsh-dev/page_http_server.py');
/** Fixed default port. Not in ALLOWED_WEB_PORTS, not 6677, not Chromium-blocked. */
export const PAGE_HTTP_DEFAULT_PORT = 18091;

/** The launcher refuses any configured base that contains the live port. */
export function assertNotLivePort(base) {
  if (String(base).includes(':6677')) {
    const error = new Error('REFUSED_LIVE_PORT');
    error.code = 'REFUSED_LIVE_PORT';
    throw error;
  }
  return base;
}

/** Loopback origin for the child; callers may pass 0 to request a random port. */
export function pageHttpOrigin(port) {
  return `http://127.0.0.1:${port}`;
}

export async function startPageHttp({
  port = PAGE_HTTP_DEFAULT_PORT,
  stateDir,
  python = process.env.DSH_DEV_PAGE_PYTHON ?? 'python3',
  env = process.env,
  signal,
  timeoutMs = 15000,
} = {}) {
  assert.ok(Number.isInteger(port) && port > 0 && port <= 65535, 'page http port must be 1-65535');
  assert.notEqual(port, 6677, '6677 is the live web; page documents never bind it');
  assert.ok(stateDir && stateDir.startsWith('/'), 'page state dir must be an absolute path');
  await mkdir(stateDir, { recursive: true, mode: 0o700 });
  const token = randomBytes(32).toString('hex');
  const child = spawn(python, [SERVER, '--host', '127.0.0.1', '--port', String(port),
    '--state-dir', stateDir], {
    cwd: repoRoot,
    env: { ...env, PAGE_DOCUMENTS_HTTP_TOKEN: token },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let captured = '';
  const ingest = chunk => {
    captured = (captured + String(chunk)).slice(-65536);
  };
  child.stdout.on('data', ingest);
  child.stderr.on('data', ingest);
  const childExit = new Promise(ok => {
    child.once('close', (code, signalName) => ok({ code, signal: signalName }));
    child.once('error', ok);
  });
  const abort = () => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM'); };
  signal?.addEventListener('abort', abort, { once: true });
  const deadline = Date.now() + timeoutMs;
  let ready = false;
  try {
    while (Date.now() < deadline) {
      if (child.exitCode !== null || child.signalCode !== null) break;
      // The server prints one ready line before uvicorn.run binds; the loop
      // then verifies the port actually accepts (a bind failure would exit).
      // binding-state on an empty manifest is a read-only authed probe: 200
      // with the token proves auth and routing without touching any page.
      if (captured.includes('page-http ready')) {
        try {
          const response = await fetch(`${pageHttpOrigin(port)}/api/v1/analytics/page-result-access/binding-state`, {
            method: 'POST',
            headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
            body: JSON.stringify({ manifest: { bindings: [], result_refs: [] } }),
            signal: AbortSignal.timeout(500),
          });
          if (response.status === 200) { ready = true; break; }
        } catch { /* bind not accepted yet */ }
      }
      await delay(100);
    }
    assert.ok(ready, `page http did not become ready on ${port}: ${captured.slice(-2000)}`);
    return {
      base: pageHttpOrigin(port),
      token,
      child,
      async stop() {
        signal?.removeEventListener('abort', abort);
        abort();
        await Promise.race([childExit, delay(3000).then(() => child.kill('SIGKILL'))]);
      },
    };
  } catch (error) {
    signal?.removeEventListener('abort', abort);
    abort();
    await Promise.race([childExit, delay(2000)]);
    error.pageHttpLog = captured.slice(-2000);
    throw error;
  }
}

/** Write-once state summary for the runtime dir. Token file is 0600. */
export async function writePageHttpState(runtime, { base, token }) {
  await writeFile(join(runtime, 'page-http-state.json'),
    `${JSON.stringify({ base }, null, 2)}\n`, { mode: 0o600 });
  await writeFile(join(runtime, 'page-http-token'), token, { mode: 0o600 });
}
