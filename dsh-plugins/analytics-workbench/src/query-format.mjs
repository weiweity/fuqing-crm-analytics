/** Pure display helpers. Raw 0–1 ratios and integer fen are not rescaled until here. */

export function formatRatioPercent(ratio) {
  if (ratio === null) return '—';
  if (typeof ratio !== 'number' || !Number.isFinite(ratio) || ratio < 0 || ratio > 1) return null;
  const percent = ratio * 100;
  return `${Number.isInteger(percent) ? String(percent) : percent.toFixed(1)}%`;
}

export function formatFenYuan(minor) {
  if (minor === null) return '—';
  if (typeof minor !== 'number' || !Number.isInteger(minor) || minor < 0) return null;
  return `${(minor / 100).toFixed(2)} 元`;
}

export function formatEmptyReason(reason) {
  if (reason === null) return { text: '', code: null };
  if (reason === 'EMPTY_MATURE_COHORT') {
    return { text: '空成熟队列（观察窗口内没有可计成熟首单）', code: 'EMPTY_MATURE_COHORT' };
  }
  return null;
}
