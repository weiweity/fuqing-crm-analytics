import { parseBoardSpec } from './schema.mjs';

function amount(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return value;
}

function factsFor(block, factsByResultId) {
  const id = block.source_result_id;
  if (!id) return { bind: 'unbound', facts: null };
  const facts = factsByResultId && typeof factsByResultId === 'object'
    ? factsByResultId[id]
    : null;
  if (!facts) return { bind: 'missing_result', facts: null };
  return { bind: 'bound', facts };
}

function series(facts) {
  const current = amount(facts?.current_gsv);
  const comparison = amount(facts?.comparison_gsv);
  if (current === null || comparison === null) return null;
  return [
    { label: '对比期', value: comparison },
    { label: '本期', value: current },
  ];
}

function paint(block, bind, facts) {
  const kind = block.kind;
  if (kind === 'LINK') {
    return {
      kind,
      url: block.url ?? block.href,
      title: block.title ?? '',
      note: typeof block.note === 'string' ? block.note : '',
    };
  }
  if (kind === 'html_sandbox') {
    return {
      kind,
      sandbox: true,
      parent_dom: false,
      model_sql: false,
      note: '沙箱叶子，解释器不执行 HTML/JS',
    };
  }
  if (kind === 'EVIDENCE') {
    const chips = Array.isArray(block.chips) ? block.chips.filter((c) => typeof c === 'string') : [];
    return { kind, chips };
  }
  if (bind !== 'bound' || !facts) {
    return { kind, series: null, headline: null };
  }
  const points = series(facts);
  if (kind === 'METRIC') {
    return { kind, headline: points ? points[1].value : null, series: points };
  }
  if (kind === 'BAR' || kind === 'LINE') {
    return { kind, series: points };
  }
  if (kind === 'TABLE') {
    const rows = points
      ? [
        { label: '本期 GSV', value: points[1].value },
        { label: '对比期 GSV', value: points[0].value },
        { label: '差额', value: amount(facts.difference) },
      ]
      : [];
    return { kind, rows };
  }
  return { kind };
}

/**
 * Read-only view of a BoardSpec. Does not write, query, or execute HTML.
 * @param {unknown} spec
 * @param {Record<string, { current_gsv?: number, comparison_gsv?: number, difference?: number, change_ratio?: number }> | null} [factsByResultId]
 */
export function interpretBoard(spec, factsByResultId = null) {
  const parsed = parseBoardSpec(spec);
  if (!parsed.ok) return parsed;
  const board = parsed.value;
  const blocks = board.blocks.map((block) => {
    const { bind, facts } = factsFor(block, factsByResultId);
    return {
      block_id: block.block_id,
      kind: block.kind,
      title: typeof block.title === 'string' ? block.title : '',
      metric_ref: typeof block.metric_ref === 'string' ? block.metric_ref : null,
      source_result_id: typeof block.source_result_id === 'string' ? block.source_result_id : null,
      bind,
      paint: paint(block, bind, facts),
    };
  });
  return {
    ok: true,
    value: {
      board_id: board.board_id,
      version: board.version,
      blocks,
    },
  };
}
