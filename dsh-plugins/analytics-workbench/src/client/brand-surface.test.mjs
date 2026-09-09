import test from 'node:test';
import assert from 'node:assert/strict';
import { applyCompetitionBrandSurface, PRODUCT_GREETING, PRODUCT_NAME } from './brand-surface.mjs';

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
  assert.equal(h1.textContent, PRODUCT_GREETING);
  assert.equal(created[0].href, '/b0/brand/mark.svg');
});
