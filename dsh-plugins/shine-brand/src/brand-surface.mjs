/** Consumer-path brand overlay. Does not edit pinned DSH source. */

export const PRODUCT_NAME = '伸美 AI 增长董事会';
export const PRODUCT_HEADLINE = '探索增长之谜，即刻启程';
export const PRODUCT_GREETING = '先问一个可核验的经营问题';
const UPSTREAM_HEADLINES = new Set(['Into the Unknown', '探索未至之境', '把增长问清楚', PRODUCT_NAME]);

function replaceHeadline(root) {
  const nodes = root.querySelectorAll('h1, h2, [class*="headline"] span, [class*="titleGroup"] span');
  for (const node of nodes) {
    if (node.children && node.children.length) continue;
    const text = (node.textContent || '').trim();
    if (UPSTREAM_HEADLINES.has(text)) node.textContent = PRODUCT_HEADLINE;
  }
}

function hidePreviewBadge(root) {
  const nodes = root.querySelectorAll('[class*="previewBadge"], [class*="preview-badge"]');
  for (const node of nodes) {
    const text = (node.textContent || '').trim();
    if (text === '预览版' || text === 'Preview') {
      node.setAttribute('hidden', '');
      if (node.style) node.style.display = 'none';
    }
  }
}

export function applyCompetitionBrandSurface(doc = globalThis.document) {
  if (!doc || !doc.documentElement) return { title: '', greeting: false };
  doc.title = PRODUCT_NAME;
  const icon = doc.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
  if (icon) icon.setAttribute('href', '/b0/brand/mark.svg');
  else {
    const link = doc.createElement('link');
    link.rel = 'icon';
    link.href = '/b0/brand/mark.svg';
    doc.head?.appendChild(link);
  }
  replaceHeadline(doc);
  hidePreviewBadge(doc);
  return {
    title: doc.title,
    greeting: [...doc.querySelectorAll('h1, h2, span')].some((n) => (n.textContent || '').trim() === PRODUCT_HEADLINE),
  };
}

export function watchCompetitionBrandSurface(doc = globalThis.document) {
  applyCompetitionBrandSurface(doc);
  if (typeof MutationObserver !== 'function' || !doc?.body) return () => {};
  const observer = new MutationObserver(() => applyCompetitionBrandSurface(doc));
  observer.observe(doc.body, { subtree: true, childList: true, characterData: true });
  return () => observer.disconnect();
}
