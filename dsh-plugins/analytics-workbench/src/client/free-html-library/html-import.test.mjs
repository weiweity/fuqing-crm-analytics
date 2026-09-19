import test from 'node:test';
import assert from 'node:assert/strict';
import { runInNewContext } from 'node:vm';
import { convertWorkspaceHtml, createHtmlImporter, resolveImportResourcePath } from './html-import.mjs';
import { createLivePageAdapters } from './live-adapters.mjs';
import { createIsolatedFetch } from './p12-http-fakes.mjs';

const TOKEN = 'library-page-isolated-test-token-32chars';
const BASE = 'http://127.0.0.1:18091';

for (const fullDocument of [true, false]) test(`classic scripts keep inline/external/repeated execution order (${fullDocument ? 'document' : 'fragment'})`, async () => {
  const scripts = '<script>window.order = ["setup"]; window.cfg = { amount: 3 };</script>'
    + '<script src="app.js"></script><script>window.order.push("middle");</script><script src="app.js"></script>';
  let reads = 0;
  const got = await convertWorkspaceHtml({ html: fullDocument ? `<html><head>${scripts}</head><body>ok</body></html>` : scripts,
    path: 'report.html', sessionId: 'session', readResource: async path => {
      assert.equal(path, 'app.js'); reads++;
      return { text: 'window.order.push(window.cfg.amount); // preserve newline' };
    } });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  const context = { window: {} };
  for (const match of got.package.html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) runInNewContext(match[1], context);
  runInNewContext(got.package.js, context);
  assert.deepEqual(Array.from(context.window.order), ['setup', 3, 'middle', 3]);
  assert.equal(reads, 1, 'read once, execute at every original reference');
});

for (const attrs of ['type="module"', 'async', 'defer', 'nomodule']) test(`unsupported script execution mode is explicit: ${attrs}`, async () => {
  let reads = 0;
  const got = await convertWorkspaceHtml({ html: `<script ${attrs} src="app.js"></script>`, path: 'report.html', sessionId: 's',
    readResource: async () => { reads++; return { text: 'window.executed = true' }; } });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'RESOURCE_UNSUPPORTED');
  assert.equal(got.error.unsupported[0].reason, 'script-execution-mode');
  assert.equal(reads, 0);
});

test('external script containing a closing tag is not embedded as HTML', async () => {
  const got = await convertWorkspaceHtml({ html: '<script src="app.js"></script>', path: 'report.html', sessionId: 's',
    readResource: async () => ({ text: 'window.literal = "</script><p>not markup</p>"' }) });
  assert.equal(got.ok, false);
  assert.equal(got.error.unsupported[0].reason, 'script-closing-tag');
});

function utf8(text) {
  return new TextEncoder().encode(text);
}

test('resolveImportResourcePath stays in the workspace and rejects parent segments', () => {
  assert.equal(resolveImportResourcePath('ops/web/index.html', 'logo.png'), 'ops/web/logo.png');
  assert.equal(resolveImportResourcePath('ops/web/index.html', '../secret.png'), null);
  assert.equal(resolveImportResourcePath('ops/web/index.html', '/tmp/x.png'), null);
  assert.equal(resolveImportResourcePath('ops/web/index.html', 'https://ex/a.png'), null);
});

test('convert extracts inline css/js from a full document without nested html wrappers or invented shine nodes', async () => {
  const html = '<!doctype html><html><head><style>p{color:red}</style></head><body><p>Hello</p><script>window.__x=1<\/script></body></html>';
  const snapshot = html;
  const got = await convertWorkspaceHtml({ html, path: 'ops/web/index.html', sessionId: 'sess-a' });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  assert.equal(html, snapshot);
  assert.doesNotMatch(got.package.html, /<html[\s>]/i);
  assert.doesNotMatch(got.package.html, /<body[\s>]/i);
  assert.match(got.package.html, /<p>Hello<\/p>/);
  assert.match(got.package.css, /color:red/);
  assert.match(got.package.js, /window\.__x=1/);
  assert.equal(got.package.node_map.length, 0);
  assert.doesNotMatch(got.package.html, /data-shine-node/);
  assert.equal(got.binding_state, 'UNBOUND_SAMPLE');
  assert.deepEqual(got.origin, { session_id: 'sess-a', path: 'ops/web/index.html' });
});

test('convert inlines relative images and keeps existing shine mapping only', async () => {
  const html = '<p data-shine-node="n_title">Hi</p><img src="logo.png" alt="">';
  const got = await convertWorkspaceHtml({
    html,
    path: 'ops/web/index.html',
    sessionId: 'sess-a',
    readResource: async (rel) => {
      assert.equal(rel, 'ops/web/logo.png');
      return { bytes: utf8('PNG'), content_type: 'image/png' };
    },
  });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  assert.match(got.package.html, /data:image\/png;base64,/);
  assert.equal(got.package.node_map.some(row => row.node_id === 'n_title'), true);
});

