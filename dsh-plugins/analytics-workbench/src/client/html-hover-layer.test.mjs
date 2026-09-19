import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { join, resolve } from 'node:path';
import {
  HOVER_CLASS, HOVER_STYLE_ID, HOVER_STYLE_TEXT, attachHoverToIframe, bindShineNodeHover, ensureShineNodes,
  htmlWithHoverRuntime, injectHoverStyle, readIframeDocument, resolveIframe, shineNodes, srcdocHasHoverRuntime,
} from './html-hover-layer.mjs';

const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');

test('hover style targets shine-nodes without a contentDocument class toggle', () => {
  assert.match(HOVER_STYLE_TEXT, /\[data-shine-node\]:hover/);
});

test('htmlWithHoverRuntime injects style once and is idempotent', () => {
  const html = '<!doctype html><html><head></head><body><h2 data-shine-node="title-1">标题</h2></body></html>';
  const once = htmlWithHoverRuntime(html);
  assert.equal(srcdocHasHoverRuntime(once), true);
  assert.match(once, /2px solid #e8e8e8/);
  assert.match(once, /rgba\(247, 247, 247, 0\.5\)/);
  assert.match(once, /border-radius: 4px/);
  assert.match(once, /150ms ease-out/);
  assert.doesNotMatch(once, /<script/i);
  assert.equal(htmlWithHoverRuntime(once), once);
});

test('editMode hover adds the capsule class and leave removes it; click is not bound', () => {
  const dom = new JSDOM('<!doctype html><html><body><h2 data-shine-node="title-1">标题</h2><p>普通</p></body></html>');
  const node = dom.window.document.querySelector('[data-shine-node]');
  const clicks = [];
  node.addEventListener('click', () => clicks.push('host'));
  const stop = bindShineNodeHover(dom.window.document);
  assert.ok(dom.window.document.getElementById(HOVER_STYLE_ID));
  node.dispatchEvent(new dom.window.Event('mouseenter', { bubbles: false }));
  assert.equal(node.classList.contains(HOVER_CLASS), true);
  node.dispatchEvent(new dom.window.Event('mouseleave', { bubbles: false }));
  assert.equal(node.classList.contains(HOVER_CLASS), false);
  node.dispatchEvent(new dom.window.Event('click', { bubbles: true }));
  assert.deepEqual(clicks, ['host']);
  assert.equal(node.getAttribute('data-selected'), null);
  assert.equal(node.classList.contains('shine-node-selected'), false);
  stop();
  node.dispatchEvent(new dom.window.Event('mouseenter', { bubbles: false }));
  assert.equal(node.classList.contains(HOVER_CLASS), false);
  assert.equal(dom.window.document.getElementById(HOVER_STYLE_ID), null);
});

test('missing shine-node attributes fall back to common tags for phase-1 testing', () => {
  const dom = new JSDOM('<!doctype html><html><body><h2>标题</h2><p>段落</p></body></html>');
  const marked = ensureShineNodes(dom.window.document);
  assert.equal(marked.length >= 1, true);
  assert.equal(dom.window.document.querySelector('h2').getAttribute('data-shine-node'), 'test-1');
});

test('production hover does not invent shine-node ids', () => {
  const dom = new JSDOM('<!doctype html><html><body><h2>标题</h2><p>段落</p></body></html>');
  const stop = bindShineNodeHover(dom.window.document);
  assert.equal(shineNodes(dom.window.document).length, 0);
  assert.equal(dom.window.document.querySelector('h2').getAttribute('data-shine-node'), null);
  stop();
});

test('opaque iframe hover does not rewrite srcdoc', () => {
  const src = '<!doctype html><html><body><h2 data-shine-node="title-1">标题</h2></body></html>';
  const iframe = {
    tagName: 'IFRAME',
    srcdoc: src,
    getAttribute(name) { return name === 'srcdoc' ? src : null; },
    addEventListener() {},
    removeEventListener() {},
  };
  const stop = attachHoverToIframe(iframe);
  assert.equal(iframe.srcdoc, src);
  assert.equal(srcdocHasHoverRuntime(iframe.srcdoc), false);
  stop();
});

test('attachHoverToIframe no-ops without an iframe', () => {
  const stop = attachHoverToIframe({ querySelector() { return null; } });
  stop();
});

test('htmlWithHoverRuntime covers empty, body-only, and fragments', () => {
  assert.equal(htmlWithHoverRuntime(''), '');
  assert.equal(htmlWithHoverRuntime(null), '');
  const body = htmlWithHoverRuntime('<body data-x="1"><p>hi</p></body>');
  assert.match(body, /<body data-x="1"><style id="cockpit-hover-style">/);
  assert.doesNotMatch(body, /<script/i);
  const fragment = htmlWithHoverRuntime('<section data-shine-node="n">块</section>');
  assert.match(fragment, /^<style id="cockpit-hover-style">/);
  assert.match(fragment, /块/);
});

test('resolve/read/load attach without inventing srcdoc and style inject is idempotent', () => {
  assert.equal(resolveIframe(null), null);
  assert.equal(resolveIframe('iframe'), null);
  assert.deepEqual(shineNodes(null), []);
  bindShineNodeHover(null)();
  const wrapped = {
    tagName: 'DIV',
    querySelector(sel) { return sel === 'iframe' ? { tagName: 'IFRAME' } : null; },
  };
  assert.equal(resolveIframe(wrapped).tagName, 'IFRAME');
  assert.equal(readIframeDocument(null), null);
  assert.equal(readIframeDocument({
    get contentDocument() { throw new Error('opaque'); },
    get contentWindow() { throw new Error('opaque'); },
  }), null);
  assert.equal(readIframeDocument({ contentDocument: { body: {} } }), null);
  const dom = new JSDOM('<!doctype html><html><body></body></html>');
  const first = injectHoverStyle(dom.window.document);
  const second = injectHoverStyle(dom.window.document);
  assert.equal(first, second);
  assert.equal(dom.window.document.querySelectorAll(`#${HOVER_STYLE_ID}`).length, 1);
  assert.equal(injectHoverStyle(null), null);
  const src = '<!doctype html><html><body><h2 data-shine-node="title-1">标题</h2></body></html>';
  const inner = new JSDOM(src);
  const loads = [];
  const iframe = {
    tagName: 'IFRAME',
    srcdoc: src,
    contentDocument: inner.window.document,
    addEventListener(type, fn) { if (type === 'load') loads.push(fn); },
    removeEventListener(type, fn) {
      if (type === 'load') {
        const index = loads.indexOf(fn);
        if (index >= 0) loads.splice(index, 1);
      }
    },
  };
  const stop = attachHoverToIframe({ tagName: 'DIV', querySelector() { return iframe; } });
  assert.equal(iframe.srcdoc, src);
  assert.equal(srcdocHasHoverRuntime(iframe.srcdoc), false);
  assert.equal(inner.window.document.getElementById(HOVER_STYLE_ID) != null, true);
  inner.window.document.getElementById(HOVER_STYLE_ID).remove();
  loads[0]();
  assert.equal(inner.window.document.getElementById(HOVER_STYLE_ID) != null, true);
  stop();
  assert.equal(loads.length, 0);
});
