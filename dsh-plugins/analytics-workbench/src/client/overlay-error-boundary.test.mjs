import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { OverlayErrorBoundary } from './overlay-error-boundary.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const plugin = resolve(here, '../..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const webReq = createRequire(join(upstream, 'apps/web/package.json'));
const React = webReq('react');
const { createRoot } = webReq('react-dom/client');
const act = typeof React.act === 'function' ? React.act : webReq('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');

function Boom() {
  throw new Error('confirm-panel-missing-scope');
}

test('OverlayErrorBoundary keeps siblings mounted and remounts on resetKey', async () => {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>');
  const previous = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const root = createRoot(dom.window.document.getElementById('root'));
  function Shell({ tick, boom }) {
    return React.createElement('div', { 'data-testid': 'dialog-shell' },
      React.createElement('button', { 'data-testid': 'footer-open' }, '打开'),
      React.createElement(OverlayErrorBoundary, { resetKey: tick },
        boom ? React.createElement(Boom) : React.createElement('p', { 'data-testid': 'panel-ok' }, 'ok'),
      ),
    );
  }
  await act(() => { root.render(React.createElement(Shell, { tick: 1, boom: true })); });
  assert.ok(dom.window.document.querySelector('[data-testid="dialog-shell"]'));
  assert.ok(dom.window.document.querySelector('[data-testid="footer-open"]'));
  assert.match(dom.window.document.querySelector('[data-testid="sm-overlay-render-error"]').textContent, /驾驶舱仍打开/);
  assert.equal(dom.window.document.querySelector('[data-testid="panel-ok"]'), null);
  await act(() => { root.render(React.createElement(Shell, { tick: 2, boom: false })); });
  assert.ok(dom.window.document.querySelector('[data-testid="panel-ok"]'));
  assert.equal(dom.window.document.querySelector('[data-testid="sm-overlay-render-error"]'), null);
  root.unmount();
  if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
  if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
  if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
});
