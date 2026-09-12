/** Open-canvas refresh: rebind facts by source_result_id. Never invent numbers. */
import { parseBoardSpec } from './schema.mjs';

const FACT_KEYS = Object.freeze(['current_gsv', 'comparison_gsv', 'difference', 'change_ratio']);

function fail(code, message) {
  return { ok: false, error: { code, message } };
}

function pickAmounts(row) {
  if (!row || typeof row !== 'object' || Array.isArray(row)) return null;
  const out = {};
  for (const key of FACT_KEYS) {
    const value = row[key];
    if (typeof value === 'number' && Number.isFinite(value)) out[key] = value;
  }
  return Object.keys(out).length ? out : null;
}

export function refreshFacts(spec, catalog) {
  const parsed = parseBoardSpec(spec);
  if (!parsed.ok) return parsed;
  const ids = [...new Set(parsed.value.blocks.map((block) => block.source_result_id).filter(Boolean))];
  const next = {};
  const book = catalog && typeof catalog === 'object' && !Array.isArray(catalog) ? catalog : {};
  for (const id of ids) {
    const picked = pickAmounts(book[id]);
    if (picked) next[id] = picked;
  }
  return { ok: true, value: next };
}

export async function refreshFactsFromTransport(spec, transport) {
  if (!transport || typeof transport.fetchImpl !== 'function') {
    return refreshFacts(spec, transport?.catalog ?? null);
  }
  const parsed = parseBoardSpec(spec);
  if (!parsed.ok) return parsed;
  const ids = [...new Set(parsed.value.blocks.map((block) => block.source_result_id).filter(Boolean))];
  try {
    const res = await transport.fetchImpl(transport.path || '/board-spec/facts', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ board_id: parsed.value.board_id, ids }),
    });
    if (!res || !res.ok) return fail('FACTS_HTTP', '刷新失败，未改数字。');
    const body = await res.json();
    return refreshFacts(spec, body.facts ?? body);
  } catch {
    return fail('FACTS_HTTP', '刷新失败，未改数字。');
  }
}
