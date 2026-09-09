/** HTTP probe of an owned dsh-dev runtime. Never prints launch tokens. */
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { currentPath } from './paths.mjs';
import { HOST } from './constants.mjs';

import { assertOwnedPort } from './ports.mjs';

const current = JSON.parse(await readFile(currentPath(), 'utf8'));
assert.equal(current.host, HOST);
assertOwnedPort(current.webPort);
const priv = JSON.parse(await readFile(join(current.runtime, 'browser-private.json'), 'utf8'));
assert.equal(priv.launchOrigin, `http://${HOST}:${current.webPort}`);
assert.ok(typeof priv.launchUrl === 'string');
const origin = priv.launchOrigin;
const unauth = await fetch(`${origin}/`, { redirect: 'manual' });
const exchange = await fetch(priv.launchUrl, { redirect: 'manual' });
const cookie = (exchange.headers.getSetCookie?.() ?? []).map(s => s.split(';')[0]).join('; ');
const location = exchange.headers.get('location');
const authed = await fetch(`${origin}/`, { headers: cookie ? { cookie } : {}, redirect: 'manual' });
const html = await authed.text();
const evidence = {
  origin,
  unauth_status: unauth.status,
  exchange_status: exchange.status,
  has_set_cookie: Boolean(cookie),
  cookie_names: cookie ? cookie.split(';').map(p => {
    const name = p.trim().split('=')[0];
    return name.startsWith('dsh-auth-') ? 'dsh-auth-*' : name.replace(/[A-Za-z0-9_-]{8,}/g, '*');
  }) : [],
  redirect_to_root: location === '/' || location === `${origin}/`,
  authed_status: authed.status,
  html_bytes: Buffer.byteLength(html),
  dsh_boot: html.includes('__DSH_BOOT__'),
  vue_growth: html.includes('growth-board') || html.includes('MissionHero'),
};
assert.equal(evidence.unauth_status, 401, 'unauthenticated access must be rejected');
assert.equal(evidence.authed_status, 200, 'authenticated document must load');
assert.equal(evidence.vue_growth, false, 'served Vue growth-board instead of DSH');
assert.equal(evidence.dsh_boot, true, 'missing DSH boot graph');
assert.equal(evidence.has_set_cookie, true, 'launch did not mint a cookie');
console.log(JSON.stringify(evidence, null, 2));
