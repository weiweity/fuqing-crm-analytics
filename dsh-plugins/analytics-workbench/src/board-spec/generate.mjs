/** GENERATE_BOARD: accept a whole spec or reject the whole board. Does not write facts. */
import { parseBoardSpec } from './schema.mjs';
import { interpretBoard } from './interpret.mjs';

/**
 * @param {unknown} spec
 * @param {object | null} [facts]
 */
export function specFromGsvFacts(facts, meta = {}) {
  const catalog = facts && typeof facts === 'object' && !Array.isArray(facts) ? facts : {};
  const ids = Object.keys(catalog).filter((id) => {
    const row = catalog[id];
    return row && typeof row.current_gsv === 'number' && Number.isFinite(row.current_gsv)
      && typeof row.comparison_gsv === 'number' && Number.isFinite(row.comparison_gsv);
  });
  if (ids.length === 0) {
    return { ok: false, error: { code: 'GENERATE_EMPTY', message: '这场对话没有可绑定的核验结果，未写入。' } };
  }
  const blocks = [];
  ids.forEach((id, index) => {
    const n = index + 1;
    blocks.push({
      block_id: `m${n}`,
      kind: 'METRIC',
      title: '零售 GSV',
      metric_ref: 'retail_gsv',
      query_binding: 'retail_gsv',
      source_result_id: id,
      layout: { x: 0, y: index * 4, w: 6, h: 4 },
    });
    blocks.push({
      block_id: `b${n}`,
      kind: 'BAR',
      title: '两期对比',
      metric_ref: 'retail_gsv',
      query_binding: 'retail_gsv',
      source_result_id: id,
      layout: { x: 6, y: index * 4, w: 6, h: 4 },
    });
  });
  blocks.push({
    block_id: 'h1',
    kind: 'html_sandbox',
    title: '渠道结构',
    source_result_id: ids[0],
    layout: { x: 0, y: ids.length * 4, w: 12, h: 4 },
  });
  const spec = {
    board_id: meta.board_id || `board_retail_gsv_${ids[0]}`,
    version: 1,
    blocks,
  };
  if (typeof meta.session_id === 'string' && meta.session_id) spec.session_id = meta.session_id;
  return parseBoardSpec(spec);
}

export function generateBoard(spec, facts = null) {
  const parsed = parseBoardSpec(spec);
  if (!parsed.ok) return parsed;
  const view = interpretBoard(parsed.value, facts);
  if (!view.ok) return view;
  return { ok: true, value: { spec: parsed.value, facts } };
}

/**
 * @param {{ boardSpec?: object | null, boardFacts?: object | null, boardError?: string }} draft
 * @param {unknown} spec
 * @param {object | null} [facts]
 */
export function summarizeGenerate(spec) {
  const parsed = parseBoardSpec(spec);
  if (!parsed.ok) return parsed.error.message;
  const blocks = Array.isArray(parsed.value.blocks) ? parsed.value.blocks : [];
  const parts = blocks.map((block) => `${block.kind} ${block.title || block.block_id}`).slice(0, 3);
  return `即将写入 ${blocks.length} 个块：${parts.join('、')}。数字来自已核验结果。确认后进入画布。`;
}

const EMPTY_BOARD = Object.freeze({ board_id: 'board_retail_gsv_2026_08', version: 1, blocks: Object.freeze([]) });

export function specWithLink(spec, link) {
  if (!link || link.kind !== 'LINK') {
    return { ok: false, error: { code: 'SPEC_LINK', message: '需要 LINK 块' } };
  }
  const parsed = spec ? parseBoardSpec(spec) : parseBoardSpec(EMPTY_BOARD);
  const board = parsed.ok ? parsed.value : EMPTY_BOARD;
  if (spec && !parsed.ok) return parsed;
  const blocks = Array.isArray(board.blocks) ? [...board.blocks] : [];
  const exists = blocks.some((block) => block.kind === 'LINK' && (block.block_id === link.block_id || block.url === link.url));
  if (!exists) blocks.push(link);
  return parseBoardSpec({
    board_id: board.board_id || EMPTY_BOARD.board_id,
    version: board.version || 1,
    blocks,
  });
}

export function applyGenerate(draft, spec, facts = null) {
  const got = generateBoard(spec, facts);
  if (!got.ok) {
    draft.boardError = got.error.message;
    return got;
  }
  draft.boardError = '';
  draft.boardSpec = got.value.spec;
  draft.boardFacts = got.value.facts;
  return got;
}
