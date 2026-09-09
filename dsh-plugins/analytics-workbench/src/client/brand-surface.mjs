/** Consumer-path brand overlay. Does not edit pinned DSH source. */

export const PRODUCT_NAME = '伸美 AI 增长董事会';
export const PRODUCT_GREETING = '先问一个可核验的经营问题';
const UPSTREAM_HEADLINES = new Set(['Into the Unknown', '探索未至之境']);

function replaceHeadline(root) {
  const nodes = root.querySelectorAll('h1, h2, [class*="headline"], [data-testid*="headline"]');
  for (const node of nodes) {
    const text = (node.textContent || '').trim();
    if (UPSTREAM_HEADLINES.has(text)) node.textContent = PRODUCT_GREETING;
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
  return { title: doc.title, greeting: [...doc.querySelectorAll('h1, h2')].some(n => n.textContent === PRODUCT_GREETING) };
}

export function watchCompetitionBrandSurface(doc = globalThis.document) {
  applyCompetitionBrandSurface(doc);
  if (typeof MutationObserver !== 'function' || !doc?.body) return () => {};
  const observer = new MutationObserver(() => applyCompetitionBrandSurface(doc));
  observer.observe(doc.body, { subtree: true, childList: true, characterData: true });
  return () => observer.disconnect();
}
