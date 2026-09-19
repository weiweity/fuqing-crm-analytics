import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { join, resolve } from 'node:path';
import {
  HOVER_CLASS, HOVER_STYLE_ID, bindShineNodeHover, ensureShineNodes, htmlWithHoverRuntime, shineNodes, srcdocHasHoverRuntime,
} from './html-hover-layer.mjs';

const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');

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
