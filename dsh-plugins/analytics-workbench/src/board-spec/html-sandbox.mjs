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

export async function refreshSandboxHtml(url, fetchImpl = fetch) {
  const frame = httpsSandboxFrame(url);
  if (!frame.ok) return frame;
  try {
    const res = await fetchImpl(frame.src, {
      method: 'GET',
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
      headers: { accept: 'text/html' },
    });
    if (!res || !res.ok) return fail('SANDBOX_REFRESH', '刷新失败，未改沙箱。');
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
  if (!/^https:\/\//i.test(trimmed)) return fail('SANDBOX_URL', '只允许 https 链接');
  return {
    ok: true,
    src: trimmed,
    sandbox: '',
    referrerPolicy: 'no-referrer',
  };
}
