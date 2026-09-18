/** Source index for free-page packages. Locate failure never widens to whole page. */
import { sha256Hex } from '../hash.mjs';
import { jsMentions, parseCssRules, scanShineMarkers } from './parse.mjs';

export const SCHEMA_VERSION = 'free-page-source-index/v1';
export const IDENTITY_PATTERN = /^[A-Za-z0-9_.:-]{1,128}$/;
export const MAPPING_STALE = Object.freeze({ code: 'MAPPING_STALE', http: 409 });

const STATIC = 'static_element';
const REGION = 'dynamic_region';
const WHOLE = 'whole_page';

export function pageIdentity(value) {
  return typeof value === 'string' && IDENTITY_PATTERN.test(value);
}

function failLocate(reason) {
  return Object.freeze({
    ok: false,
    error: MAPPING_STALE,
    require: 'reselect',
    keep_draft: true,
    widen_to_whole_page: false,
    allowed_scope: 'none',
    reason,
  });
}

function packageHash(pagePackage) {
  const html = pagePackage?.html ?? '';
  const css = pagePackage?.css ?? '';
  const js = pagePackage?.js ?? '';
  return sha256Hex(`html:${html}\0css:${css}\0js:${js}`);
}

function tokenFor(version_hash, node_id, start, end) {
  return sha256Hex(`${version_hash}:${node_id}:${start}:${end}`).slice(0, 32);
}

function uniqueSelector(selector, node_id, kind) {
  const s = String(selector ?? '').trim();
  const quoted = [`[data-shine-node='${node_id}']`, `[data-shine-node="${node_id}"]`,
    `[data-shine-region='${node_id}']`, `[data-shine-region="${node_id}"]`];
  if (quoted.includes(s)) return true;
  if (kind === STATIC && s === `[data-shine-node='${node_id}']`) return true;
  return false;
}

