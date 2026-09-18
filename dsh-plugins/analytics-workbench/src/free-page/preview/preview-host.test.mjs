import test from 'node:test';
import assert from 'node:assert/strict';
import { mountPreviewHost } from './preview-host.mjs';
import { RUNAWAY_LOOP_PACKAGE, SAVED_COMPLEX_PACKAGE } from '../runtime/fixtures.mjs';
import { FREE_PAGE_SANDBOX } from '../runtime/isolation-policy.mjs';

function stubDom() {
  const doc = {
    defaultView: {
      requestAnimationFrame(fn) { this._fn = fn; return 1; },
      cancelAnimationFrame() {},
    },
  };
  function create(tag) {
    const node = {
      tagName: tag,
      attrs: Object.create(null),
      children: [],
      dataset: {},
      textContent: '',
      srcdoc: '',
      removed: false,
      ownerDocument: doc,
      setAttribute(key, value) { this.attrs[key] = String(value); },
      getAttribute(key) { return Object.hasOwn(this.attrs, key) ? this.attrs[key] : null; },
      addEventListener() {},
      append(...nodes) { this.children.push(...nodes); },
      appendChild(node) { this.children.push(node); return node; },
      remove() { this.removed = true; },
    };
    return node;
  }
  doc.createElement = create;
  const root = create('div');
  root.ownerDocument = doc;
  function query(sel) {
    const id = /data-testid="([^"]+)"/.exec(sel)?.[1];
    const walk = (node) => {
      if (!node || node.removed) return null;
      if (id && node.attrs['data-testid'] === id) return node;
      for (const child of node.children) {
        const found = walk(child);
        if (found) return found;
      }
      return null;
    };
    return walk(root);
  }
  return { root, query };
}

test('preview host exposes stop/restart/restore independent of the page iframe', async () => {
  const { root, query } = stubDom();
  const host = mountPreviewHost(root, {
    pageId: 'page_fixture_unbound',
    actorId: 'actor_fixture',
    savedPackage: SAVED_COMPLEX_PACKAGE,
    savedVersion: 1,
  });
  const loaded = await host.loadPackage(SAVED_COMPLEX_PACKAGE, 1);
  assert.equal(loaded.ok, true, JSON.stringify(loaded.error));
  const frame = query('[data-testid="fp-preview-frame"]');
  assert.ok(frame);
  assert.equal(frame.getAttribute('sandbox'), FREE_PAGE_SANDBOX);
  assert.equal(frame.getAttribute('referrerpolicy'), 'no-referrer');
  assert.match(frame.srcdoc, /已保存经营复盘/);
  assert.ok(query('[data-testid="fp-stop"]'));
  assert.ok(query('[data-testid="fp-restart"]'));
  assert.ok(query('[data-testid="fp-restore"]'));
  assert.equal(query('[data-testid="fp-host-ping"]'), null);
  assert.equal(query('[data-testid="fp-host-ticks"]'), null);

  host.stop('页面已停止');
  assert.equal(query('[data-testid="fp-preview-frame"]'), null);
  assert.match(query('[data-testid="fp-preview-status"]').textContent, /停止/);

  const restored = await host.restoreSaved();
  assert.equal(restored.ok, true, JSON.stringify(restored.error));
  assert.match(query('[data-testid="fp-preview-frame"]').srcdoc, /已保存经营复盘/);

  await host.loadPackage(RUNAWAY_LOOP_PACKAGE, 2);
  assert.match(query('[data-testid="fp-preview-frame"]').srcdoc, /while \(true\)/);
  host.stop();
  const again = await host.restoreSaved();
  assert.equal(again.ok, true);
  assert.equal(host.isolation().allowSameOrigin, false);
  assert.match(String(host.isolation().cpuIsolation), /unverified|not a CPU isolation claim|sandbox attributes/i);
  host.dispose();
});

test('chrome:false keeps MessageChannel iframe and hides host action buttons', async () => {
  const { root, query } = stubDom();
  const host = mountPreviewHost(root, {
    pageId: 'page_fixture_unbound',
    actorId: 'actor_fixture',
    chrome: false,
    frameTestId: 'fhl-iframe',
  });
  const loaded = await host.loadPackage(SAVED_COMPLEX_PACKAGE, 1);
  assert.equal(loaded.ok, true, JSON.stringify(loaded.error));
  assert.ok(query('[data-testid="fp-preview-host"]'));
  assert.ok(query('[data-testid="fhl-iframe"]'));
  assert.equal(query('[data-testid="fp-preview-frame"]'), null);
  assert.equal(query('[data-testid="fp-stop"]'), null);
  assert.equal(query('[data-testid="fp-restart"]'), null);
  host.dispose();
});
