/** Conserved numeric geometry. No model-supplied SVG, styling or executable code. */
function isPlainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

export function waterfallGeometry(data) {
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const label = value => typeof value === 'string' && value.trim().length > 0 && [...value].length <= 160;
  const value = point => isPlainObject(point) && Object.keys(point).sort().join(',') === 'label,value'
    && label(point.label) && finite(point.value);
  if (!isPlainObject(data) || Object.keys(data).sort().join(',') !== 'contributions,end,start,unit'
    || typeof data.unit !== 'string' || !data.unit.trim() || [...data.unit].length > 24
    || !value(data.start) || !value(data.end) || !Array.isArray(data.contributions)
    || data.contributions.length > 200 || !data.contributions.every(value)
    || new Set(data.contributions.map(item => item.label)).size !== data.contributions.length) return null;
  let running = data.start.value;
  const bars = [{ ...data.start, role: 'total', from: 0, to: running }];
  for (const item of data.contributions) {
    const from = running;
    running += item.value;
    if (!finite(running)) return null;
    bars.push({ ...item, role: 'delta', from, to: running });
  }
  if (Math.abs(running - data.end.value) > Math.max(1e-8, 1e-12 * Math.max(Math.abs(running), Math.abs(data.end.value)))) return null;
  bars.push({ ...data.end, role: 'total', from: 0, to: data.end.value });
  const min = Math.min(0, ...bars.map(item => Math.min(item.from, item.to)));
  const max = Math.max(0, ...bars.map(item => Math.max(item.from, item.to)));
  const magnitude = Math.max(1, Math.abs(min), Math.abs(max));
  const range = max / magnitude - min / magnitude || 1;
  const y = number => 240 - (number / magnitude - min / magnitude) / range * 200;
  return { width: Math.max(400, 80 + bars.length * 96), height: 300, min, max, zero: y(0),
    bars: bars.map((bar, index) => ({ ...bar, x: 64 + index * 96, width: 56,
      top: y(Math.max(bar.from, bar.to)), bottom: y(Math.min(bar.from, bar.to)), carry: y(bar.to) })) };
}
