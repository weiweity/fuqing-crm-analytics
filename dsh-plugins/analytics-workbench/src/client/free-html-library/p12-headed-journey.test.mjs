import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'os';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromeAvailable, evaluate, launchChrome } from '../../free-page/runtime/chrome-cdp.mjs';
import { AGENT_PACKAGE, createIsolatedFetch } from './p12-http-fakes.mjs';
import { PAGE_DOCUMENTS_PREFIX, PAGE_RESULT_PREFIX } from './page-http.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const pluginSrc = resolve(here, '../..');
const TOKEN = 'library-page-isolated-test-token-32chars';
const MIME = {
  '.mjs': 'text/javascript; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
};

function harnessHtml(origin) {
  return `<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>P12 headed journey</title></head>
<body>
  <p data-testid="fhl-status">idle</p>
  <p data-testid="fhl-title"></p>
  <p data-testid="fhl-version"></p>
  <p data-testid="fhl-html"></p>
  <p data-testid="fhl-binding"></p>
  <p data-testid="fhl-leave"></p>
  <button type="button" data-testid="fhl-generate">生成</button>
  <button type="button" data-testid="fhl-bind">绑定数据</button>
  <button type="button" data-testid="fhl-edit">进入编辑</button>
  <button type="button" data-testid="fhl-select">点选</button>
  <button type="button" data-testid="fhl-d6">D6确认</button>
  <button type="button" data-testid="fhl-d9">D9保存</button>
  <button type="button" data-testid="fhl-reopen">刷新重开</button>
  <button type="button" data-testid="fhl-rollback">回滚</button>
  <button type="button" data-testid="fhl-dirty-leave">脏稿离开</button>
  <script type="module">
    import { createLivePageAdapters } from '/src/client/free-html-library/live-adapters.mjs';
    import { createFreeHtmlLibraryStore } from '/src/client/free-html-library/store.mjs';
    const origin = ${JSON.stringify(origin)};
    const token = ${JSON.stringify(TOKEN)};
    const agentPackage = ${JSON.stringify(AGENT_PACKAGE)};
    const adapters = createLivePageAdapters({
      nativeGenerate: async () => agentPackage,
      documentsHttp: { base: origin, token, fetchImpl: (url, init) => fetch(url, init) },
      resultHttp: { base: origin, token, fetchImpl: (url, init) => fetch(url, init) },
    });
    const store = createFreeHtmlLibraryStore({ adapters, viewportWidth: 1440 });
    const status = document.querySelector('[data-testid="fhl-status"]');
    const paint = () => {
      const snap = store.getSnapshot();
      status.textContent = snap.liveStatus || snap.message || 'idle';
      document.querySelector('[data-testid="fhl-title"]').textContent = snap.current?.title || '';
      document.querySelector('[data-testid="fhl-version"]').textContent = String(snap.current?.version || '');
      document.querySelector('[data-testid="fhl-html"]').textContent = snap.current?.package?.html || '';
      document.querySelector('[data-testid="fhl-binding"]').textContent = snap.current?.binding_state || '';
      document.querySelector('[data-testid="fhl-leave"]').textContent = snap.pendingLeaveIntent || '';
    };
    store.subscribe(paint);
    document.querySelector('[data-testid="fhl-generate"]').onclick = async () => {
      store.setPrompt('经营杂志复盘');
      await store.generate();
      paint();
    };
    document.querySelector('[data-testid="fhl-bind"]').onclick = async () => {
      const read = await adapters.bridge.readResult({
        op: 'data.read', result_ref: 'result_fixture_1', mode: 'summary',
        manifest: { result_refs: ['result_fixture_1'], bindings: [] },
      });
      status.textContent = read.ok ? '已读授权结果' : '绑定失败';
      window.__bindOk = read.ok === true;
    };
    document.querySelector('[data-testid="fhl-edit"]').onclick = () => { store.enterEdit(); paint(); };
    document.querySelector('[data-testid="fhl-select"]').onclick = async () => {
      store.selectLocatable({ kind: 'static_element', node_id: 'n_title' });
      await store.previewPatch('局部新标题');
      paint();
    };
    document.querySelector('[data-testid="fhl-d6"]').onclick = async () => { await store.confirmPatch(); paint(); };
    document.querySelector('[data-testid="fhl-d9"]').onclick = async () => {
      store.markLocalDraft({ ...store.getSnapshot().current.package, js: 'window.__d9=true' });
      await store.saveDraft();
      paint();
    };
    document.querySelector('[data-testid="fhl-reopen"]').onclick = async () => {
      const id = store.getSnapshot().current.page_id;
      await store.openPage(id);
      paint();
    };
    document.querySelector('[data-testid="fhl-rollback"]').onclick = async () => { await store.rollback(1); paint(); };
    document.querySelector('[data-testid="fhl-dirty-leave"]').onclick = () => {
      store.markLocalDraft({ ...store.getSnapshot().current.package, html: store.getSnapshot().current.package.html + '<!--dirty-->' });
      store.requestLeave('home');
      paint();
    };
    window.__store = store;
    window.__fpReady = true;
  </script>
</body>
</html>`;
}

