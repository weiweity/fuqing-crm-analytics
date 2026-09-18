/** Diff a proposed package against the selected scope. Shared CSS/JS is expansion; HTML outside the selection is not silently accepted. */
import { sha256Hex } from '../hash.mjs';
import { partitionCss, proposedKeepsUnowned } from '../source-index/parse.mjs';
import { buildSourceIndex, isSelectorUniqueToNode } from '../source-index/index.mjs';

const PAGE_WIDE_JS = /document\s*\.\s*(body|documentElement|write|replaceChildren)\b/;

function nodeMapFromIndex(index) {
  return Object.values(index.nodes).map(node => ({
    node_id: node.node_id,
    kind: node.kind,
    selector: node.selector,
  }));
}

function htmlChangedNodes(index, proposedIndex) {
  const changed = [];
  for (const id of Object.keys(index.nodes)) {
    const before = index.nodes[id].html_range.outer_text;
    const after = proposedIndex.nodes[id]?.html_range.outer_text;
    if (before !== after) changed.push(id);
  }
  return changed;
}

export function htmlOutsideSelectionUnchanged(index, located, proposedHtml) {
  if (located.scope === 'whole_package') return true;
  const range = located.node?.html_range;
  if (!range || typeof proposedHtml !== 'string') return false;
  const prefix = index.html.slice(0, range.start);
  const suffix = index.html.slice(range.end);
  if (!proposedHtml.startsWith(prefix) || !proposedHtml.endsWith(suffix)) return false;
  if (proposedHtml.length < prefix.length + suffix.length) return false;
  const middle = proposedHtml.slice(prefix.length, proposedHtml.length - suffix.length);
  let proposedIndex;
  try {
    proposedIndex = buildSourceIndex({
      html: proposedHtml,
      css: index.css,
      js: index.js,
      node_map: nodeMapFromIndex(index),
    });
  } catch {
    return false;
  }
  const next = proposedIndex.nodes[located.node.node_id];
  return Boolean(next) && next.html_range.outer_text === middle;
}

function cssDiff(index, proposedCss, selectedId) {
  const before = partitionCss(index.css);
  const after = partitionCss(proposedCss);
  const changed = [];
  if (before.atBlocks.join('\0') !== after.atBlocks.join('\0')) {
    changed.push(Object.freeze({
      selector: '@media/@supports/@keyframes',
      unique_to_selection: false,
      shared: true,
    }));
  }
  const beforeBag = bagRules(before.rules);
  const afterBag = bagRules(after.rules);
  const keys = new Set([...beforeBag.keys(), ...afterBag.keys()]);
  for (const key of keys) {
    if ((beforeBag.get(key) ?? 0) === (afterBag.get(key) ?? 0)) continue;
    const selector = key.slice(0, key.indexOf('\n'));
    const unique = selectedId ? isSelectorUniqueToNode(selector, selectedId) : false;
    changed.push(Object.freeze({ selector, unique_to_selection: unique, shared: !unique }));
  }
  return changed;
}

function bagRules(rules) {
  const bag = new Map();
  for (const rule of rules) {
    const key = `${rule.selector}\n${rule.body}`;
    bag.set(key, (bag.get(key) ?? 0) + 1);
  }
  return bag;
}

function regionNeedles(node) {
  const id = node.node_id;
  return [
    id,
    `[data-shine-node='${id}']`,
    `[data-shine-node="${id}"]`,
    `[data-shine-region='${id}']`,
    `[data-shine-region="${id}"]`,
    node.selector,
  ].filter(Boolean);
}

function jsImpact(index, proposedJs, located) {
  if (index.js === proposedJs) return { changed: false, shared: false };
  if (located.scope === 'whole_package') return { changed: true, shared: false };
  if (located.scope === 'exact_source_range') return { changed: true, shared: true };
  const node = located.node;
  if (!node) return { changed: true, shared: true };
  const stillTargets = regionNeedles(node).some(needle => proposedJs.includes(needle));
  const otherIds = Object.keys(index.nodes).filter(id => id !== node.node_id);
  const mentionsOther = otherIds.some(id => proposedJs.includes(id));
  const outsideOwned = node.js_ranges.length
    ? !proposedKeepsUnowned(index.js, proposedJs, node.js_ranges)
    : true;
  const pageWide = PAGE_WIDE_JS.test(proposedJs) && !PAGE_WIDE_JS.test(index.js);
  return {
    changed: true,
    shared: !stillTargets || mentionsOther || outsideOwned || pageWide,
  };
}

export function analyzeImpact(index, located, proposedPackage) {
  const proposedCss = proposedPackage?.css ?? '';
  const proposedJs = proposedPackage?.js ?? '';
  let proposedIndex;
  try {
    proposedIndex = buildSourceIndex({
      html: proposedPackage?.html ?? '',
      css: proposedCss,
      js: proposedJs,
      resources: proposedPackage?.resources ?? [],
      node_map: proposedPackage?.node_map ?? nodeMapFromIndex(index),
    });
  } catch {
    proposedIndex = { nodes: {} };
  }
  const html_changed_nodes = htmlChangedNodes(index, proposedIndex);
  const selectedId = located.node?.node_id ?? null;
  const css_changed = cssDiff(index, proposedCss, selectedId);
  const js = jsImpact(index, proposedJs, located);
  const html_outside_selection = located.scope !== 'whole_package'
    && !htmlOutsideSelectionUnchanged(index, located, proposedPackage?.html ?? '');
  const foreign_html_nodes = located.scope === 'whole_package'
    ? []
    : html_changed_nodes.filter(id => id !== selectedId);
  const shared_css = css_changed.some(rule => rule.shared);
  const shared_js = js.shared && js.changed;
  const expanded = located.scope === 'whole_package' ? false : (shared_css || shared_js);
  const unchanged_nodes = Object.keys(index.nodes).filter(id => !html_changed_nodes.includes(id));
  const canvas_nodes = Object.values(index.nodes)
    .filter(node => node.kind === 'dynamic_region' && node.tag === 'canvas')
    .map(node => node.node_id);
  const payload = {
    scope: located.scope,
    html_changed_nodes,
    foreign_html_nodes,
    html_outside_selection,
    css_changed,
    shared_css,
    shared_js,
    js_changed: js.changed,
    expanded,
  };
  return Object.freeze({
    ...payload,
    html_changed_nodes: Object.freeze(html_changed_nodes),
    foreign_html_nodes: Object.freeze(foreign_html_nodes),
    css_changed: Object.freeze(css_changed),
    unchanged_nodes: Object.freeze(unchanged_nodes),
    canvas_html_unchanged: canvas_nodes.every(id => !html_changed_nodes.includes(id)),
    js_bytes_unchanged: index.js === proposedJs,
    css_bytes_unchanged: index.css === proposedCss,
    impact_hash: sha256Hex(JSON.stringify(payload)).slice(0, 32),
  });
}

export function assertPackage(pagePackage) {
  if (!pagePackage || typeof pagePackage !== 'object') return false;
  if (typeof pagePackage.html !== 'string') return false;
  if (pagePackage.css != null && typeof pagePackage.css !== 'string') return false;
  if (pagePackage.js != null && typeof pagePackage.js !== 'string') return false;
  return true;
}
