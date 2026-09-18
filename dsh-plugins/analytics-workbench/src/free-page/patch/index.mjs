/**
 * D6 patch preview. Confirm uses the original idempotency_key.
 * Locate failure does not become a whole-page patch.
 */
import { locateSelection, rebuildSourceIndex } from '../source-index/index.mjs';
import { analyzeImpact, assertPackage, htmlOutsideSelectionUnchanged } from './impact.mjs';
import { ERRORS, fail, isIdentity } from './codes.mjs';
import { replaceRange } from '../source-index/parse.mjs';

export { ERRORS, fail, isIdentity } from './codes.mjs';
export { analyzeImpact } from './impact.mjs';
export { createMemoryPageStore } from './store.mjs';

const DEFAULT_TTL_MS = 15 * 60 * 1000;

export function applyInnerText(pagePackage, located, text) {
  if (!located?.ok || located.scope !== 'exact_source_range') {
    return fail('MAPPING_STALE');
  }
  const range = located.node.html_range;
  const html = replaceRange(pagePackage.html, range.inner_start, range.inner_end, text);
  return { ok: true, package: { ...pagePackage, html } };
}

export function applyRegionOuter(pagePackage, located, outerHtml) {
  if (!located?.ok || located.scope !== 'declared_region') {
    return fail('MAPPING_STALE');
  }
  const range = located.node.html_range;
  const html = replaceRange(pagePackage.html, range.start, range.end, outerHtml);
  return { ok: true, package: { ...pagePackage, html } };
}

export function applyCss(pagePackage, css) {
  return { ok: true, package: { ...pagePackage, css } };
}

export function createPatchPreview({
  index,
  pagePackage,
  selection,
  proposed,
  page_id,
  session_id,
  base_version,
  idempotency_key,
  preview_id,
  now_ms,
  ttl_ms = DEFAULT_TTL_MS,
  scope_confirmed = false,
  impact_hash = null,
  binding_manifest = null,
}) {
  if (!isIdentity(page_id) || !isIdentity(session_id) || !isIdentity(preview_id) || !isIdentity(idempotency_key)) {
    return fail('INVALID_PAGE');
  }
  if (!Number.isInteger(base_version) || base_version < 1) return fail('INVALID_PAGE');
  if (!assertPackage(pagePackage) || !assertPackage(proposed)) return fail('INVALID_PAGE');
  if (!proposed.html.trim()) return fail('INVALID_PAGE', { reason: 'empty_html', submitted: false });

  const located = locateSelection(index, selection);
  if (!located.ok) {
    return Object.freeze({
      ...located,
      preview: null,
      submitted: false,
    });
  }

  const impact = analyzeImpact(index, located, proposed);
  if (located.scope !== 'whole_package' && (
    impact.foreign_html_nodes.length || impact.html_outside_selection
    || !htmlOutsideSelectionUnchanged(index, located, proposed.html)
  )) {
    return fail('INVALID_PAGE', {
      reason: impact.foreign_html_nodes.length ? 'foreign_html_change' : 'html_outside_selection',
      require: 'user_switch_whole_page',
      impact,
      preview: null,
      submitted: false,
    });
  }
  if (impact.expanded && (!scope_confirmed || impact_hash !== impact.impact_hash)) {
    return fail('SCOPE_REQUIRES_CONFIRMATION', {
      impact,
      impact_hash: impact.impact_hash,
      preview: null,
      submitted: false,
    });
  }

  const preview = Object.freeze({
    preview_id,
    page_id,
    session_id,
    status: 'PENDING',
    operation: 'PATCH',
    base_version,
    idempotency_key,
    expires_at_ms: now_ms + ttl_ms,
    selection: located.selection,
    scope: located.scope,
    impact,
    proposed_package: Object.freeze({
      html: proposed.html,
      css: proposed.css ?? '',
      js: proposed.js ?? '',
      resources: proposed.resources ?? [],
      node_map: proposed.node_map ?? pagePackage.node_map,
    }),
    binding_manifest,
    snapshot_version: base_version + 1,
  });
  return Object.freeze({ ok: true, preview, located, impact, submitted: false });
}

export function rebuildAfterApply(pagePackage) {
  return rebuildSourceIndex(pagePackage);
}
