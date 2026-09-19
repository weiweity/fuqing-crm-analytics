/** Cockpit product cabinet: harvest workspace files. Does not wait on plugin tools. */

const HTML_EXT = /\.(html?|htm)$/i;
const SHEET_EXT = /\.(xlsx|xls|csv)$/i;
const PDF_EXT = /\.pdf$/i;
const SKIP_DIR = new Set(['node_modules', '.git', '.context']);

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

export function workspaceEntriesToProducts(sessionId, listing, { depth = 0 } = {}) {
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
      });
    } else if (entry.type === 'directory' && depth < 2) {
      products.push({ id: `dir:${sessionId}:${path}`, kind: 'directory', title: entry.name, path, sessionId });
    }
  }
  return products;
}

export function mergeCockpitProducts({ files = [], boards = [], pages = [] } = {}) {
  const items = [];
  for (const page of pages) {
    if (!page?.page_id) continue;
    items.push({
      id: `page:${page.page_id}`,
      kind: 'html',
      title: page.title || page.page_id,
      page_id: page.page_id,
      subtitle: page.version != null ? `v${page.version}` : undefined,
    });
  }
  for (const board of boards) {
    if (!board?.board_id) continue;
    items.push({
      id: `board:${board.board_id}`,
      kind: 'board',
      title: board.title || board.board_id,
      board_id: board.board_id,
      subtitle: board.version != null ? `v${board.version}` : undefined,
    });
  }
  const pageTitles = new Set(items.filter(item => item.kind === 'html').map(item => item.title));
  for (const file of files) {
    if (file.kind === 'directory') continue;
    if (file.kind === 'html' && pageTitles.has(file.title)) continue;
    items.push(file);
  }
  return items;
}

export async function collectWorkspaceProducts(listDir, sessionId, { signal, max = 80 } = {}) {
  if (typeof listDir !== 'function' || !sessionId) return [];
  const root = unwrapRemoteValue(await listDir(sessionId, '.', signal));
  const first = workspaceEntriesToProducts(sessionId, root, { depth: 0 });
  const files = first.filter(item => item.kind !== 'directory');
  const dirs = first.filter(item => item.kind === 'directory');
  for (const dir of dirs) {
    if (files.length >= max) break;
    try {
      const nested = unwrapRemoteValue(await listDir(sessionId, dir.path, signal));
      files.push(...workspaceEntriesToProducts(sessionId, nested, { depth: 1 }).filter(item => item.kind !== 'directory'));
    } catch {
      /* skip unreadable directories */
    }
  }
  return files.slice(0, max);
}
