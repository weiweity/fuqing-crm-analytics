/** Own 4325-4329, competition 14327, or local 6677. Never probe-kill foreign listeners. */
import assert from 'node:assert/strict';
import { createServer } from 'node:net';
import {
  ALLOWED_WEB_PORTS, BROWSER_BLOCKED_PORTS, COMPETITION_VITE_PORT, FOREIGN_PORTS, HOST,
  PORT_RANGE, PORTS,
} from './constants.mjs';

export function assertOwnedPort(port) {
  const n = Number(port);
  assert.ok(!BROWSER_BLOCKED_PORTS.includes(n),
    `port ${n} is on the Chromium ERR_UNSAFE_PORT blocklist; a listener here never renders in a browser`);
  assert.ok(Number.isInteger(n) && ALLOWED_WEB_PORTS.includes(n),
    `port must be one of ${ALLOWED_WEB_PORTS.join(',')}`);
  assert.notEqual(n, COMPETITION_VITE_PORT, '15173 is reserved for Vite; dsh-dev must not bind it');
  assert.ok(!FOREIGN_PORTS.includes(n), `refusing foreign port ${n}`);
  return n;
}

export function assertOwnedHost(host) {
  assert.equal(host, HOST, `host must be ${HOST}; this is not a public bind`);
  return host;
}

export async function assertFree(port, host = HOST) {
  assertOwnedPort(port);
  const server = createServer();
  await new Promise((ok, fail) => {
    server.once('error', fail);
    server.listen(port, host, ok);
  });
  await new Promise((ok, fail) => server.close(e => e ? fail(e) : ok()));
}

export async function assertRangeFree(host = HOST) {
  for (const port of PORT_RANGE) await assertFree(port, host);
}

export { PORTS, PORT_RANGE, FOREIGN_PORTS, HOST, ALLOWED_WEB_PORTS, COMPETITION_VITE_PORT };
