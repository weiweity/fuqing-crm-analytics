import http from 'node:http';
import { once } from 'node:events';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, extname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { evaluate, launchChrome, screenshot } from './chrome-cdp.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const pluginSrc = resolve(here, '../..');
const repoRoot = resolve(pluginSrc, '../../..');

const MIME = {
  '.mjs': 'text/javascript; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
};

function harnessHtml() {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Lane B 隔离夹具</title>
  <style>
    body { margin: 0; font-family: "Noto Sans SC", "PingFang SC", sans-serif; background: #09050D; color: #FEFCFF; }
    #scenarios { display: flex; gap: 8px; flex-wrap: wrap; padding: 12px 16px; border-bottom: 1px solid rgba(211,195,232,.24); }
    button { background: #805D9D; color: #FEFCFF; border: 0; border-radius: 8px; padding: 8px 12px; }
    .fp-preview-host { padding: 16px; }
    .fp-preview-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }
    iframe { width: 100%; height: 420px; border: 1px solid rgba(211,195,232,.24); background: #fff; }
  </style>
</head>
<body>
  <div id="scenarios">
    <button type="button" data-testid="fp-load-saved">加载已保存</button>
    <button type="button" data-testid="fp-load-runaway">加载失控循环</button>
    <button type="button" data-testid="fp-load-yield">加载让步忙循环</button>
    <button type="button" data-testid="fp-load-leak">加载动态外联</button>
    <button type="button" data-testid="fp-host-ping">宿主仍可操作</button>
    <span data-testid="fp-host-ticks">0</span>
    <span data-testid="fp-host-clicks">0</span>
  </div>
  <div id="root"></div>
  <script type="module">
    import { mountPreviewHost } from '/src/free-page/preview/preview-host.mjs';
    import {
      DYNAMIC_LEAK_PACKAGE, RUNAWAY_LOOP_PACKAGE, RUNAWAY_YIELDING_PACKAGE, SAVED_COMPLEX_PACKAGE,
    } from '/src/free-page/runtime/fixtures.mjs';
    let ticks = 0;
    let clicks = 0;
    const tickNode = document.querySelector('[data-testid="fp-host-ticks"]');
    const clickNode = document.querySelector('[data-testid="fp-host-clicks"]');
    const beat = () => {
      ticks += 1;
      tickNode.textContent = String(ticks);
      requestAnimationFrame(beat);
    };
    requestAnimationFrame(beat);
    document.querySelector('[data-testid="fp-host-ping"]').onclick = () => {
      clicks += 1;
      clickNode.textContent = String(clicks);
    };
    const host = mountPreviewHost(document.getElementById('root'), {
      pageId: 'page_fixture_unbound',
      actorId: 'actor_fixture',
      savedPackage: SAVED_COMPLEX_PACKAGE,
      savedVersion: 1,
      version: 1,
    });
    window.__fpHost = host;
    await host.loadPackage(SAVED_COMPLEX_PACKAGE, 1);
    document.querySelector('[data-testid="fp-load-saved"]').onclick = () => host.restoreSaved();
    document.querySelector('[data-testid="fp-load-runaway"]').onclick = () => host.loadPackage(RUNAWAY_LOOP_PACKAGE, 2);
    document.querySelector('[data-testid="fp-load-yield"]').onclick = () => host.loadPackage(RUNAWAY_YIELDING_PACKAGE, 3);
    document.querySelector('[data-testid="fp-load-leak"]').onclick = () => host.loadPackage(DYNAMIC_LEAK_PACKAGE, 4);
    window.__fpReady = true;
  </script>
</body>
</html>`;
}

function ignoreSocketErrors(server) {
  server.on('connection', (socket) => { socket.on('error', () => {}); });
  server.on('error', () => {});
}

function createStaticServer() {
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://127.0.0.1');
      if (url.pathname === '/' || url.pathname === '/harness') {
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
        res.end(harnessHtml());
        return;
      }
      if (url.pathname === '/sink') {
        res.writeHead(204, { 'cache-control': 'no-store' });
        res.end();
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
    } catch {
      if (!res.headersSent) res.writeHead(404);
      res.end('not found');
    }
  });
  ignoreSocketErrors(server);
  return server;
}

function createEgressProxy() {
  const hits = [];
  const server = http.createServer((req, res) => {
    const target = new URL(req.url.startsWith('http') ? req.url : `http://${req.headers.host}${req.url}`);
    const loopback = target.hostname === '127.0.0.1' || target.hostname === 'localhost' || target.hostname === '::1';
    if (!loopback) {
      hits.push({ method: req.method, url: target.href, host: target.host, at: Date.now() });
      res.writeHead(451, { 'content-type': 'text/plain' });
      res.end('lane-b-proxy-blocked');
      return;
    }
    const upstream = http.request({
      hostname: target.hostname,
      port: target.port || 80,
      path: `${target.pathname}${target.search}`,
      method: req.method,
      headers: { ...req.headers, host: target.host },
    }, (up) => {
      res.writeHead(up.statusCode, up.headers);
      up.pipe(res);
    });
    upstream.on('error', () => {
      if (!res.headersSent) res.writeHead(502);
      res.end('proxy-upstream');
    });
    req.pipe(upstream);
  });
  server.on('connect', (req, socket) => {
    socket.on('error', () => {});
    hits.push({ method: 'CONNECT', url: req.url, host: req.url, at: Date.now() });
    socket.write('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');
    socket.end();
  });
  ignoreSocketErrors(server);
  return { server, hits };
}

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server.address().port;
}

