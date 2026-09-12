/** Ask → PATCH_BLOCK suggestion. Never writes facts. HTTP fail-closed. */
import { parsePatchBlock } from './schema.mjs';
import { BOARD_SPEC_KINDS } from './kinds.mjs';
import { catalogFromGsvItems } from './facts-from-result.mjs';

function fail(code, message) {
  return { ok: false, error: { code, message } };
}

export function titleFromAsk(ask) {
  const text = String(ask || '').trim();
  const quoted = text.match(/[「"]([^」"]+)[」"]/);
  if (quoted) return quoted[1].trim();
  return text.replace(/^把标题改成/, '').trim() || text;
}

export function metricFromAsk(ask) {
  const text = String(ask || '');
  if (!/换成|改成|口径/.test(text)) return null;
  if (/零售\s*GSV|retail_gsv/.test(text)) return 'retail_gsv';
  return null;
}

export function isFactsQuestion(ask) {
  const text = String(ask || '');
  if (/改成|换成|加一块|标题|口径/.test(text)) return false;
  return /多少|是多少|GSV\s*是多少|这个数字/.test(text);
}

function selectedBlock(state) {
  const blocks = state?.spec?.blocks;
  if (!Array.isArray(blocks)) return null;
  return blocks.find((block) => block.block_id === state.selected_block_id) ?? null;
}

export function layoutFromAsk(ask) {
  const match = String(ask || '').match(/布局\s*(-?\d+)\s+(-?\d+)\s+(\d+)\s+(\d+)/);
  if (!match) return null;
  return { x: Number(match[1]), y: Number(match[2]), w: Number(match[3]), h: Number(match[4]) };
}

export function refreshSelectedFacts(state, items) {
  const block = selectedBlock(state);
  const id = block && typeof block.source_result_id === 'string' ? block.source_result_id : '';
  if (!id) return fail('ASK_FACTS', '当前块没有绑定结果，未写入。');
  const catalog = catalogFromGsvItems(items);
  const row = catalog[id];
  if (!row) return fail('ASK_FACTS', '当前块没有可刷新的绑定结果，未写入。');
  return {
    ok: true,
    value: { ...state, facts: { ...(state.facts || {}), [id]: row }, pending_patch: null },
    refreshed: true,
  };
}

function patchForAsk(state, ask) {
  const block = selectedBlock(state);
  if (!block) return fail('CANVAS_NO_SELECTION', '先点选一块');
  if (isFactsQuestion(ask)) {
    return fail('ASK_FACTS', '问数不改数字。打开画布按绑定刷新，未写入。');
  }
  const layout = layoutFromAsk(ask);
  if (layout) {
    return parsePatchBlock({
      block_id: block.block_id,
      base_version: state.spec.version,
      op: 'set_layout',
      layout,
    });
  }
  const metric = metricFromAsk(ask);
  if (metric) {
    return parsePatchBlock({
      block_id: block.block_id,
      base_version: state.spec.version,
      op: 'set_metric_ref',
      metric_ref: metric,
    });
  }
  const kind = kindFromAsk(ask);
  const patch = kind
    ? { block_id: block.block_id, base_version: state.spec.version, op: 'set_kind', kind }
    : { block_id: block.block_id, base_version: state.spec.version, op: 'set_title', title: titleFromAsk(ask) };
  return parsePatchBlock(patch);
}

export function kindFromAsk(ask) {
  const text = String(ask || '');
  if (!/加一块|换成|改成/.test(text)) return null;
  for (const kind of BOARD_SPEC_KINDS) {
    if (kind === 'LINK') continue;
    if (text.includes(kind)) return kind;
  }
  if (/折线/.test(text)) return 'LINE';
  if (/柱/.test(text)) return 'BAR';
  if (/表/.test(text)) return 'TABLE';
  return null;
}

export function proposeAskLocal(state) {
  if (!state?.selected_block_id) return fail('CANVAS_NO_SELECTION', '先点选一块');
  const ask = typeof state.ask === 'string' ? state.ask.trim() : '';
  if (!ask) return fail('PATCH_TITLE', 'set_title 需要 title');
  const parsed = patchForAsk(state, ask);
  if (!parsed.ok) return parsed;
  return { ok: true, value: { ...state, pending_patch: parsed.value } };
}

export async function proposeAsk(state, transport) {
  if (!state?.selected_block_id) return fail('CANVAS_NO_SELECTION', '先点选一块');
  const ask = typeof state.ask === 'string' ? state.ask.trim() : '';
  if (!ask) return fail('PATCH_TITLE', 'set_title 需要 title');
  if (isFactsQuestion(ask) && transport?.fetchImpl && transport.resultsPath) {
    try {
      const res = await transport.fetchImpl(transport.resultsPath);
      if (!res || !res.ok) return fail('ASK_FACTS', '当前块没有可刷新的绑定结果，未写入。');
      const body = await res.json();
      const items = Array.isArray(body.items) ? body.items : [];
      return refreshSelectedFacts(state, items);
    } catch {
      return fail('ASK_FACTS', '当前块没有可刷新的绑定结果，未写入。');
    }
  }
  if (!transport || typeof transport.fetchImpl !== 'function') return proposeAskLocal(state);
  try {
    const block = selectedBlock(state);
    const res = await transport.fetchImpl(transport.path || '/board-spec/ask', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        board_id: state.spec.board_id,
        version: state.spec.version,
        block_id: state.selected_block_id,
        kind: block?.kind ?? null,
        title: block?.title ?? null,
        metric_ref: block?.metric_ref ?? null,
        source_result_id: block?.source_result_id ?? null,
        ask,
      }),
    });
    if (!res || !res.ok) return fail('ASK_HTTP', '问数服务不可用，未写入。');
    const body = await res.json();
    const parsed = parsePatchBlock(body.patch ?? body);
    if (!parsed.ok) return fail('ASK_PATCH', '问数返回非法 PATCH，未写入。');
    if (parsed.value.block_id !== state.selected_block_id) {
      return fail('ASK_BLOCK', '问数只能改当前选中块，未写入。');
    }
    if (parsed.value.base_version !== state.spec.version) {
      return fail('PATCH_VERSION_CONFLICT', '问数 PATCH 版本冲突，未写入。');
    }
    return { ok: true, value: { ...state, pending_patch: parsed.value } };
  } catch {
    return fail('ASK_HTTP', '问数服务不可用，未写入。');
  }
}
