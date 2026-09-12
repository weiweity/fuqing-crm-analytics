/** html_sandbox leaf: iframe only. No parent DOM, no token, no model SQL. */

export const HTML_SANDBOX = '';

function fail(code, message) {
  return { ok: false, error: { code, message } };
}

function neutralizeWrapperBreakout(html) {
  return String(html)
    .replace(/<\/(?=html|head|body)\b/gi, '&lt;/')
    .replace(/<meta\b/gi, '&lt;meta');
}

export function wrapSandboxHtml(html) {
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: https:; style-src 'unsafe-inline';"></head><body>${neutralizeWrapperBreakout(html)}</body></html>`;
}

export function htmlSandboxFrame(block) {
  if (!block || block.kind !== 'html_sandbox') {
    return fail('SANDBOX_KIND', '不是 html_sandbox');
  }
  const html = typeof block.html === 'string' ? block.html : '';
  if (!html.trim()) return { ok: true, empty: true };
  return {
    ok: true,
    srcdoc: wrapSandboxHtml(html),
    sandbox: HTML_SANDBOX,
    referrerPolicy: 'no-referrer',
  };
}

export function openHttpsLink(url) {
  const got = httpsSandboxFrame(url);
  if (!got.ok) return got;
  return { ok: true, href: got.src, target: '_blank', rel: 'noopener noreferrer' };
}

function isBlockedHost(host) {
  const h = String(host || '').toLowerCase().replace(/\.$/, '').replace(/^\[|\]$/g, '');
  if (!h) return true;
  if (h === 'localhost' || h.endsWith('.localhost') || h.endsWith('.local')) return true;
  if (h === '::1' || h.startsWith('fe80:') || h.startsWith('fc') || h.startsWith('fd')) return true;
  const m = h.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (m) {
    const parts = m.slice(1).map(Number);
    if (parts.some((n) => n > 255)) return true;
    const [a, b] = parts;
    if (a === 0 || a === 10 || a === 127) return true;
    if (a === 169 && b === 254) return true;
    if (a === 192 && b === 168) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 100 && b >= 64 && b <= 127) return true;
  }
  return false;
}

export async function refreshSandboxHtml(url, fetchImpl = fetch) {
  const frame = httpsSandboxFrame(url);
  if (!frame.ok) return frame;
  try {
    const res = await fetchImpl(frame.src, {
      method: 'GET',
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
      redirect: 'manual',
      headers: { accept: 'text/html' },
    });
    if (!res || !res.ok) return fail('SANDBOX_REFRESH', '刷新失败，未改沙箱。');
    if (res.type === 'opaqueredirect' || (res.status >= 300 && res.status < 400)) {
      return fail('SANDBOX_REFRESH', '刷新失败，未改沙箱。');
    }
    const type = String(res.headers.get('content-type') || '');
    if (!/text\/html/i.test(type) && !/text\/plain/i.test(type)) {
      return fail('SANDBOX_REFRESH', '刷新结果不是 HTML，未改沙箱。');
    }
    const html = await res.text();
    if (html.length > 100_000) return fail('SANDBOX_REFRESH', '刷新结果过大，未改沙箱。');
    return {
      ok: true,
      srcdoc: wrapSandboxHtml(html),
      sandbox: HTML_SANDBOX,
      referrerPolicy: 'no-referrer',
    };
  } catch {
    return fail('SANDBOX_REFRESH', '刷新失败，未改沙箱。');
  }
}

export function httpsSandboxFrame(url) {
  if (typeof url !== 'string') return fail('SANDBOX_URL', '需要 https 链接');
  const trimmed = url.trim();
  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    return fail('SANDBOX_URL', '只允许 https 链接');
  }
  if (parsed.protocol !== 'https:') return fail('SANDBOX_URL', '只允许 https 链接');
  if (parsed.username || parsed.password) return fail('SANDBOX_URL', '只允许 https 链接');
  if (isBlockedHost(parsed.hostname)) return fail('SANDBOX_URL', '只允许 https 链接');
  return {
    ok: true,
    src: parsed.href,
    sandbox: '',
    referrerPolicy: 'no-referrer',
  };
}
