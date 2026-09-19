/** Cockpit product cabinet: harvest workspace files. Does not wait on plugin tools. */

const HTML_EXT = /\.(html?|htm)$/i;
const SHEET_EXT = /\.(xlsx|xls|csv)$/i;
const PDF_EXT = /\.pdf$/i;
const SKIP_DIR = new Set(['node_modules', '.git', '.context']);

export const DEFAULT_WORKSPACE_SCAN_MAX = 80;
export const DEFAULT_WORKSPACE_DIR_DEPTH = 2;
export const DEFAULT_WORKSPACE_LIST_CAP = 40;

export function classifyWorkspaceFile(path) {
  const name = String(path).split('/').pop() ?? '';
  if (HTML_EXT.test(name)) return 'html';
  if (SHEET_EXT.test(name)) return 'spreadsheet';
  if (PDF_EXT.test(name)) return 'pdf';
  return null;
}

function encodeSegment(segment) {
  return encodeURIComponent(String(segment)).replace(/%3A/gi, ':');
}

export function isSafeWorkspaceRelPath(path) {
  const normalized = String(path ?? '').replace(/\\/g, '/').replace(/^(?:\.\/)+/, '');
  if (!normalized || normalized.startsWith('/') || normalized.includes('://') || normalized.includes('\0')) {
    return false;
  }
  return normalized.split('/').every(part => part.length > 0 && part !== '.' && part !== '..');
}

