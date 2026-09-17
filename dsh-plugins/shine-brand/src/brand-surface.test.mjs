import test from 'node:test';
import assert from 'node:assert/strict';
import { applyCompetitionBrandSurface, PRODUCT_HEADLINE, PRODUCT_NAME } from './brand-surface.mjs';

test('brand surface sets DESIGN title and replaces upstream greeting', () => {
  const h1 = { textContent: 'Into the Unknown' };
  const created = [];
  const doc = {
    documentElement: {},
    title: 'DeepSeek Harness',
    head: { appendChild(node) { created.push(node); } },
    body: {},
    querySelector(sel) {
      if (sel.includes('rel="icon"') || sel.includes("rel='icon'") || sel.includes('rel="icon"') || sel.startsWith('link')) {
        return created[0] || null;
      }
      return null;
    },
    querySelectorAll(sel) {
      if (sel.includes('h1')) return [h1];
      return [];
    },
    createElement() {
      const node = { rel: '', href: '', setAttribute(name, value) { this[name] = value; } };
      return node;
    },
  };
  const out = applyCompetitionBrandSurface(doc);
  assert.equal(out.title, PRODUCT_NAME);
  assert.equal(doc.title, PRODUCT_NAME);
  assert.equal(h1.textContent, PRODUCT_HEADLINE);
  assert.equal(created[0].href, '/b0/brand/mark.svg');
});

test('brand surface hides 预览版 and does not rewrite nested headline hosts', () => {
  const nested = { textContent: 'Into the Unknown', children: { length: 1 } };
  const leaf = { textContent: '把增长问清楚', children: { length: 0 } };
  const badge = { textContent: '预览版', style: {}, setAttribute(name, value) { this[name] = value; } };
  const icon = { setAttribute(name, value) { this[name] = value; } };
  const doc = {
    documentElement: {},
    title: 'DeepSeek Harness',
    head: { appendChild() {} },
    querySelector(sel) {
      if (String(sel).includes('rel="icon"') || String(sel).startsWith('link')) return icon;
      return null;
    },
    querySelectorAll(sel) {
      const key = String(sel);
      if (key.includes('previewBadge')) return [badge];
      if (key.includes('h1')) return [nested, leaf];
      if (key.includes('span')) return [leaf];
      return [];
    },
    createElement() {
      return { rel: '', href: '', setAttribute() {} };
    },
  };
  const out = applyCompetitionBrandSurface(doc);
  assert.equal(nested.textContent, 'Into the Unknown');
  assert.equal(leaf.textContent, PRODUCT_HEADLINE);
  assert.equal(badge.hidden, '');
  assert.equal(badge.style.display, 'none');
  assert.equal(out.greeting, true);
  assert.equal(icon.href, '/b0/brand/mark.svg');
});
