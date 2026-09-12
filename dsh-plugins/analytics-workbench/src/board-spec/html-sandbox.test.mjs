import test from 'node:test';
import assert from 'node:assert/strict';
import { HTML_SANDBOX, htmlSandboxFrame, httpsSandboxFrame, openHttpsLink, refreshSandboxHtml, wrapSandboxHtml } from './html-sandbox.mjs';

test('htmlSandboxFrame does not put markup on the parent paint surface', () => {
  const got = htmlSandboxFrame({
    kind: 'html_sandbox',
    html: '<script>window.parent.steal()</script>',
  });
  assert.equal(got.ok, true);
  assert.equal(got.sandbox, HTML_SANDBOX);
  assert.doesNotMatch(got.sandbox, /allow-scripts/);
  assert.doesNotMatch(got.sandbox, /allow-same-origin/);
  assert.equal(got.referrerPolicy, 'no-referrer');
  assert.match(got.srcdoc, /steal/);
  assert.match(got.srcdoc, /Content-Security-Policy/);
  assert.doesNotMatch(got.srcdoc, /script-src/);
});

test('empty html_sandbox is empty not a parent innerHTML', () => {
  const got = htmlSandboxFrame({ kind: 'html_sandbox', title: 'x' });
  assert.equal(got.ok, true);
  assert.equal(got.empty, true);
  assert.equal('srcdoc' in got, false);
});

test('httpsSandboxFrame rejects javascript and http', () => {
  assert.equal(httpsSandboxFrame('javascript:alert(1)').ok, false);
  assert.equal(httpsSandboxFrame('http://example.invalid').ok, false);
  const got = httpsSandboxFrame('https://example.invalid/doc');
  assert.equal(got.ok, true);
  assert.equal(got.src, 'https://example.invalid/doc');
  assert.equal(got.sandbox, '');
});

test('httpsSandboxFrame rejects loopback, private, and credentialed hosts', () => {
  assert.equal(httpsSandboxFrame('https://127.0.0.1/x').ok, false);
  assert.equal(httpsSandboxFrame('https://localhost/x').ok, false);
  assert.equal(httpsSandboxFrame('https://192.168.1.1/x').ok, false);
  assert.equal(httpsSandboxFrame('https://10.0.0.2/x').ok, false);
  assert.equal(httpsSandboxFrame('https://user:pass@example.invalid/x').ok, false);
});

test('wrapSandboxHtml keeps payload inside srcdoc only', () => {
  const wrapped = wrapSandboxHtml('<img src=x onerror=bad()>');
  assert.match(wrapped, /onerror=bad/);
  assert.match(wrapped, /<!doctype html>/i);
});

test('wrapSandboxHtml does not let payload close the CSP wrapper', () => {
  const wrapped = wrapSandboxHtml('</body></html><script>steal()</script><meta http-equiv="refresh">');
  assert.match(wrapped, /Content-Security-Policy/);
  assert.match(wrapped, /&lt;\/body/);
  assert.match(wrapped, /&lt;\/html/);
  assert.match(wrapped, /&lt;meta/);
  assert.doesNotMatch(wrapped, /script-src/);
  assert.equal((wrapped.match(/<\/body>/gi) || []).length, 1);
  assert.equal((wrapped.match(/<\/html>/gi) || []).length, 1);
});

test('refreshSandboxHtml GETs https HTML without Authorization and wraps srcdoc', async () => {
  const headers = [];
  const got = await refreshSandboxHtml('https://example.invalid/sandbox', async (url, init) => {
    headers.push(init);
    assert.equal(url, 'https://example.invalid/sandbox');
    return new Response('<p>live</p>', { status: 200, headers: { 'content-type': 'text/html' } });
  });
  assert.equal(got.ok, true);
  assert.match(got.srcdoc, /live/);
  assert.equal(headers[0].credentials, 'omit');
  assert.equal(headers[0].redirect, 'manual');
  assert.equal(headers[0].headers.authorization, undefined);
});

test('refreshSandboxHtml refuses http and non-HTML', async () => {
  assert.equal((await refreshSandboxHtml('http://example.invalid/x')).ok, false);
  const got = await refreshSandboxHtml('https://example.invalid/sandbox', async () => (
    new Response('{"x":1}', { status: 200, headers: { 'content-type': 'application/json' } })
  ));
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'SANDBOX_REFRESH');
});

test('openHttpsLink is noopener and refuses javascript', () => {
  assert.equal(openHttpsLink('javascript:alert(1)').ok, false);
  const got = openHttpsLink('https://example.invalid/feishu/doc/channel');
  assert.equal(got.ok, true);
  assert.equal(got.target, '_blank');
  assert.equal(got.rel, 'noopener noreferrer');
});

test('htmlSandboxFrame refuses other kinds; refresh fails closed on throw and oversized HTML', async () => {
  assert.equal(htmlSandboxFrame({ kind: 'METRIC' }).error.code, 'SANDBOX_KIND');
  const huge = await refreshSandboxHtml('https://example.invalid/x', async () => (
    new Response('h'.repeat(100_001), { status: 200, headers: { 'content-type': 'text/html' } })
  ));
  assert.equal(huge.ok, false);
  assert.equal(huge.error.code, 'SANDBOX_REFRESH');
  const boom = await refreshSandboxHtml('https://example.invalid/x', async () => { throw new Error('net'); });
  assert.equal(boom.error.code, 'SANDBOX_REFRESH');
  const plain = await refreshSandboxHtml('https://example.invalid/x', async () => (
    new Response('<p>ok</p>', { status: 200, headers: { 'content-type': 'text/plain' } })
  ));
  assert.equal(plain.ok, true);
  assert.match(plain.srcdoc, /ok/);
});
