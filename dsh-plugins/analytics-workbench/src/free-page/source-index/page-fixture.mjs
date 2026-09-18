/** Deterministic page packages for D48. Consumes coordinator fixtures; does not rewrite them. */
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

function repoRoot() {
  let dir = dirname(fileURLToPath(import.meta.url));
  while (dir !== dirname(dir)) {
    if (existsSync(join(dir, 'AGENTS.md')) && existsSync(join(dir, 'dsh-plugins'))) return dir;
    dir = dirname(dir);
  }
  throw new Error('repository root not found');
}

export function loadCoordinatorFixture(name) {
  return JSON.parse(readFileSync(resolve(repoRoot(), 'docs/hackathon/free-html-cockpit/fixtures', name), 'utf8'));
}

export const FROZEN_CONTRACT = loadCoordinatorFixture('frozen-contract-v0.json');
export const D48_CASES = loadCoordinatorFixture('d48-scope.fixture.json');

export const D48_HTML = '<!doctype html><html><body>'
  + '<h1 data-shine-node="n_title">示例标题</h1>'
  + '<p data-shine-node="n_lede">导语保持不变</p>'
  + '<canvas data-shine-region="r_chart" width="320" height="180"></canvas>'
  + '<span data-shine-node="n_forged">伪造标记</span>'
  + '</body></html>';

export const D48_CSS = "h1{font:600 28px/1.3 sans-serif}[data-shine-node='n_title']{color:#111}p{line-height:1.6}";
export const D48_JS = 'document.querySelector(\'[data-shine-region="r_chart"]\')?.getContext(\'2d\')';

export const D48_NODE_MAP = Object.freeze([
  Object.freeze({ node_id: 'n_title', kind: 'static_element', selector: "[data-shine-node='n_title']" }),
  Object.freeze({ node_id: 'n_lede', kind: 'static_element', selector: "[data-shine-node='n_lede']" }),
  Object.freeze({ node_id: 'r_chart', kind: 'dynamic_region', selector: "[data-shine-region='r_chart']" }),
]);

export function d48Package(overrides = {}) {
  return {
    html: D48_HTML,
    css: D48_CSS,
    js: D48_JS,
    resources: [],
    node_map: D48_NODE_MAP.map(row => ({ ...row })),
    ...overrides,
  };
}

export function frozenPackage() {
  const pkg = FROZEN_CONTRACT.asset.package;
  return {
    html: pkg.html,
    css: pkg.css,
    js: pkg.js,
    resources: Array.isArray(pkg.resources) ? pkg.resources.slice() : [],
    node_map: pkg.node_map.map(row => ({ ...row })),
  };
}

export const DUPLICATE_HTML = '<!doctype html><html><body>'
  + '<h1 data-shine-node="n_title">A</h1>'
  + '<h2 data-shine-node="n_title">B</h2>'
  + '</body></html>';
