import { fail } from './frozen-contract.mjs';

const ATTR = /\b(?:src|href|action|poster|formaction|cite|data-src)\s*=\s*(['"])(.*?)\1/gi;
const PING = /\bping\s*=\s*(['"])(.*?)\1/gi;
const CSS_URL = /url\(\s*(['"]?)(.*?)\1\s*\)/gi;
const CSS_IMPORT = /@import\s+(?:url\(\s*)?(['"]?)(.*?)\1/gi;
const JS_HTTP = /\b(?:fetch|open|importScripts|import)\s*\(\s*(['"`])((?:https?:|wss?:|ws:)[^'"`]+)\1/gi;
const JS_CTOR = /\bnew\s+(?:WebSocket|EventSource|Worker|SharedWorker)\s*\(\s*(['"`])([^'"`]+)\1/gi;
const BEACON = /\bsendBeacon\s*\(\s*(['"`])([^'"`]+)\1/gi;
const ASSIGN = /\b(?:location|window)\.(?:href|location)\s*=\s*(['"`])([^'"`]+)\1/gi;

const ALLOWED_SCHEMES = new Set(['blob:', 'data:', 'resource:']);

export function isBlockedNetworkUrl(raw) {
  const value = String(raw || '').trim();
  if (!value || value.startsWith('#') || value.startsWith('about:')) return false;
  if (value.startsWith('resource:')) return false;
  if (value.startsWith('data:image/')) return false;
  if (value.startsWith('data:font/')) return false;
  if (value.startsWith('blob:')) return false;
  const lower = value.toLowerCase();
  if (lower.startsWith('javascript:') || lower.startsWith('vbscript:')) return true;
  if (lower.startsWith('data:')) return true;
  if (lower.startsWith('http:') || lower.startsWith('https:') || lower.startsWith('ws:') || lower.startsWith('wss:')) {
    return true;
  }
  if (lower.startsWith('//') || lower.startsWith('/') || lower.startsWith('./') || lower.startsWith('../')) return true;
  try {
    const parsed = new URL(value);
    if (!ALLOWED_SCHEMES.has(parsed.protocol) && parsed.protocol !== 'about:') return true;
  } catch {
    return true;
  }
  return false;
}

function collect(source, regex) {
  const found = [];
  if (typeof source !== 'string' || !source) return found;
  regex.lastIndex = 0;
  let match;
  while ((match = regex.exec(source))) {
    found.push(match[2] ?? match[1]);
    if (regex.lastIndex === match.index) regex.lastIndex += 1;
  }
  return found;
}

export function extractCandidateUrls(html = '', css = '', js = '') {
  const urls = [];
  for (const value of collect(html, ATTR)) urls.push(value);
  for (const value of collect(html, PING)) {
    for (const part of String(value).split(/\s+/)) if (part) urls.push(part);
  }
  for (const value of collect(css, CSS_URL)) urls.push(value);
  for (const value of collect(css, CSS_IMPORT)) urls.push(value);
  for (const value of collect(js, JS_HTTP)) urls.push(value);
  for (const value of collect(js, JS_CTOR)) urls.push(value);
  for (const value of collect(js, BEACON)) urls.push(value);
  for (const value of collect(js, ASSIGN)) urls.push(value);
  return urls;
}

export function assertNoActiveOutbound(html, css, js, allowedResourceIds = new Set()) {
  const blocked = [];
  for (const url of extractCandidateUrls(html, css, js)) {
    const trimmed = String(url || '').trim();
    if (trimmed.startsWith('resource:')) {
      const id = trimmed.slice('resource:'.length);
      if (!allowedResourceIds.has(id)) blocked.push(trimmed);
      continue;
    }
    if (isBlockedNetworkUrl(trimmed)) blocked.push(trimmed);
  }
  if (blocked.length) {
    return fail('INVALID_PAGE', '页面默认禁止主动外联；外部资源必须进入显式清单由宿主加载。', {
      urls: blocked.slice(0, 20),
    });
  }
  return { ok: true };
}
