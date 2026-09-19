/** Host workspace file helpers from apply(); not a native Settings run. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';

const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const outfile = join(plugin, 'lib/test-workspace-files-host.mjs');
await createRequire(web.resolve('vite/package.json'))('esbuild').build({
  absWorkingDir: plugin,
  entryPoints: ['src/client/index.tsx'],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2022',
  jsx: 'automatic',
  loader: { '.css': 'empty' },
  external: ['react', 'react/jsx-runtime', 'react-dom', '@deepseek-ai/dsh-client-store'],
  logLevel: 'silent',
});
const { apply } = await import(pathToFileURL(outfile).href);

function sessionList(id = 'session-visible') {
  return {
    phase: 'ready',
    ids: [id],
    byId: { [id]: { id, retainedBy: { mainView: 1 } } },
  };
}

function mount(extra = {}) {
  const entries = [];
  const effects = [];
  apply({
    effect: factory => { effects.push(factory()); },
    get() { return undefined; },
    theme: {
      overrideTokens: () => () => {},
      getTheme: () => ({ active: { colorScheme: 'light' }, preference: 'light' }),
    },
    layout: { selectPanel() {} },
    sessions: {
      list: { getSnapshot: () => sessionList(), subscribe: () => () => {} },
      retain: () => ({ release() {} }),
      create() { assert.fail('no session create'); },
    },
    slots: {
      inject: (_name, callback) => effects.push(callback()),
      register: (options, component) => {
        entries.push({ options, component });
        return () => {};
      },
    },
    on: () => () => {},
    ...extra,
  });
  const cockpit = entries.find(row => row.options.name === 'main' && row.options.key === 'cockpit');
  return { entries, effects, inject: cockpit.options.inject() };
}

test('workspace helpers no-op without remote, then list/read/open through the host APIs', async () => {
  const missing = mount();
  assert.deepEqual(await missing.inject.listWorkspaceFiles(), []);
  assert.equal(await missing.inject.readWorkspaceFile({ sessionId: 'session-visible', path: 'a.html' }), null);
  missing.inject.openWorkspaceFile({ sessionId: 'session-visible', path: 'a.html' });
  for (const dispose of missing.effects) if (typeof dispose === 'function') dispose();

  const listed = [];
  const opened = [];
  const reads = [];
  const withApi = mount({
    remote: {
      workspaceFiles: {
        async list(sessionId, path) {
          listed.push({ sessionId, path });
          if (path === '.') {
            return { ok: true, value: { path: '', entries: [
              { name: 'week.html', type: 'file' },
              { name: 'notes.txt', type: 'file' },
            ], truncated: false } };
          }
          return { ok: true, value: { path, entries: [] } };
        },
        async read(sessionId, path, range) {
          reads.push({ sessionId, path, range });
          if (path === 'direct.html') return { text: '<p>direct</p>' };
          if (path === 'wrapped.html') return { value: { text: '<p>wrapped</p>' } };
          if (path === 'remote.html') return { ok: true, value: { text: '<p>remote</p>', eof: true, lines: 1, offset: 1 } };
          if (path === 'paged.html') {
            if (range?.offset === 1) return { ok: true, value: { text: '<p>one</p>', eof: false, lines: 1, offset: 1 } };
            return { ok: true, value: { text: '<p>two</p>', eof: true, lines: 1, offset: 2 } };
          }
          if (path === 'empty.html') return { text: '' };
          throw new Error('read failed');
        },
      },
      session: { prompt: async () => ({ ok: false }) },
    },
    sidebarRight: { openResource: address => opened.push(address) },
  });
  const files = await withApi.inject.listWorkspaceFiles();
  assert.deepEqual(listed, [{ sessionId: 'session-visible', path: '.' }]);
  assert.deepEqual(files.map(item => item.path), ['week.html']);
  assert.equal(await withApi.inject.readWorkspaceFile({ sessionId: 'session-visible', path: 'direct.html' }), '<p>direct</p>');
  assert.equal(await withApi.inject.readWorkspaceFile({ sessionId: 'session-visible', path: 'wrapped.html' }), '<p>wrapped</p>');
  assert.equal(await withApi.inject.readWorkspaceFile({ sessionId: 'session-visible', path: 'remote.html' }), '<p>remote</p>');
  assert.equal(await withApi.inject.readWorkspaceFile({ sessionId: 'session-visible', path: 'paged.html' }), '<p>one</p>\n<p>two</p>');
  assert.equal(await withApi.inject.readWorkspaceFile({ sessionId: 'session-visible', path: 'empty.html' }), null);
  assert.equal(await withApi.inject.readWorkspaceFile({ sessionId: 'session-visible', path: 'missing.html' }), null);
  assert.equal(await withApi.inject.readWorkspaceFile({ path: 'no-session.html' }), null);
  assert.deepEqual(reads[0].range, { offset: 1, limit: 4000 });
  withApi.inject.openWorkspaceFile({ sessionId: 'session-visible', path: 'week.csv' });
  withApi.inject.openWorkspaceFile({ sessionId: 'session-visible', path: '../secret.html' });
  withApi.inject.openWorkspaceFile({ sessionId: 'session-visible' });
  assert.deepEqual(opened, ['dsh-resource://file/session/session-visible/week.csv']);
  for (const dispose of withApi.effects) if (typeof dispose === 'function') dispose();
});

test('capture the visible source before native panel release; never choose the first listed session', () => {
  const listeners = new Set();
  let snapshot = { phase: 'ready', ids: ['older', 'visible'], byId: {
    older: { id: 'older', retainedBy: {} }, visible: { id: 'visible', retainedBy: { mainView: 1 } },
  } };
  const mounted = mount({ sessions: {
    list: { getSnapshot: () => snapshot, subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); } },
    retain() { assert.fail('no invented source retain'); }, create() { assert.fail('no create'); },
  } });
  const notify = () => { for (const listener of listeners) listener(); };
  assert.equal(mounted.inject.delivery.getSessionId(), 'visible');
  snapshot.byId.visible.retainedBy = {}; notify();
  assert.equal(mounted.inject.delivery.getSessionId(), 'visible', 'native mainView release must not erase the captured source');
  snapshot.byId.older.retainedBy = { mainView: 1 }; notify();
  assert.equal(mounted.inject.delivery.getSessionId(), 'older', 'an actually observed new mainView changes the source');
  snapshot = { phase: 'ready', ids: [], byId: {} }; notify();
  assert.equal(mounted.inject.delivery.getSessionId(), null, 'removed source is not retained as a fallback');
  for (const dispose of mounted.effects) if (typeof dispose === 'function') dispose();
  assert.equal(listeners.size, 0);
});
