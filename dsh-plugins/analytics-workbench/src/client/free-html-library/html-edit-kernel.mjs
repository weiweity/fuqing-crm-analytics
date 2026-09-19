/** Literal HTML text patch. Reuses source-index + patch; does not run AI instructions. */

import { buildSourceIndex, locateSelection } from '../../free-page/source-index/index.mjs';
import { applyInnerText, createPatchPreview } from '../../free-page/patch/index.mjs';

export function escapeReplacementText(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}

function fail(code, message, extra = {}) {
  return { ok: false, error: { code, message, ...extra } };
}

export function boundNodeIds(manifest) {
  const ids = new Set();
  for (const item of manifest?.bindings ?? []) {
    if (typeof item?.node_id === 'string' && item.node_id) ids.add(item.node_id);
  }
  return ids;
}

function selectionRequest(selection) {
  if (!selection) return {};
  if (selection.kind === 'whole_page') {
    return { kind: 'whole_page', user_switched: selection.user_switched === true };
  }
  return {
    kind: selection.kind,
    node_id: selection.node_id,
    mapping: selection.mapping,
    mapping_token: selection.mapping_token,
    version_hash: selection.version_hash,
  };
}

export function previewLiteralText({
  pkg,
  selection,
  replacementText,
  instruction,
  aiInstruction,
  page_id = 'page_local',
  session_id = 'session_local',
  base_version = 1,
  preview_id = 'preview_local',
  idempotency_key = 'idem_local',
  now_ms = Date.now(),
  binding_manifest = null,
} = {}) {
  if (typeof aiInstruction === 'string' && aiInstruction.length > 0) {
    return fail(
      'AI_INSTRUCTION_UNSUPPORTED',
      '本内核不执行自然语言 instruction；请传入字面 replacementText',
    );
  }
  const literal = typeof replacementText === 'string' ? replacementText : instruction;
  if (typeof literal !== 'string') {
    return fail('INVALID_PAGE', 'replacementText 必须是字面新文本');
  }
  if (!pkg) return fail('INVALID_PAGE', '缺少 package');
  const index = buildSourceIndex(pkg);
  const request = selectionRequest(selection);
  const located = locateSelection(index, request);
  if (!located.ok) {
    return fail(located.error?.code || 'MAPPING_STALE', '无法定位源码范围；不会扩大为整页', {
      requireReselect: true,
      widenToPage: false,
      located,
    });
  }
  if (located.scope !== 'exact_source_range') {
    return fail('TEXT_REPLACE_UNSUPPORTED', '当前范围不能做字面文本替换', {
      scope: located.scope,
      requireReselect: located.scope !== 'whole_package',
    });
  }
  if (located.node?.js_ranges?.length || /<[a-z!/]/i.test(located.node?.html_range?.inner_text ?? '')) {
    return fail('TEXT_REPLACE_UNSUPPORTED', '包含子节点或动态逻辑的区域暂不支持直接改字');
  }
  const nodeId = located.node?.node_id;
  if (nodeId && boundNodeIds(binding_manifest).has(nodeId)) {
    return fail('BINDING_PROTECTED', '绑定节点禁止普通文本替换', { node_id: nodeId });
  }
  const applied = applyInnerText(pkg, located, escapeReplacementText(literal));
  if (!applied.ok) {
    return fail(applied.error?.code || 'MAPPING_STALE', '文本替换失败', { located });
  }
  const made = createPatchPreview({
    index,
    pagePackage: pkg,
    selection: request,
    proposed: applied.package,
    page_id,
    session_id,
    base_version,
    idempotency_key,
    preview_id,
    now_ms,
    binding_manifest,
  });
  if (!made.ok) {
    return fail(made.error?.code || 'INVALID_PAGE', '补丁预览被拒绝', {
      impact: made.impact,
      require: made.require,
      located,
    });
  }
  return {
    ok: true,
    package: applied.package,
    located,
    preview: made.preview,
    replacementText: literal,
    literalSource: typeof replacementText === 'string' ? 'replacementText' : 'instruction',
  };
}

export async function submitHtmlPatchPreview(documents, { page_id, base_version, package: pagePackage, title } = {}) {
  if (!documents?.patchPreview) return fail('http_not_configured', '没有 documents.patchPreview');
  if (!page_id || !pagePackage) return fail('INVALID_PAGE', 'patch-preview 需要 page_id 与 package');
  try {
    const got = await documents.patchPreview({ page_id, base_version, package: pagePackage, title });
    if (!got.ok) return fail(got.reason || 'http_not_configured', '无法创建 patch 预览');
    return { ok: true, preview_id: got.body?.preview_id, body: got.body };
  } catch (error) {
    return fail(error.code || 'PAGE_HTTP', error.message || 'patch-preview 失败', {
      status: error.status,
      recoverable: error.status == null || error.status >= 500,
    });
  }
}
