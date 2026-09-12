/** Bind BoardSpec facts from a GSV result. Copies numbers only; never invents 0%. */

function amount(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return value;
}

export function factsFromGsvResult(result) {
  const facts = result && typeof result === 'object' ? result.facts : null;
  if (!facts || typeof facts !== 'object' || Array.isArray(facts)) {
    return { ok: false, error: { code: 'FACTS_SHAPE', message: '没有可绑定的 GSV 结果' } };
  }
  const current = amount(facts.current && facts.current.gsv);
  const comparison = amount(facts.comparison && facts.comparison.gsv);
  if (current === null || comparison === null) {
    return { ok: false, error: { code: 'FACTS_SHAPE', message: 'GSV 结果不完整，未绑定' } };
  }
  const difference = amount(facts.difference);
  const change = amount(facts.change_ratio);
  const row = {
    current_gsv: current,
    comparison_gsv: comparison,
    difference: difference === null ? current - comparison : difference,
  };
  if (change !== null) row.change_ratio = change;
  return { ok: true, value: { r1: row } };
}

export function catalogFromGsvItems(items) {
  const catalog = {};
  if (!Array.isArray(items)) return catalog;
  let n = 0;
  for (const item of items) {
    const mapped = factsFromGsvResult(item);
    if (!mapped.ok) continue;
    n += 1;
    const raw = item && typeof item === 'object'
      ? (item.result_id || item.source_result_ref || item.id)
      : null;
    const id = typeof raw === 'string' && raw ? raw : `r${n}`;
    catalog[id] = mapped.value.r1;
  }
  return catalog;
}