/** Event/tool paths may be absolute or contain `../`; those are never trusted as workspace reads. */
export function workspaceRelFromEventPath(path) {
  const raw = String(path ?? '').replace(/\\/g, '/');
  if (!raw || raw.includes('\0') || raw.includes('://')) return null;
  if (raw.startsWith('/') || /^[A-Za-z]:\//.test(raw)) return null;
  const normalized = raw.replace(/^(?:\.\/)+/, '');
  return isSafeWorkspaceRelPath(normalized) ? normalized : null;
}

export function unwrapRemoteValue(result) {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return null;
  if ('ok' in result) {
    if (result.ok !== true) return null;
    const value = result.value;
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  }
  return result;
}

export function fileResourceAddress(sessionId, path) {
  const normalized = String(path).replace(/\\/g, '/').replace(/^(?:\.\/)+/, '');
  if (!isSafeWorkspaceRelPath(normalized)) return '';
  const encodedPath = normalized.split('/').map(encodeSegment).join('/');
  return `dsh-resource://file/session/${encodeSegment(sessionId)}/${encodedPath}`;
}

export function joinWorkspacePath(dir, name) {
  const prefix = dir && dir !== '.' ? dir.replace(/\/$/, '') : '';
  return prefix ? `${prefix}/${name}` : name;
}

export function workspaceEntriesToProducts(sessionId, listing, { depth = 0, dirDepth = DEFAULT_WORKSPACE_DIR_DEPTH } = {}) {
  const dir = listing?.path ?? '';
  const entries = Array.isArray(listing?.entries) ? listing.entries : [];
  const products = [];
  for (const entry of entries) {
    if (!entry?.name || SKIP_DIR.has(entry.name)) continue;
    if (/[\\/]/.test(entry.name) || entry.name === '..' || entry.name === '.') continue;
    const path = joinWorkspacePath(dir, entry.name);
    if (!isSafeWorkspaceRelPath(path)) continue;
    if (entry.type === 'file') {
      const kind = classifyWorkspaceFile(path);
      if (!kind) continue;
      products.push({
        id: `file:${sessionId}:${path}`,
        kind,
        title: entry.name,
        path,
        sessionId,
        size: entry.size,
        source: 'workspace-file',
      });
    } else if (entry.type === 'directory' && depth < dirDepth) {
      products.push({ id: `dir:${sessionId}:${path}`, kind: 'directory', title: entry.name, path, sessionId });
    }
  }
  return products;
}

export function cockpitProductIdentity(item) {
  if (!item || typeof item !== 'object') return '';
  if (typeof item.page_id === 'string' && item.page_id) return `page:${item.page_id}`;
  if (typeof item.board_id === 'string' && item.board_id) return `board:${item.board_id}`;
  const sessionId = item.sessionId;
  const path = item.path;
  if (typeof sessionId === 'string' && sessionId && typeof path === 'string' && isSafeWorkspaceRelPath(path)) {
    return `file:${sessionId}:${path}`;
  }
  if (typeof item.id === 'string' && item.id.startsWith('file:')) {
    const rest = item.id.slice(5);
    const split = rest.indexOf(':');
    if (split > 0 && isSafeWorkspaceRelPath(rest.slice(split + 1))) return item.id;
  }
  return '';
}

export function mergeCockpitProducts({ files = [], boards = [], pages = [] } = {}) {
  const seen = new Set();
  const items = [];
  const push = (item) => {
    const id = item.id || cockpitProductIdentity(item);
    if (!id || seen.has(id)) return;
    seen.add(id);
    items.push({ ...item, id });
  };
  for (const page of pages) {
    if (!page?.page_id) continue;
    push({
      id: `page:${page.page_id}`,
      kind: 'html',
      title: page.title || page.page_id,
      page_id: page.page_id,
      source: 'page-library',
      subtitle: page.version != null ? `v${page.version}` : undefined,
    });
  }
  for (const board of boards) {
    if (!board?.board_id) continue;
    push({
      id: `board:${board.board_id}`,
      kind: 'board',
      title: board.title || board.board_id,
      board_id: board.board_id,
      source: 'board-library',
      subtitle: board.version != null ? `v${board.version}` : undefined,
    });
  }
  for (const file of files) {
    if (file.kind === 'directory') continue;
    const identity = cockpitProductIdentity(file);
    if (!identity.startsWith('file:')) continue;
    push({
      ...file,
      id: identity,
      source: file.source || 'workspace-file',
    });
  }
  return items;
}

export async function collectWorkspaceScan(listDir, sessionId, {
  signal, max = DEFAULT_WORKSPACE_SCAN_MAX, dirDepth = DEFAULT_WORKSPACE_DIR_DEPTH,
  listCap = DEFAULT_WORKSPACE_LIST_CAP,
} = {}) {
  if (typeof listDir !== 'function') {
    return { status: 'error', sessionId: sessionId || null, files: [], truncated: false, error: 'no-list', lists: 0 };
  }
  if (!sessionId) {
    return { status: 'no-session', sessionId: null, files: [], truncated: false, error: 'no-session', lists: 0 };
  }
  const files = [];
  const queue = [{ path: '.', depth: 0 }];
  let truncated = false;
  let lists = 0;
  let rootFailed = false;
  while (queue.length > 0) {
    if (files.length >= max || lists >= listCap) {
      truncated = true;
      break;
    }
    const { path, depth } = queue.shift();
    lists += 1;
    let listing;
    try {
      listing = unwrapRemoteValue(await listDir(sessionId, path, signal));
    } catch {
      if (path === '.') rootFailed = true;
      continue;
    }
    if (!listing) {
      if (path === '.') rootFailed = true;
      continue;
    }
    if (listing.truncated === true) truncated = true;
    const products = workspaceEntriesToProducts(sessionId, listing, { depth, dirDepth });
    for (const item of products) {
      if (item.kind === 'directory') {
        if (depth < dirDepth) queue.push({ path: item.path, depth: depth + 1 });
        continue;
      }
      if (files.length >= max) {
        truncated = true;
        break;
      }
      files.push(item);
    }
  }
  if (rootFailed && files.length === 0) {
    return { status: 'error', sessionId, files: [], truncated, error: 'list-failed', lists };
  }
  return {
    status: files.length ? 'ready' : 'empty',
    sessionId,
    files,
    truncated,
    error: null,
    lists,
  };
}

export async function collectWorkspaceProducts(listDir, sessionId, options) {
  const scan = await collectWorkspaceScan(listDir, sessionId, options);
  return scan.files;
}

function readPagePayload(raw) {
  const first = unwrapRemoteValue(raw);
  if (!first) return null;
  if (typeof first.text === 'string') return first;
  const nested = first.value;
  if (nested && typeof nested === 'object' && !Array.isArray(nested) && typeof nested.text === 'string') return nested;
  return null;
}

export async function readWorkspaceFileText(read, sessionId, path, { signal, limit = 4000, maxPages = 32 } = {}) {
  if (typeof read !== 'function') return { status: 'error', text: null, reason: 'no-read', eof: false };
  if (!sessionId) return { status: 'rejected', text: null, reason: 'no-session', eof: false };
  if (!isSafeWorkspaceRelPath(path)) return { status: 'rejected', text: null, reason: 'unsafe-path', eof: false };
  try {
    const chunks = [];
    let offset = 1;
    for (let index = 0; index < maxPages; index++) {
      const raw = await read(sessionId, path, { offset, limit }, signal);
      signal?.throwIfAborted();
      const page = readPagePayload(raw);
      if (!page || typeof page.text !== 'string') return { status: 'error', text: null, reason: 'invalid-page', eof: false };
      if (page.text) chunks.push(page.text);
      const atomic = !Object.hasOwn(page, 'eof') && !Object.hasOwn(page, 'lines') && !Object.hasOwn(page, 'offset');
      if (page.eof === true || atomic) return chunks.length
        ? { status: 'ok', text: chunks.join('\n'), eof: true }
        : { status: 'empty', text: null, reason: 'empty-or-missing', eof: true };
      if (page.eof !== false || !page.text || !Number.isSafeInteger(page.lines) || page.lines <= 0
        || (page.offset !== undefined && page.offset !== offset)) return { status: 'error', text: null, reason: 'incomplete-page', eof: false };
      offset += page.lines;
    }
    return { status: 'error', text: null, reason: 'page-limit-before-eof', eof: false };
  } catch {
    return { status: 'error', text: null, reason: 'read-failed', eof: false };
  }
}
