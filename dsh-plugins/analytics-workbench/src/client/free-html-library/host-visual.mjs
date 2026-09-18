/** T16/T17/T19 host visual helpers. Readings are computed from tokens/layout, not assumed. */

const BINDING_STATES = new Set(['UNBOUND_SAMPLE', 'BOUND_VERIFIED', 'BOUND_STALE']);

export function relativeLuminance(hex) {
  const n = hex.replace('#', '');
  const v = n.length === 3 ? n.split('').map(c => c + c).join('') : n;
  const rgb = [0, 2, 4].map(i => parseInt(v.slice(i, i + 2), 16) / 255).map(channel => (
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ));
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
}

export function contrastRatio(foreground, background) {
  const l1 = relativeLuminance(foreground);
  const l2 = relativeLuminance(background);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

export function contrastReport(schemeTokens) {
  const bg = schemeTokens.color.background;
  const rows = [
    { role: 'body-ink', fg: schemeTokens.color.ink, bg, min: 4.5 },
    { role: 'body-lilac', fg: schemeTokens.color.brandSecondary, bg, min: 4.5 },
    { role: 'large-purple', fg: schemeTokens.color.brandPrimary, bg, min: 3, bodyForbidden: true },
    { role: 'signal-nontext', fg: schemeTokens.color.brandAccent, bg, min: 3 },
    { role: 'danger', fg: schemeTokens.color.danger, bg, min: 3 },
  ].map(row => {
    const ratio = contrastRatio(row.fg, row.bg);
    return { ...row, ratio: Number(ratio.toFixed(2)), pass: ratio + 1e-6 >= row.min };
  });
  return { background: bg, rows };
}

export function widthBand(viewportWidth) {
  if (viewportWidth <= 375) return 'phone-375';
  if (viewportWidth <= 768) return 'tablet-768';
  if (viewportWidth <= 1280) return 'desktop-1280';
  return 'desktop-1440';
}

export function defaultRailCollapsed(viewportWidth) {
  return viewportWidth <= 1280;
}

export function panelPresentation(viewportWidth) {
  if (viewportWidth <= 375) return 'fullscreen';
  if (viewportWidth <= 768) return 'overlay';
  return 'side';
}

export function estimateIframeContentWidth({
  viewportWidth, railOpen, panelOpen, zoom = 1, padding = 40, rail = 220, panel = 360,
} = {}) {
  const band = widthBand(viewportWidth);
  let chrome = padding;
  if (band === 'desktop-1440' && railOpen) chrome += rail;
  if ((band === 'desktop-1440' || band === 'desktop-1280') && panelOpen) chrome += panel;
  return {
    viewportWidth,
    band,
    orientation: viewportWidth >= 768 && viewportWidth <= 1024 ? 'either' : 'portrait-default',
    zoom,
    railOpen: Boolean(railOpen),
    panelOpen: Boolean(panelOpen),
    iframeContentWidth: Math.max(0, Math.floor((viewportWidth - chrome) / zoom)),
    hostOverflow: 'page tables/canvas scroll locally; host chrome must not force horizontal overflow',
  };
}

export const WIDTH_MATRIX = Object.freeze([
  { viewportWidth: 375, orientation: 'portrait', zoom: 1, railOpen: false, panelOpen: false },
  { viewportWidth: 375, orientation: 'landscape', zoom: 1, railOpen: false, panelOpen: true },
  { viewportWidth: 768, orientation: 'portrait', zoom: 1, railOpen: false, panelOpen: false },
  { viewportWidth: 768, orientation: 'landscape', zoom: 1, railOpen: false, panelOpen: true },
  { viewportWidth: 1024, orientation: 'landscape', zoom: 1, railOpen: false, panelOpen: true },
  { viewportWidth: 1280, orientation: 'landscape', zoom: 1, railOpen: false, panelOpen: true },
  { viewportWidth: 1440, orientation: 'landscape', zoom: 1, railOpen: true, panelOpen: false },
  { viewportWidth: 1440, orientation: 'landscape', zoom: 1, railOpen: true, panelOpen: true },
  { viewportWidth: 1440, orientation: 'landscape', zoom: 2, railOpen: false, panelOpen: false },
].map(row => ({ ...row, ...estimateIframeContentWidth(row), presentation: panelPresentation(row.viewportWidth) })));

export const HOST_VERDICTS = Object.freeze(['HOST_PASS', 'PAGE_LIMITATION', 'PAGE_REPAIRED_PENDING_RETEST', 'PAGE_PASS']);

export function inspectPage({ host, page } = {}) {
  const hostGaps = [];
  if (!host?.landmarks) hostGaps.push('缺少 landmark');
  if (!host?.nativeChat) hostGaps.push('原生聊天入口不可达');
  if (!host?.statusSpineVisible) hostGaps.push('状态脊不可见');
  if (!host?.keyboard) hostGaps.push('宿主键盘路径不完整');
  const pageGaps = [];
  if (!page?.focusableActions) pageGaps.push('主要动作不可聚焦');
  if (!page?.textStatus) pageGaps.push('状态缺少文字');
  if (!page?.chartAlternative) pageGaps.push('图表缺少摘要或数据表');
  if (page?.hostOverflow) pageGaps.push('页面造成宿主横溢');
  if (page?.canvasUnknown) pageGaps.push('Canvas 交互需人工确认');
  const hostVerdict = hostGaps.length === 0 ? 'HOST_PASS' : 'HOST_INCOMPLETE';
  let pageVerdict = 'PAGE_PASS';
  if (pageGaps.length) pageVerdict = page?.repaired ? 'PAGE_REPAIRED_PENDING_RETEST' : 'PAGE_LIMITATION';
  return {
    hostVerdict,
    pageVerdict,
    hostGaps,
    pageGaps,
    blocksGenerate: false,
    silentRewrite: false,
    notes: hostVerdict === 'HOST_PASS' && pageVerdict === 'PAGE_PASS' ? '宿主闭环与页面地板均满足' : '缺陷可见，交给 AI 修订；不阻断生成、不静默改源码',
  };
}

export function bindingLabel(state, { partial = false } = {}) {
  if (!BINDING_STATES.has(state)) return '未知绑定状态';
  if (state === 'UNBOUND_SAMPLE') return '示例数据 · 未绑定经营数据';
  if (state === 'BOUND_STALE') return '数据已过期';
  if (partial) return '部分已绑定';
  return '已绑定经营数据';
}
