/** Convert a workspace HTML file into a page-documents candidate. Does not confirm, write workspace files, or invent shine nodes. */

import { extractCandidateUrls } from '../../free-page/resource/network-policy.mjs';
import { normalizePagePackage } from '../../free-page/resource/package-normalize.mjs';
import { bytesToBase64, utf8Bytes } from '../../free-page/resource/bytes.mjs';
import { workspaceRelFromEventPath } from '../cockpit-products.mjs';

export const DEFAULT_IMPORT_RESOURCE_MAX = 16;
export const DEFAULT_IMPORT_RESOURCE_BYTES = 256 * 1024;

function fail(code, message, extra = {}) {
  return { ok: false, error: { code, message, ...extra } };
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function dirnameOf(path) {
  const index = String(path).lastIndexOf('/');
  return index <= 0 ? '' : path.slice(0, index);
}

export function resolveImportResourcePath(fromPath, href) {
  const trimmed = String(href ?? '').trim();
  if (!trimmed || trimmed.startsWith('#') || trimmed.includes('://') || trimmed.startsWith('//') || trimmed.startsWith('/')) {
    return null;
  }
  const from = workspaceRelFromEventPath(fromPath);
  if (!from) return null;
  const joined = [...dirnameOf(from).split('/').filter(Boolean), ...trimmed.replace(/\\/g, '/').split('/')];
  const stack = [];
  for (const part of joined) {
    if (!part || part === '.') continue;
    if (part === '..') return null;
    stack.push(part);
  }
  return workspaceRelFromEventPath(stack.join('/'));
}

function mimeFromPath(path) {
  const name = String(path).toLowerCase();
  if (name.endsWith('.png')) return 'image/png';
  if (name.endsWith('.jpg') || name.endsWith('.jpeg')) return 'image/jpeg';
  if (name.endsWith('.gif')) return 'image/gif';
  if (name.endsWith('.webp')) return 'image/webp';
  if (name.endsWith('.svg')) return 'image/svg+xml';
  if (name.endsWith('.woff2')) return 'font/woff2';
  if (name.endsWith('.woff')) return 'font/woff';
  if (name.endsWith('.css')) return 'text/css';
  if (name.endsWith('.js') || name.endsWith('.mjs')) return 'text/javascript';
  return null;
}

function asBytes(value) {
  if (value instanceof Uint8Array) return value;
  if (typeof value === 'string') return utf8Bytes(value);
  return null;
}

function toDataUrl(mime, bytes) {
  if (!mime?.startsWith('image/') && !mime?.startsWith('font/')) return null;
  return `data:${mime};base64,${bytesToBase64(bytes)}`;
}

function stripTagWithAttr(html, tag, attr, url) {
  const pattern = new RegExp(
    `<${tag}\\b[^>]*${attr}\\s*=\\s*(['"])${escapeRegExp(url)}\\1[^>]*>\\s*(?:</${tag}>)?`,
    'gi',
  );
  return html.replace(pattern, '');
}

const HTML_URL_ATTRS = 'src|href|action|poster|formaction|cite|data-src';

function replaceHtmlAttrUrl(html, url, next) {
  const re = new RegExp(`(\\b(?:${HTML_URL_ATTRS})\\s*=\\s*)(['"])${escapeRegExp(url)}\\2`, 'gi');
  return html.replace(re, (_, prefix, quote) => `${prefix}${quote}${next}${quote}`);
}

function replaceCssUrl(css, url, next) {
  const re = new RegExp(`url\\(\\s*(['"]?)${escapeRegExp(url)}\\1\\s*\\)`, 'gi');
  return css.replace(re, () => `url("${next}")`);
}

function rewriteStyleTags(html, rewriteCss) {
  return html.replace(/<style\b([^>]*)>([\s\S]*?)<\/style>/gi, (_, attrs, body) => (
    `<style${attrs}>${rewriteCss(body)}</style>`
  ));
}

function inlineStyleText(html) {
  return [...String(html).matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map(match => match[1]).join('\n');
}

function stripCssImport(css, url) {
  const escaped = escapeRegExp(url);
  return String(css)
    .replace(new RegExp(`@import\\s+url\\(\\s*(['"]?)${escaped}\\1\\s*\\)\\s*;?`, 'gi'), '')
    .replace(new RegExp(`@import\\s+(['"])${escaped}\\1\\s*;?`, 'gi'), '');
}

function collectSourceUrls(html, css) {
  const urls = [];
  const seen = new Set();
  for (const url of [...extractCandidateUrls(html, '', ''), ...extractCandidateUrls('', css ?? '', '')]) {
    const trimmed = String(url || '').trim();
    if (!trimmed || seen.has(trimmed)) continue;
    seen.add(trimmed);
    urls.push(trimmed);
  }
  return urls;
}

function scriptAttributes(source) {
  const attrs = new Map();
  for (const match of source.matchAll(/([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) {
    attrs.set(match[1].toLowerCase(), match[2] ?? match[3] ?? match[4] ?? '');
  }
  return attrs;
}

function toHttpPackage(normalized) {
  return {
    html: normalized.html,
    css: normalized.css,
    js: normalized.js,
    resources: [],
    node_map: Array.isArray(normalized.node_map)
      ? normalized.node_map.map(row => ({ node_id: row.node_id, kind: row.kind, selector: row.selector }))
      : [],
  };
}

export async function convertWorkspaceHtml({
  html, path, sessionId, readResource,
  maxResources = DEFAULT_IMPORT_RESOURCE_MAX,
  maxResourceBytes = DEFAULT_IMPORT_RESOURCE_BYTES,
} = {}) {
  if (!sessionId) return fail('NO_SESSION', '导入需要明确 session_id');
  if (!workspaceRelFromEventPath(path)) return fail('UNSAFE_PATH', '来源路径必须是工作区相对路径');
  if (typeof html !== 'string' || !html.trim()) return fail('EMPTY_HTML', 'HTML 正文为空');
  let rewritten = html;
  const extraCss = [];
  const missing = [];
  const unsupported = [];
  const loaded = new Map();
  const htmlRewrites = new Map();
  const cssRewrites = new Map();
  // Normalization combines classic scripts. Module/async/defer execution cannot
  // be represented by that package contract, so never silently change it.
  for (const match of html.matchAll(/<script\b([^>]*)>[\s\S]*?<\/script\s*>/gi)) {
    const attrs = scriptAttributes(match[1]);
    if (['async', 'defer', 'nomodule'].some(key => attrs.has(key))
      || (attrs.has('type') && !['', 'text/javascript', 'application/javascript'].includes(attrs.get('type').toLowerCase()))) {
      return fail('RESOURCE_UNSUPPORTED', '脚本执行方式无法保真入库，请保留原文件预览', {
        unsupported: [{ url: attrs.get('src') ?? null, reason: 'script-execution-mode' }],
      });
    }
  }
  const queue = collectSourceUrls(html, inlineStyleText(html)).map(url => ({ url, basePath: path, from: 'html' }));

  const rememberCssRewrite = (basePath, url, next) => {
    if (!cssRewrites.has(basePath)) cssRewrites.set(basePath, new Map());
    cssRewrites.get(basePath).set(url, next);
  };

  while (queue.length) {
    const { url: trimmed, basePath, from } = queue.shift();
    if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('data:') || trimmed.startsWith('blob:')
      || trimmed.startsWith('resource:') || trimmed.startsWith('about:')) continue;
    if (/^(https?:|wss?:)/i.test(trimmed) || trimmed.startsWith('//')) {
      unsupported.push({ url: trimmed, reason: 'network-forbidden' });
      continue;
    }
    const rel = resolveImportResourcePath(basePath, trimmed);
    if (!rel) {
      unsupported.push({ url: trimmed, reason: 'unsafe-path' });
      continue;
    }
    if (!loaded.has(rel) && loaded.size >= maxResources) {
      unsupported.push({ path: rel, reason: 'resource-count' });
      continue;
    }
    if (!loaded.has(rel)) {
      if (typeof readResource !== 'function') {
        missing.push({ path: rel, reason: 'unread' });
        loaded.set(rel, { status: 'missing' });
        continue;
      }
      let got;
      try { got = await readResource(rel); } catch { got = null; }
      const bytes = asBytes(got?.bytes ?? got?.text);
      if (!bytes) {
        missing.push({ path: rel, reason: 'missing' });
        loaded.set(rel, { status: 'missing' });
        continue;
      }
      if (bytes.byteLength > maxResourceBytes) {
        unsupported.push({ path: rel, reason: 'too-large', byte_length: bytes.byteLength });
        loaded.set(rel, { status: 'unsupported' });
        continue;
      }
      const mime = got?.content_type || mimeFromPath(rel);
      if (mime === 'text/css') {
        const text = new TextDecoder().decode(bytes);
        loaded.set(rel, { status: 'css', text });
        for (const nested of collectSourceUrls('', text)) queue.push({ url: nested, basePath: rel, from: 'css' });
      } else if (mime === 'text/javascript') {
        loaded.set(rel, { status: 'js', text: new TextDecoder().decode(bytes) });
      } else {
        const dataUrl = toDataUrl(mime, bytes);
        if (!dataUrl) {
          unsupported.push({ path: rel, reason: 'unsupported-type' });
          loaded.set(rel, { status: 'unsupported' });
          continue;
        }
        loaded.set(rel, { status: 'data', dataUrl });
      }
    }
    const item = loaded.get(rel);
    if (!item || item.status === 'missing' || item.status === 'unsupported') continue;
    if (item.status === 'css') {
      if (from === 'html') rewritten = stripTagWithAttr(rewritten, 'link', 'href', trimmed);
      if (from === 'css') {
        const parent = loaded.get(basePath);
        if (parent?.status === 'css' && typeof parent.text === 'string') {
          parent.text = stripCssImport(parent.text, trimmed);
        }
      }
      continue;
    }
    if (item.status === 'js') {
      // Replace at each original tag, including repeated references. Appending
      // external code to package.js would run it before preceding inline setup.
      if (/<\/script[\s>]/i.test(item.text)) {
        unsupported.push({ path: rel, reason: 'script-closing-tag' });
        continue;
      }
      if (from === 'html') rewritten = rewritten.replace(/<script\b([^>]*)>[\s\S]*?<\/script\s*>/gi, (tag, attrs) => (
        scriptAttributes(attrs).get('src') === trimmed ? `<script>\n;${item.text}\n;</script>` : tag
      ));
      continue;
    }
    if (from === 'html') htmlRewrites.set(trimmed, item.dataUrl);
    rememberCssRewrite(basePath, trimmed, item.dataUrl);
  }
  for (const [url, next] of htmlRewrites) rewritten = replaceHtmlAttrUrl(rewritten, url, next);
  rewritten = rewriteStyleTags(rewritten, (body) => {
    let css = body;
    for (const [url, next] of cssRewrites.get(path) ?? []) css = replaceCssUrl(css, url, next);
    return css;
  });
  for (const [rel, item] of loaded) {
    if (item.status !== 'css' || typeof item.text !== 'string') continue;
    let css = item.text;
    for (const [url, next] of cssRewrites.get(rel) ?? []) css = replaceCssUrl(css, url, next);
    extraCss.push(css);
  }
  if (missing.length) {
    return fail('RESOURCE_MISSING', '相对资源缺失，未联网抓取', { missing, unsupported });
  }
  if (unsupported.length) {
    return fail('RESOURCE_UNSUPPORTED', '存在禁止或无法入库的资源', { missing, unsupported });
  }
  const normalized = await normalizePagePackage({
    html: rewritten,
    css: extraCss.join('\n'),
    js: '',
    resources: [],
    node_map: [],
  });
  if (!normalized.ok) {
    return { ok: false, error: normalized.error, missing, unsupported };
  }
  return {
    ok: true,
    package: toHttpPackage(normalized.value),
    origin: { session_id: sessionId, path },
    binding_manifest: { bindings: [], result_refs: [] },
    binding_state: 'UNBOUND_SAMPLE',
    missing,
    unsupported,
  };
}

function unwrapSpec(body) {
  if (body?.spec?.page_id) return body.spec;
  if (body?.snapshot?.spec?.page_id) return body.snapshot.spec;
  if (body?.page_id) return body;
  return null;
}

function httpError(error) {
  const code = error?.code || 'PAGE_HTTP';
  const status = error?.status;
  return {
    ok: false,
    error: {
      code,
      message: error?.message || '页库请求失败',
      status,
      recoverable: status == null || status >= 500 || code === 'http_not_configured',
    },
  };
}

export function createHtmlImporter({ documents } = {}) {
  if (!documents?.generatePreview || !documents?.confirmPreview || !documents?.cancelPreview) {
    throw new Error('html importer requires documents generatePreview/confirmPreview/cancelPreview');
  }
  return {
    convert: convertWorkspaceHtml,
    async createCandidate(input) {
      const converted = await convertWorkspaceHtml(input);
      if (!converted.ok) return converted;
      const title = input.title || String(input.path).split('/').pop();
      try {
        const made = await documents.generatePreview({
          title,
          session_id: input.sessionId,
          package: converted.package,
          binding_manifest: converted.binding_manifest,
          origin_path: input.path,
        });
        if (!made.ok) return fail(made.reason || 'http_not_configured', '无法创建入库候选');
        const spec = unwrapSpec(made.body);
        return {
          ok: true,
          preview_id: made.body.preview_id,
          status: made.body.status || 'PENDING',
          origin: converted.origin,
          package: converted.package,
          binding_state: spec?.binding_state || 'UNBOUND_SAMPLE',
          snapshot: made.body.snapshot ?? null,
          missing: converted.missing,
          unsupported: converted.unsupported,
        };
      } catch (error) {
        return httpError(error);
      }
    },
    async confirm(previewId, idempotencyKey) {
      if (!previewId) return fail('NOT_FOUND', '缺少 preview_id');
      if (!idempotencyKey) return fail('IDEMPOTENCY_KEY_REQUIRED', '确认需要稳定 Idempotency-Key');
      try {
        const got = await documents.confirmPreview(previewId, idempotencyKey);
        if (!got.ok) return fail(got.reason || 'http_not_configured', '无法确认入库');
        const spec = unwrapSpec(got.body);
        if (!spec?.page_id) return fail('UNKNOWN_RECEIPT', '确认回执缺少 page_id，可用同一幂等键重试', { recoverable: true });
        return {
          ok: true,
          page_id: spec.page_id,
          version: spec.version,
          session_id: spec.session_id,
          origin_path: spec.origin_path || null,
          binding_state: spec.binding_state,
          spec,
        };
      } catch (error) {
        return httpError(error);
      }
    },
    async cancel(previewId) {
      if (!previewId) return fail('NOT_FOUND', '缺少 preview_id');
      try {
        const got = await documents.cancelPreview(previewId);
        if (!got.ok) return fail(got.reason || 'http_not_configured', '无法取消候选');
        if (got.body?.status !== 'CANCELLED' || got.body?.preview_id !== previewId) return fail('UNKNOWN_RECEIPT', '取消回执不匹配，保留当前候选');
        return { ok: true, preview_id: previewId, status: 'CANCELLED' };
      } catch (error) {
        return httpError(error);
      }
    },
    async reopen(pageId) {
      if (typeof documents.pullPage !== 'function') return fail('NOT_FOUND', '没有 pullPage');
      try {
        const got = await documents.pullPage(pageId);
        if (!got.ok) return fail(got.reason || 'NOT_FOUND', '重开失败');
        return { ok: true, page_id: got.page_id };
      } catch (error) {
        return httpError(error);
      }
    },
  };
}