test('convert rewrites only src/href/css url() and leaves the same path in body text', async () => {
  const png = utf8('PNG');
  const html = '<p>see logo.png in copy</p><img src="logo.png" alt=""><style>.x{background:url(bg.png)}</style>';
  const got = await convertWorkspaceHtml({
    html,
    path: 'ops/web/index.html',
    sessionId: 'sess-a',
    readResource: async (rel) => {
      if (rel === 'ops/web/logo.png' || rel === 'ops/web/bg.png') return { bytes: png, content_type: 'image/png' };
      return null;
    },
  });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  const source = `${got.package.html}\n${got.package.css}`;
  assert.match(got.package.html, /see logo\.png in copy/);
  assert.match(got.package.html, /data:image\/png;base64,/);
  assert.doesNotMatch(got.package.html, /src="logo\.png"/);
  assert.match(source, /url\("data:image\/png;base64,/);
  assert.doesNotMatch(source, /url\(?['"]?bg\.png/);
});

test('convert inlines linked css and its relative url() without fetching the network', async () => {
  const got = await convertWorkspaceHtml({
    html: '<link rel="stylesheet" href="theme.css"><p>ok</p>',
    path: 'ops/web/index.html',
    sessionId: 'sess-a',
    readResource: async (rel) => {
      if (rel === 'ops/web/theme.css') return { text: '.x{background:url(bg.png)}', content_type: 'text/css' };
      if (rel === 'ops/web/bg.png') return { bytes: utf8('PNG'), content_type: 'image/png' };
      return null;
    },
  });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  assert.doesNotMatch(got.package.html, /theme\.css/);
  assert.match(got.package.css, /url\("data:image\/png;base64,/);
  assert.doesNotMatch(got.package.css, /bg\.png/);
});

test('convert reports missing, oversize, and network resources without fetching', async () => {
  const missing = await convertWorkspaceHtml({
    html: '<img src="gone.png" alt="">',
    path: 'a.html',
    sessionId: 'sess',
    readResource: async () => null,
  });
  assert.equal(missing.ok, false);
  assert.equal(missing.error.code, 'RESOURCE_MISSING');

  const net = await convertWorkspaceHtml({
    html: '<img src="https://cdn.example/a.png" alt="">',
    path: 'a.html',
    sessionId: 'sess',
  });
  assert.equal(net.ok, false);
  assert.equal(net.error.code, 'RESOURCE_UNSUPPORTED');

  const huge = await convertWorkspaceHtml({
    html: '<img src="big.png" alt="">',
    path: 'a.html',
    sessionId: 'sess',
    maxResourceBytes: 4,
    readResource: async () => ({ bytes: utf8('12345'), content_type: 'image/png' }),
  });
  assert.equal(huge.ok, false);
  assert.equal(huge.error.code, 'RESOURCE_UNSUPPORTED');
});

test('importer creates a candidate, cancel does not persist, confirm is idempotent and reopenable', async () => {
  const isolated = createIsolatedFetch({ token: TOKEN });
  const http = { base: BASE, token: TOKEN, fetchImpl: isolated.fetchImpl };
  const adapters = createLivePageAdapters({ documentsHttp: http });
  const importer = createHtmlImporter({ documents: adapters.documents });
  const html = '<p>copy me</p>';
  const made = await importer.createCandidate({
    html, path: 'sess-a/index.html', sessionId: 'session_alpha', title: 'copy me',
  });
  assert.equal(made.ok, true, JSON.stringify(made.error));
  assert.equal(made.binding_state, 'UNBOUND_SAMPLE');
  assert.ok(made.preview_id);

  const cancelled = await importer.createCandidate({
    html: '<p>temp</p>', path: 'sess-a/temp.html', sessionId: 'session_alpha',
  });
  await importer.cancel(cancelled.preview_id);
  const confirmCancelled = await importer.confirm(cancelled.preview_id, 'key_cancel');
  assert.equal(confirmCancelled.ok, false);

  const first = await importer.confirm(made.preview_id, 'key_import_1');
  assert.equal(first.ok, true, JSON.stringify(first.error));
  assert.equal(first.origin_path, 'sess-a/index.html');
  assert.equal(first.binding_state, 'UNBOUND_SAMPLE');
  const again = await importer.confirm(made.preview_id, 'key_import_1');
  assert.equal(again.page_id, first.page_id);
  assert.equal(again.version, first.version);

  const other = createLivePageAdapters({ documentsHttp: http });
  const otherImporter = createHtmlImporter({ documents: other.documents });
  const reopened = await otherImporter.reopen(first.page_id);
  assert.equal(reopened.ok, true);
  const pulled = other.assets.get(first.page_id);
  assert.equal(pulled.origin_path, 'sess-a/index.html');
  assert.equal(pulled.session_id, 'session_alpha');
});

test('same title from two sessions stay distinct pages', async () => {
  const isolated = createIsolatedFetch({ token: TOKEN });
  const http = { base: BASE, token: TOKEN, fetchImpl: isolated.fetchImpl };
  const importer = createHtmlImporter({ documents: createLivePageAdapters({ documentsHttp: http }).documents });
  const a = await importer.createCandidate({ html: '<p>one</p>', path: 'index.html', sessionId: 'sess_a', title: 'index.html' });
  const b = await importer.createCandidate({ html: '<p>two</p>', path: 'index.html', sessionId: 'sess_b', title: 'index.html' });
  const pageA = await importer.confirm(a.preview_id, 'key_a');
  const pageB = await importer.confirm(b.preview_id, 'key_b');
  assert.notEqual(pageA.page_id, pageB.page_id);
  assert.equal(pageA.session_id, 'sess_a');
  assert.equal(pageB.session_id, 'sess_b');
});
