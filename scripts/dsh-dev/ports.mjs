/** Own only 4325-4329. Never probe-kill foreign listeners. */
import assert from 'node:assert/strict';
import { createServer } from 'node:net';
import { FOREIGN_PORTS, HOST, PORT_RANGE, PORTS } from './constants.mjs';

export function assertOwnedPort(port) {
  const n = Number(port);
  assert.ok(Number.isInteger(n) && PORT_RANGE.includes(n), `port must be one of ${PORT_RANGE.join(',')}`);
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

export { PORTS, PORT_RANGE, FOREIGN_PORTS, HOST };
