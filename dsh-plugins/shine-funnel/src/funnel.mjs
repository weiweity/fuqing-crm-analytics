/** Nested customer counts only. Geometry encodes count by width, never by area. */
function isPlainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

const exact = (value, keys) => isPlainObject(value) && Object.keys(value).length === keys.length
  && keys.every(key => Object.hasOwn(value, key));
const label = (value, limit) => typeof value === 'string' && !!value.trim() && [...value].length <= limit;

export function funnelGeometry(data) {
  if (!exact(data, ['unit', 'cohort_label', 'counting_rule', 'stages']) || data.unit !== '人'
    || !label(data.cohort_label, 240) || !label(data.counting_rule, 1000)
    || !Array.isArray(data.stages) || data.stages.length < 2 || data.stages.length > 12) return null;
  const names = new Set();
  for (const [index, stage] of data.stages.entries()) {
    if (!exact(stage, ['label', 'count']) || !label(stage.label, 160) || names.has(stage.label)
      || !Number.isSafeInteger(stage.count) || stage.count < 0
      || (index > 0 && stage.count > data.stages[index - 1].count)) return null;
    names.add(stage.label);
  }
  const base = data.stages[0].count;
  return { empty: base === 0, stages: data.stages.map((stage, index) => {
    const previous = index === 0 ? null : data.stages[index - 1].count;
    return { ...stage, width: base === 0 ? 0 : stage.count / base * 100,
      first_ratio: base === 0 ? null : stage.count / base,
      previous_ratio: previous === null || previous === 0 ? null : stage.count / previous };
  }) };
}