function createServer(originHolder) {
  const isolated = createIsolatedFetch({ token: TOKEN });
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://127.0.0.1');
      if (url.pathname.startsWith(PAGE_DOCUMENTS_PREFIX) || url.pathname.startsWith(PAGE_RESULT_PREFIX)) {
        const chunks = [];
        for await (const chunk of req) chunks.push(chunk);
        const raw = Buffer.concat(chunks).toString('utf8');
        const init = {
          method: req.method,
          headers: req.headers,
          body: raw || undefined,
        };
        const result = await isolated.fetchImpl(`http://127.0.0.1${url.pathname}${url.search}`, init);
        const body = JSON.stringify(await result.json());
        res.writeHead(result.status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
        res.end(body);
        return;
      }
      if (url.pathname === '/' || url.pathname === '/harness') {
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
        res.end(harnessHtml(originHolder.origin));
        return;
      }
      if (!url.pathname.startsWith('/src/')) {
        res.writeHead(404); res.end('not found'); return;
      }
      const rel = url.pathname.slice('/src/'.length);
      const abs = resolve(pluginSrc, rel);
      if (!abs.startsWith(pluginSrc + sep) && abs !== pluginSrc) {
        res.writeHead(403); res.end('forbidden'); return;
      }
      const body = await readFile(abs);
      res.writeHead(200, {
        'content-type': MIME[extname(abs)] || 'application/octet-stream',
        'cache-control': 'no-store',
      });
      res.end(body);
    } catch (error) {
      if (!res.headersSent) res.writeHead(500);
      res.end(String(error));
    }
  });
  server.on('connection', (socket) => { socket.on('error', () => {}); });
  return server;
}

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server.address().port;
}

async function click(session, testId) {
  await evaluate(session, `document.querySelector('[data-testid="${testId}"]').click(); true`);
}

test('headed Chrome: generate-preview-bind-select-D6-D9-reopen-rollback-leave on an isolated port', {
  timeout: 180_000,
  skip: chromeAvailable() ? false : 'Google Chrome is not installed',
}, async () => {
  const originHolder = { origin: '' };
  const server = createServer(originHolder);
  const userDataDir = await mkdtemp(join(tmpdir(), 'free-html-p12-headed-'));
  let chrome;
  try {
    const port = await listen(server);
    assert.notEqual(port, 6677);
    originHolder.origin = `http://127.0.0.1:${port}`;
    chrome = await launchChrome({ userDataDir, url: `${originHolder.origin}/harness` });
    await chrome.session.send('Page.navigate', { url: `${originHolder.origin}/harness` });
    await evaluate(chrome.session, `new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('harness timeout')), 15000);
      const tick = () => window.__fpReady ? (clearTimeout(t), resolve(true)) : setTimeout(tick, 50);
      tick();
    })`, 16000);
    await click(chrome.session, 'fhl-generate');
    await new Promise(resolve => setTimeout(resolve, 200));
    const html = await evaluate(chrome.session, `document.querySelector('[data-testid="fhl-html"]').textContent`);
    assert.match(html, /原生Agent标题/);
    assert.doesNotMatch(html, /示例标题/);
    await click(chrome.session, 'fhl-bind');
    await new Promise(resolve => setTimeout(resolve, 100));
    const bindOk = await evaluate(chrome.session, `window.__bindOk === true`);
    assert.equal(bindOk, true);
    await click(chrome.session, 'fhl-edit');
    await click(chrome.session, 'fhl-select');
    await new Promise(resolve => setTimeout(resolve, 150));
    await click(chrome.session, 'fhl-d6');
    await new Promise(resolve => setTimeout(resolve, 150));
    const afterD6 = await evaluate(chrome.session, `document.querySelector('[data-testid="fhl-html"]').textContent`);
    assert.match(afterD6, /局部新标题/);
    await click(chrome.session, 'fhl-d9');
    await new Promise(resolve => setTimeout(resolve, 150));
    const vAfterD9 = await evaluate(chrome.session, `document.querySelector('[data-testid="fhl-version"]').textContent`);
    assert.equal(vAfterD9, '3');
    await click(chrome.session, 'fhl-reopen');
    await new Promise(resolve => setTimeout(resolve, 100));
    await click(chrome.session, 'fhl-rollback');
    await new Promise(resolve => setTimeout(resolve, 150));
    const afterRollback = await evaluate(chrome.session, `document.querySelector('[data-testid="fhl-html"]').textContent`);
    assert.match(afterRollback, /原生Agent标题/);
    await click(chrome.session, 'fhl-dirty-leave');
    const leave = await evaluate(chrome.session, `document.querySelector('[data-testid="fhl-leave"]').textContent`);
    assert.equal(leave, 'home');
    assert.notEqual(port, 6677);
  } finally {
    if (chrome) await chrome.close();
    server.close();
    await rm(userDataDir, { recursive: true, force: true });
  }
});
