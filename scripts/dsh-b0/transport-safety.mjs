/** Pure helpers for the pinned, synthetic-only B0 transport. No IO or credentials. */
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const stripAnsi = text => text.replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, '');

/** Pass the accumulated log, never an individual stdout chunk. */
export function findReadyUrl(log, origin) {
  if (typeof log !== 'string') return null;
  const complete = stripAnsi(log.slice(0, log.lastIndexOf('\n') + 1));
  for (const candidate of complete.match(/https?:\/\/[^\s<>"']+/g) ?? []) {
    try {
      const url = new URL(candidate);
      const tokens = url.searchParams.getAll('token');
      if (url.origin === origin && !url.username && !url.password && !url.hash
        && tokens.length === 1 && /^[A-Za-z0-9_-]+$/.test(tokens[0])) return url.href;
    } catch { /* Not a complete, trusted launch URL. */ }
  }
  return null;
}

/** Redact a complete/accumulated log before persisting it; do not stream chunks. */
export function redactLaunchLog(log) {
  return stripAnsi(String(log)).replace(/([?&](?:token|b0)=)[^&#\s"'<>]*/gi, '$1[REDACTED]');
}

function bootGraph(bootHtml, origin) {
  if (typeof bootHtml !== 'string' || bootHtml.length > 2 * 1024 * 1024
    || new URL(origin).origin !== origin) throw new Error('Invalid B0 boot input');
  const scripts = [...bootHtml.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)];
  const assignments = scripts.map(([, , body]) => body.match(/^\s*globalThis\["__DSH_BOOT__"\]\s*=\s*(\{[\s\S]*\})\s*;?\s*$/)).filter(Boolean);
  if (assignments.length !== 1) throw new Error('Expected one JSON DSH boot graph');
  const graph = JSON.parse(assignments[0][1]);
  if (!record(graph) || !Array.isArray(graph.entries) || !Array.isArray(graph.batches)) {
    throw new Error('Invalid DSH boot graph');
  }
  return { graph, scripts };
}

/** Exact absolute URLs, including the published batch query/revision; no wildcard. */
export function pluginManifest(bootHtml, origin) {
  const { graph, scripts } = bootGraph(bootHtml, origin);
  const urls = new Set();
  const add = resource => {
    if (typeof resource !== 'string' || !resource.startsWith('/plugins/??')
      || /[\s\\]/.test(resource)) throw new Error('Invalid published plugin URL');
    const url = new URL(resource, origin);
    if (url.origin !== origin || url.pathname !== '/plugins/' || url.username || url.password
      || url.hash || url.href !== origin + resource) throw new Error('Invalid published plugin URL');
    urls.add(url.href);
  };
  for (const entry of [...graph.entries, ...graph.batches]) {
    if (!record(entry)) throw new Error('Invalid DSH resource entry');
    add(entry.url);
  }
  for (const [, attributes] of scripts) {
    const src = attributes.match(/(?:^|\s)src\s*=\s*(["'])(.*?)\1/i);
    if (!src) {
      if (/(?:^|\s)src\s*=/i.test(attributes)) throw new Error('Unquoted script URL');
      continue;
    }
    const resource = src[2].replaceAll('&amp;', '&');
    const url = new URL(resource, origin);
    if (url.origin !== origin || url.username || url.password || url.hash) {
      throw new Error('External script is not part of the B0 boot graph');
    }
    if (url.pathname.startsWith('/plugins/')) add(resource);
  }
  if (!urls.size) throw new Error('Empty DSH plugin manifest');
  return urls;
}

/** Admit only the pinned Host's per-boot entry revision rotation.
 * Package identities/order and content-addressed batch URLs must be identical.
 * The returned allowlist still contains exact URLs, never a revision wildcard.
 */
export function refreshedPluginManifest(previousHtml, nextHtml, origin) {
  const oldUrls = pluginManifest(previousHtml, origin);
  const nextUrls = pluginManifest(nextHtml, origin);
  const previous = bootGraph(previousHtml, origin).graph;
  const next = bootGraph(nextHtml, origin).graph;
  const fail = () => { throw new Error('Pinned plugin manifest changed beyond a Host boot revision'); };
  if (previous.entries.length !== next.entries.length || previous.batches.length !== next.batches.length) fail();
  const entryIdentity = (entry, index) => {
    const match = entry.url.match(/^(\/plugins\/\?\?[^&?]+)&rev=([a-f0-9]{16})-([0-9]+)$/);
    if (!match || match[3] !== String(index)) return fail();
    return { path: match[1], nonce: match[2] };
  };
  const oldEntries = previous.entries.map(entryIdentity);
  const nextEntries = next.entries.map(entryIdentity);
  if (!oldEntries.length || new Set(oldEntries.map(e => e.nonce)).size !== 1
    || new Set(nextEntries.map(e => e.nonce)).size !== 1) fail();
  if (oldEntries.some((entry, index) => entry.path !== nextEntries[index].path)) fail();
  if (previous.batches.some((entry, index) => entry.url !== next.batches[index].url)) fail();
  for (const [graph, urls] of [[previous, oldUrls], [next, nextUrls]]) {
    const declared = new Set([...graph.entries, ...graph.batches].map(entry => origin + entry.url));
    if ([...urls].some(url => !declared.has(url))) fail();
  }
  return nextUrls;
}

/** Project every response; a failure never exposes upstream message/details. */
export function safeRpcResult(envelope, rpcId, method, scope, filter) {
  if (typeof rpcId !== 'string' || !rpcId || rpcId.length > 256
    || !record(envelope) || envelope.type !== 'server-response' || envelope.rpcId !== rpcId
    || !record(envelope.result) || typeof envelope.result.ok !== 'boolean') return null;
  if (!envelope.result.ok) {
    if (!record(envelope.result.error)) return null;
    return { type: 'server-response', rpcId, result: { ok: false,
      error: { code: 'gateway/internal', message: 'B0上游请求失败；内部诊断未公开', details: {} } } };
  }
  if (typeof filter !== 'function') return null;
  try {
    const value = filter(method, envelope.result.value, scope);
    if (value === null || value === undefined) return null;
    return { type: 'server-response', rpcId, result: { ok: true, value } };
  } catch { return null; }
}
