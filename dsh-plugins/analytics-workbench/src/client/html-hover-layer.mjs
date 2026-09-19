/** Shine-node hover highlight for the HTML canvas. Phase 1: visual only, no click. */

export const HOVER_STYLE_ID = 'cockpit-hover-style';
export const HOVER_CLASS = 'shine-node-hover';
export const FALLBACK_SELECTOR = 'h1,h2,h3,p,section,article,li,blockquote,figcaption';
const HOVER_RULE = [
  '  border: 2px solid #e8e8e8 !important;',
  '  background: rgba(247, 247, 247, 0.5) !important;',
  '  border-radius: 4px !important;',
  '  outline: none !important;',
  '  box-shadow: 0 0 0 1px rgba(23, 23, 23, 0.05) !important;',
  '  transition: border-color 150ms ease-out, background 150ms ease-out, box-shadow 150ms ease-out !important;',
].join('\n');

export const HOVER_STYLE_TEXT = [
  `[data-shine-node]:hover {`,
  HOVER_RULE,
  '}',
  `.${HOVER_CLASS} {`,
  HOVER_RULE,
  '}',
].join('\n');

export function srcdocHasHoverRuntime(html) {
  return String(html ?? '').includes(HOVER_STYLE_ID);
}

/** Injects hover CSS only. Does not rewrite the page with a script. */
export function htmlWithHoverRuntime(html) {
  const source = String(html ?? '');
  if (!source || srcdocHasHoverRuntime(source)) return source;
  const snippet = `<style id="${HOVER_STYLE_ID}">${HOVER_STYLE_TEXT}</style>`;
  if (/<\/head>/i.test(source)) return source.replace(/<\/head>/i, `${snippet}</head>`);
  if (/<body\b/i.test(source)) return source.replace(/<body([^>]*)>/i, `<body$1>${snippet}`);
  return `${snippet}${source}`;
}

export function resolveIframe(target) {
  if (!target || typeof target !== 'object') return null;
  if (String(target.tagName).toUpperCase() === 'IFRAME') return target;
  return typeof target.querySelector === 'function' ? target.querySelector('iframe') : null;
}

export function readIframeDocument(iframe) {
  if (!iframe) return null;
  try {
    const doc = iframe.contentDocument || iframe.contentWindow?.document || null;
    if (!doc || !doc.documentElement) return null;
    return doc;
  } catch {
    return null;
  }
}

export function injectHoverStyle(doc) {
  if (!doc) return null;
  const head = doc.head || doc.documentElement;
  if (!head) return null;
  let style = doc.getElementById(HOVER_STYLE_ID);
  if (!style) {
    style = doc.createElement('style');
    style.id = HOVER_STYLE_ID;
    style.textContent = HOVER_STYLE_TEXT;
    head.appendChild(style);
  }
  return style;
}

export function shineNodes(doc) {
  if (!doc?.querySelectorAll) return [];
  return [...doc.querySelectorAll('[data-shine-node]')];
}

/** Test helper only. Production hover must not invent shine-node ids. */
export function ensureShineNodes(doc) {
  const marked = shineNodes(doc);
  if (marked.length) return marked;
  const fallback = [...(doc.querySelectorAll(FALLBACK_SELECTOR) ?? [])];
  fallback.forEach((node, index) => {
    if (!node.getAttribute('data-shine-node')) node.setAttribute('data-shine-node', `test-${index + 1}`);
  });
  return shineNodes(doc);
}

export function bindShineNodeHover(doc) {
  if (!doc) return () => {};
  injectHoverStyle(doc);
  const nodes = shineNodes(doc);
  const handleEnter = event => {
    event.currentTarget.classList.add(HOVER_CLASS);
  };
  const handleLeave = event => {
    event.currentTarget.classList.remove(HOVER_CLASS);
  };
  for (const node of nodes) {
    node.addEventListener('mouseenter', handleEnter);
    node.addEventListener('mouseleave', handleLeave);
  }
  return () => {
    for (const node of nodes) {
      node.removeEventListener('mouseenter', handleEnter);
      node.removeEventListener('mouseleave', handleLeave);
      node.classList.remove(HOVER_CLASS);
    }
    doc.getElementById(HOVER_STYLE_ID)?.remove();
  };
}

export function attachHoverToIframe(target) {
  const iframe = resolveIframe(target);
  if (!iframe) return () => {};
  let stop = () => {};
  const attach = () => {
    stop();
    const doc = readIframeDocument(iframe);
    stop = doc ? bindShineNodeHover(doc) : () => {};
  };
  attach();
  const onLoad = () => attach();
  iframe.addEventListener('load', onLoad);
  return () => {
    iframe.removeEventListener('load', onLoad);
    stop();
  };
}