async function click(session, testId) {
  await evaluate(session, `document.querySelector('[data-testid="${testId}"]').click(); true`);
}

async function ticks(session, timeoutMs = 2500) {
  return evaluate(session, `Number(document.querySelector('[data-testid="fp-host-ticks"]')?.textContent || 0)`, timeoutMs);
}

export async function runIsolationProbe({ evidenceDir } = {}) {
  const outDir = evidenceDir || join(repoRoot, 'docs/hackathon/free-html-cockpit/reports/lane-b');
  await mkdir(outDir, { recursive: true });
  const staticServer = createStaticServer();
  const proxy = createEgressProxy();
  let chrome;
  const userDataDir = await mkdtemp(join(tmpdir(), 'free-html-lane-b-chrome-'));
  const started = Date.now();
  try {
    const port = await listen(staticServer);
    const proxyPort = await listen(proxy.server);
    if (port === 6677 || proxyPort === 6677) throw new Error('refusing to bind 6677');
    const origin = `http://127.0.0.1:${port}`;
    chrome = await launchChrome({ userDataDir, proxyPort, url: `${origin}/harness` });
    await chrome.session.send('Page.navigate', { url: `${origin}/harness` });
    await chrome.session.send('Page.enable');
    try {
      await evaluate(chrome.session, `new Promise((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('harness timeout')), 15000);
        const tick = () => window.__fpReady ? (clearTimeout(t), resolve(true)) : setTimeout(tick, 50);
        tick();
      })`, 16000);
    } catch (error) {
      const href = await evaluate(chrome.session, 'String(location.href)', 3000).catch(() => 'unreadable');
      const readyState = await evaluate(chrome.session, 'String(document.readyState)', 3000).catch(() => 'unreadable');
      const body = await evaluate(chrome.session, '(document.body && document.body.innerText || "").slice(0, 1500)', 3000).catch(() => 'unreadable');
      throw new Error(`${error.message}; href=${href}; readyState=${readyState}; console=${JSON.stringify(chrome.session.console)}; exceptions=${JSON.stringify(chrome.session.exceptions)}; body=${body}`);
    }

    await new Promise((resolve) => setTimeout(resolve, 700));
    const savedShot = await screenshot(chrome.session);
    await writeFile(join(outDir, 't0-saved.png'), savedShot);
    const savedStatus = await evaluate(chrome.session, `document.querySelector('[data-testid="fp-preview-status"]')?.textContent`);
    const savedSrc = await evaluate(chrome.session, `document.querySelector('[data-testid="fp-preview-frame"]')?.srcdoc?.includes('已保存经营复盘')`);

    const ticksBefore = await ticks(chrome.session);
    const tRunaway = Date.now();
    await click(chrome.session, 'fp-load-runaway');
    await new Promise((resolve) => setTimeout(resolve, 1500));
    let ticksDuring = null;
    let clickDuring = false;
    let evaluateTimeout = false;
    try {
      ticksDuring = await ticks(chrome.session, 2500);
      await click(chrome.session, 'fp-host-ping');
      const clickCount = await evaluate(chrome.session, `Number(document.querySelector('[data-testid="fp-host-clicks"]')?.textContent || 0)`, 2500);
      clickDuring = clickCount >= 1;
    } catch (error) {
      evaluateTimeout = /timeout/i.test(error.message);
    }
    const runawayMs = Date.now() - tRunaway;
    let runawayShot = null;
    try {
      runawayShot = await screenshot(chrome.session);
      await writeFile(join(outDir, 't0-runaway.png'), runawayShot);
    } catch { /* renderer may be wedged */ }

    let closed = false;
    let restarted = false;
    let restored = false;
    let recoveryMs = null;
    const tRecover = Date.now();
    try {
      await click(chrome.session, 'fp-stop');
      await new Promise((resolve) => setTimeout(resolve, 300));
      closed = await evaluate(chrome.session, `document.querySelector('[data-testid="fp-preview-frame"]') == null`, 3000);
      await click(chrome.session, 'fp-restart');
      await new Promise((resolve) => setTimeout(resolve, 400));
      restarted = await evaluate(chrome.session, `Boolean(document.querySelector('[data-testid="fp-preview-frame"]'))`, 3000);
      await click(chrome.session, 'fp-restore');
      await new Promise((resolve) => setTimeout(resolve, 400));
      restored = await evaluate(chrome.session, `document.querySelector('[data-testid="fp-preview-frame"]')?.srcdoc?.includes('已保存经营复盘')`, 3000);
      recoveryMs = Date.now() - tRecover;
    } catch {
      await chrome.session.send('Page.reload', { ignoreCache: true }, 10000);
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        await evaluate(chrome.session, `new Promise((resolve, reject) => {
          const t = setTimeout(() => reject(new Error('reload timeout')), 15000);
          const tick = () => window.__fpReady ? (clearTimeout(t), resolve(true)) : setTimeout(tick, 50);
          tick();
        })`, 16000);
        restored = await evaluate(chrome.session, `document.querySelector('[data-testid="fp-preview-frame"]')?.srcdoc?.includes('已保存经营复盘')`);
        closed = false;
        restarted = false;
        recoveryMs = Date.now() - tRecover;
      } catch {
        restored = false;
      }
    }

    const restoredShot = await screenshot(chrome.session).catch(() => null);
    if (restoredShot) await writeFile(join(outDir, 't0-restored.png'), restoredShot);

    await click(chrome.session, 'fp-load-leak').catch(() => {});
    await new Promise((resolve) => setTimeout(resolve, 1200));
    const leakHits = proxy.hits.filter((row) => /example\.com/i.test(String(row.url || '') + String(row.host || '')));

    const hostOperable = !evaluateTimeout && clickDuring && (ticksDuring === null || ticksDuring > ticksBefore);
    const cpuIsolation = hostOperable
      ? 'observed-host-operable-during-srcdoc-runaway'
      : 'host-event-loop-blocked-or-unresponsive; sandbox attributes are not CPU isolation';

    const evidence = {
      schema: 'free-page-t0-evidence/v1',
      at: new Date().toISOString(),
      machine: {
        os: `${process.platform} ${process.arch}`,
        node: process.version,
      },
      browser: {
        path: process.env.FREE_PAGE_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        version: chrome.version,
        userAgent: chrome.userAgent,
        headless: true,
        viewport: '1280x800',
      },
      ports: { harness: port, proxy: proxyPort, chromeCdp: chrome.port, avoided: 6677 },
      sandbox: 'allow-scripts',
      allowSameOrigin: false,
      duration_ms: Date.now() - started,
      runaway_observe_ms: runawayMs,
      recovery_ms: recoveryMs,
      host_ticks_before: ticksBefore,
      host_ticks_during: ticksDuring,
      host_click_during_runaway: clickDuring,
      evaluate_timeout_during_runaway: evaluateTimeout,
      saved_srcdoc_contains_title: savedSrc,
      saved_status: savedStatus,
      iframe_closed: closed,
      iframe_restarted: restarted,
      saved_restored: restored,
      egress_proxy_hits: leakHits,
      egress_proxy_hit_count: leakHits.length,
      cpu_isolation: cpuIsolation,
      gates: {
        host_operable: hostOperable,
        close_restart: closed && restarted,
        saved_restore: Boolean(savedSrc && restored),
      },
      screenshots: {
        saved: relative(repoRoot, join(outDir, 't0-saved.png')),
        runaway: runawayShot ? relative(repoRoot, join(outDir, 't0-runaway.png')) : null,
        restored: restoredShot ? relative(repoRoot, join(outDir, 't0-restored.png')) : null,
      },
      note: 'Permission isolation is opaque-origin sandbox. CPU isolation is only whatever this Chrome run observed.',
    };
    await writeFile(join(outDir, 't0-evidence.json'), JSON.stringify(evidence, null, 2));
    return evidence;
  } finally {
    await chrome?.close();
    staticServer.closeAllConnections?.();
    proxy.server.closeAllConnections?.();
    await Promise.all([
      new Promise((resolve) => staticServer.close(() => resolve())),
      new Promise((resolve) => proxy.server.close(() => resolve())),
    ]);
    await rm(userDataDir, { recursive: true, force: true });
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const evidence = await runIsolationProbe();
  console.log(JSON.stringify(evidence, null, 2));
  const { host_operable: a, close_restart: b, saved_restore: c } = evidence.gates;
  process.exit(a && b && c ? 0 : 2);
}
