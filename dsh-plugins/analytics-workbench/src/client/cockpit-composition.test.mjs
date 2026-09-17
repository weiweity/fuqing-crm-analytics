/** Geometry/session/DOM ownership tests; not native browser acceptance. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { join, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { COMPOSITION_PIN, compositionGeometry, createCockpitComposition, nativeCompositionTarget, leaseNativeComposition, leaseCompactNavigation } from './cockpit-composition.mjs';
const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');

test('composition is pinned and sizes continuous split, collapsed and narrow views without squeezing either minimum', () => {
  assert.equal(COMPOSITION_PIN, JSON.parse(readFileSync(join(plugin, 'toolchain.json'))).upstream_sha);
  assert.deepEqual(compositionGeometry(1160), { mode: 'split', canvas: 712, chat: 440 });
  assert.deepEqual(compositionGeometry(968, 900), { mode: 'split', canvas: 560, chat: 400 });
  assert.deepEqual(compositionGeometry(334), { mode: 'canvas', canvas: 334, chat: 0 });
  assert.deepEqual(compositionGeometry(334, 440, true, 'chat'), { mode: 'chat', canvas: 0, chat: 334 });
  assert.deepEqual(compositionGeometry(1160, 440, false), { mode: 'canvas', canvas: 1160, chat: 0 });
  assert.equal(compositionGeometry(0).mode, 'unavailable');
  assert.deepEqual(compositionGeometry(1160, NaN), compositionGeometry(1160));
  for (let width = 968; width < 2000; width += 13) for (let wanted = 400; wanted < 2000; wanted += 17) {
    const g = compositionGeometry(width, wanted);
    assert.equal(g.canvas + g.chat + 8, width); assert.ok(g.canvas >= 560 && g.chat >= 400);
  }
});

function sessionRow(id, main = 0) {
  return { id, retainedBy: main ? { mainView: main } : {} };
}
function sessionFixture() {
  let snapshot = { ids: ['s1', 's2'], byId: { s1: sessionRow('s1', 1), s2: sessionRow('s2') } };
  const listeners = new Set(), opens = [], panels = [];
  const update = values => { snapshot = { ...snapshot, ...values }; for (const fn of [...listeners]) fn(); };
  const sessions = {
    list: { getSnapshot: () => snapshot, subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); } },
    retain(id) {
      opens.push(id);
      const byId = {};
      for (const key of snapshot.ids) byId[key] = sessionRow(key, key === id ? 1 : 0);
      if (!byId[id]) byId[id] = sessionRow(id, 1);
      update({ byId });
      return { sessionId: id, release() {} };
    },
  };
  const composition = createCockpitComposition({ sessions, layout: { selectPanel: id => panels.push(id) } });
  return { composition, update, opens, panels, listeners };
}

test('composition binds exact saved session, never creates a session, and external navigation leaves drafts alone', () => {
  const f = sessionFixture(), c = f.composition;
  c.open('s2'); assert.equal(c.getSnapshot().open, true); assert.deepEqual(f.opens, ['s2']);
  assert.deepEqual(f.panels, [null]); assert.equal(c.getSnapshot().sessionId, 's2');
  c.open('s2'); assert.deepEqual(f.opens, ['s2']);
  c.setWidth(567); c.toggleChat(); assert.equal(c.getSnapshot().showChat, false);
  c.revealChat(); assert.equal(c.getSnapshot().narrowView, 'chat');
  f.update({ byId: { s1: sessionRow('s1', 1), s2: sessionRow('s2') } }); assert.equal(c.getSnapshot().open, false);
  c.open('s2'); assert.equal(c.getSnapshot().width, 567);
  f.update({ ids: ['s1'], byId: { s1: sessionRow('s1') } });
  assert.equal(c.getSnapshot().open, true); assert.equal(c.getSnapshot().sessionAvailable, false);
  c.bindSession('missing'); assert.deepEqual(f.opens, ['s2', 's2']);
  f.update({ ids: ['s1'], byId: { s1: sessionRow('s1', 1) } }); assert.equal(c.getSnapshot().open, false);
  c.fallback(); assert.equal(c.getSnapshot().fallback, true); assert.equal(f.panels.at(-1), 'cockpit');
  c.dispose(); assert.equal(f.listeners.size, 0);
  const before = [...f.opens]; c.bindSession('s1'); c.open('s1'); c.fallback(); assert.deepEqual(f.opens, before);
});

test('controlled seam leases the original native subtree, restores prior attributes, and rejects ambiguous structure', () => {
  const dom = new JSDOM('<div id="frame"><aside></aside><div id="center"><div data-slot="main" style="display:contents"><div data-slot="main.conversation" style="display:contents"><div data-phase="active"><header></header><div><div data-conversation-scroll><div data-composer-seat><textarea></textarea></div></div></div></div></div></div></div><div data-rightbar-col></div><div data-shell-overlay><div id="anchor"></div></div></div>');
  const doc = dom.window.document, anchor = doc.querySelector('#anchor');
  const target = nativeCompositionTarget(anchor); assert.ok(target);
  const input = target.native.querySelector('textarea'); input.value = '未发送的原生草稿';
  target.native.style.setProperty('--sm-cockpit-chat-width', '123px', 'important');
  target.native.setAttribute('aria-hidden', 'false');
  const before = target.native.outerHTML;
  const lease = leaseNativeComposition(target.native);
  assert.throws(() => leaseNativeComposition(target.native), /already leased/);
  lease.update(440, false); assert.equal(target.native.querySelector('textarea'), input);
  lease.update(0, true); assert.equal(target.native.inert, true); assert.equal(target.native.getAttribute('aria-hidden'), 'true');
  lease.dispose(); lease.dispose();
  assert.equal(target.native.outerHTML, before); assert.equal(input.value, '未发送的原生草稿');
  const alien = doc.createElement('div'); alien.setAttribute('data-conversation-scroll', ''); doc.querySelector('#frame').append(alien);
  assert.equal(nativeCompositionTarget(anchor), null); alien.remove();
  target.native.parentElement.style.display = 'block';
  assert.equal(nativeCompositionTarget(anchor), null);
  target.native.parentElement.style.display = 'contents';
  target.native.parentElement.setAttribute('data-slot', 'unknown');
  assert.equal(nativeCompositionTarget(anchor), null);
  target.native.parentElement.setAttribute('data-slot', 'main.conversation');
  assert.ok(nativeCompositionTarget(anchor));
  target.native.removeAttribute('data-phase'); assert.equal(nativeCompositionTarget(anchor), null);
  dom.window.close();
});

test('compact navigation preserves native widths, sidebar identity and preferences across expansion, resize and disposal', () => {
  const dom = new JSDOM('<div id="frame" style="grid-template-columns:280px minmax(0,1fr) 0px"><aside><button>导航</button></aside><main></main></div>');
  const frame = dom.window.document.querySelector('#frame'), sidebar = frame.firstElementChild;
  const button = sidebar.firstElementChild;
  const beforeStyle = frame.style.cssText, beforeChildren = frame.innerHTML;
  const lease = leaseCompactNavigation(frame, frame.lastElementChild);
  assert.equal(lease.update(390), true); assert.ok(frame.hasAttribute('data-sm-cockpit-compact'));
  assert.equal(frame.style.gridTemplateColumns, '280px minmax(0,1fr) 0px');
  assert.equal(frame.style.getPropertyValue('--sm-cockpit-sidebar-width'), '280px');
  frame.setAttribute('data-sidebar-collapsed', '');
  assert.equal(lease.update(390), false);
  frame.removeAttribute('data-sidebar-collapsed'); frame.style.gridTemplateColumns = '350px minmax(0,1fr) 0px';
  assert.equal(lease.update(390), true);
  assert.equal(frame.style.getPropertyValue('--sm-cockpit-sidebar-width'), '350px');
  assert.equal(lease.update(1020), false); assert.equal(frame.hasAttribute('data-sm-cockpit-compact'), false);
  assert.equal(sidebar.firstElementChild, button);
  frame.style.gridTemplateColumns = '280px minmax(0,1fr) 0px'; lease.dispose(); lease.dispose();
  assert.equal(frame.style.cssText, beforeStyle); assert.equal(frame.innerHTML, beforeChildren);
  assert.deepEqual(frame.getAttributeNames(), ['id', 'style']); dom.window.close();
});