function needlesFor(node) {
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

export function buildSourceIndex(pagePackage) {
  if (!pagePackage || typeof pagePackage !== 'object' || typeof pagePackage.html !== 'string') {
    throw Object.assign(new Error('INVALID_PAGE'), { code: 'INVALID_PAGE', http: 422 });
  }
  const html = pagePackage.html;
  const css = typeof pagePackage.css === 'string' ? pagePackage.css : '';
  const js = typeof pagePackage.js === 'string' ? pagePackage.js : '';
  const node_map = Array.isArray(pagePackage.node_map) ? pagePackage.node_map : [];
  const version_hash = packageHash(pagePackage);
  const markers = scanShineMarkers(html);
  const byId = new Map();
  const duplicates = [];
  for (const marker of markers) {
    const list = byId.get(marker.node_id) ?? [];
    list.push(marker);
    byId.set(marker.node_id, list);
  }
  for (const [node_id, list] of byId) {
    if (list.length > 1) duplicates.push(node_id);
  }

  const trusted = new Map();
  for (const row of node_map) {
    if (!row || !pageIdentity(row.node_id)) continue;
    if (row.kind !== STATIC && row.kind !== REGION) continue;
    trusted.set(row.node_id, row);
  }

  const nodes = {};
  const missing_from_dom = [];
  for (const [node_id, row] of trusted) {
    const wantAttr = row.kind === REGION ? 'region' : 'node';
    const matches = (byId.get(node_id) ?? []).filter(marker => marker.attr === wantAttr);
    if (matches.length !== 1 || duplicates.includes(node_id)) {
      missing_from_dom.push(node_id);
      continue;
    }
    const marker = matches[0];
    const mapping_token = tokenFor(version_hash, node_id, marker.start, marker.end);
    nodes[node_id] = Object.freeze({
      node_id,
      kind: row.kind,
      selector: row.selector,
      tag: marker.tag,
      html_range: Object.freeze({
        start: marker.start,
        inner_start: marker.inner_start,
        inner_end: marker.inner_end,
        end: marker.end,
        inner_text: html.slice(marker.inner_start, marker.inner_end),
        outer_text: html.slice(marker.start, marker.end),
      }),
      mapping_token,
      unique_selector: uniqueSelector(row.selector, node_id, row.kind),
      css_rules: parseCssRules(css).filter(rule => ruleTargets(rule.selector, node_id, row.kind, marker.tag)),
      js_ranges: jsMentions(js, needlesFor({ node_id, selector: row.selector })),
    });
  }

  const untrusted_markers = [];
  for (const [node_id, list] of byId) {
    if (!trusted.has(node_id)) untrusted_markers.push(node_id);
    void list;
  }

  return Object.freeze({
    schema_version: SCHEMA_VERSION,
    version_hash,
    nodes: Object.freeze(nodes),
    duplicates: Object.freeze(duplicates.slice()),
    untrusted_markers: Object.freeze(untrusted_markers),
    missing_from_dom: Object.freeze(missing_from_dom),
    html,
    css,
    js,
  });
}

function ruleTargets(selector, node_id, kind, tag) {
  const s = selector.trim();
  if (!s) return false;
  if (s === '*') return true;
  if (s === tag) return true;
  if (s.includes(`[data-shine-node='${node_id}']`) || s.includes(`[data-shine-node="${node_id}"]`)) return true;
  if (s.includes(`[data-shine-region='${node_id}']`) || s.includes(`[data-shine-region="${node_id}"]`)) return true;
  return false;
}

export function isSelectorUniqueToNode(selector, node_id) {
  const s = String(selector ?? '').trim();
  return s === `[data-shine-node='${node_id}']`
    || s === `[data-shine-node="${node_id}"]`
    || s === `[data-shine-region='${node_id}']`
    || s === `[data-shine-region="${node_id}"]`;
}

export function rebuildSourceIndex(pagePackage) {
  return buildSourceIndex(pagePackage);
}

export function locateSelection(index, selection) {
  if (!index || index.schema_version !== SCHEMA_VERSION) return failLocate('index');
  if (!selection || typeof selection !== 'object') return failLocate('selection');

  if (selection.kind === WHOLE) {
    if (selection.user_switched !== true) {
      return Object.freeze({
        ok: false,
        error: Object.freeze({ code: 'INVALID_PAGE', http: 422 }),
        require: 'user_switch_whole_page',
        keep_draft: true,
        widen_to_whole_page: false,
        allowed_scope: 'none',
        reason: 'whole_page_requires_user_switch',
      });
    }
    return Object.freeze({
      ok: true,
      scope: 'whole_package',
      allowed_scope: 'whole_package',
      node: null,
      selection: Object.freeze({ kind: WHOLE, user_switched: true }),
    });
  }

  if (selection.mapping === 'stale' || selection.mapping === 'forged') {
    return failLocate(selection.mapping);
  }

  const node_id = selection.node_id;
  if (!pageIdentity(node_id)) return failLocate('node_id');
  if (index.untrusted_markers.includes(node_id)) return failLocate('forged');
  if (index.duplicates.includes(node_id)) return failLocate('duplicate');
  if (typeof selection.version_hash === 'string' && selection.version_hash !== index.version_hash) {
    return failLocate('version_hash');
  }

  const node = index.nodes[node_id];
  if (!node) return failLocate('missing');
  if (typeof selection.mapping_token === 'string' && selection.mapping_token !== node.mapping_token) {
    return failLocate('mapping_token');
  }
  if (selection.kind !== STATIC && selection.kind !== REGION) return failLocate('kind');
  if (selection.kind !== node.kind) return failLocate('kind');

  const scope = node.kind === REGION ? 'declared_region' : 'exact_source_range';
  return Object.freeze({
    ok: true,
    scope,
    allowed_scope: scope,
    node,
    selection: Object.freeze({
      kind: node.kind,
      node_id,
      mapping: 'valid',
      mapping_token: node.mapping_token,
    }),
  });
}
