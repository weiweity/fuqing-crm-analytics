import test from 'node:test';
import assert from 'node:assert/strict';
import {
  classifyWorkspaceFile, fileResourceAddress, isSafeWorkspaceRelPath, joinWorkspacePath, mergeCockpitProducts,
  unwrapRemoteValue, workspaceEntriesToProducts, collectWorkspaceProducts, collectWorkspaceScan,
  readWorkspaceFileText, workspaceRelFromEventPath, cockpitProductIdentity,
} from './cockpit-products.mjs';

test('classify html spreadsheet and pdf only', () => {
  assert.equal(classifyWorkspaceFile('free-html-page/index.html'), 'html');
  assert.equal(classifyWorkspaceFile('a.CSV'), 'spreadsheet');
  assert.equal(classifyWorkspaceFile('deck.pdf'), 'pdf');
  assert.equal(classifyWorkspaceFile('app.js'), null);
});

test('file resource address matches DSH file tabs', () => {
  assert.equal(
    fileResourceAddress('s1', 'src/a.ts'),
    'dsh-resource://file/session/s1/src/a.ts',
  );
  assert.equal(
    fileResourceAddress('s 1', 'a b.html'),
    'dsh-resource://file/session/s%201/a%20b.html',
  );
});

test('merge keeps same-title page and workspace file as distinct identities', () => {
  const items = mergeCockpitProducts({
    pages: [{ page_id: 'page_1', title: 'index.html', version: 2 }],
    boards: [{ board_id: 'board_1', title: '经营看板', version: 3 }],
    files: [
      { id: 'file:s1:index.html', kind: 'html', title: 'index.html', path: 'index.html', sessionId: 's1' },
      { id: 'file:s1:week.csv', kind: 'spreadsheet', title: 'week.csv', path: 'week.csv', sessionId: 's1' },
    ],
  });
  assert.equal(items.filter(item => item.title === 'index.html').length, 2);
  assert.equal(items.find(item => item.page_id === 'page_1').id, 'page:page_1');
  assert.equal(items.find(item => item.path === 'index.html').id, 'file:s1:index.html');
  assert.ok(items.some(item => item.kind === 'board'));
  assert.ok(items.some(item => item.kind === 'spreadsheet'));
});

test('merge does not mix two sessions that share a file name', () => {
  const items = mergeCockpitProducts({
    files: [
      { kind: 'html', title: 'index.html', path: 'index.html', sessionId: 'sess-a' },
      { kind: 'html', title: 'index.html', path: 'index.html', sessionId: 'sess-b' },
    ],
  });
  assert.deepEqual(items.map(item => item.id).sort(), ['file:sess-a:index.html', 'file:sess-b:index.html']);
});

test('collect walks one extra directory for html packages', async () => {
  const tree = {
    '.': { path: '', entries: [
      { name: 'notes.txt', type: 'file' },
      { name: 'free-html-page-1', type: 'directory' },
      { name: 'summary.pdf', type: 'file', size: 12 },
    ] },
    'free-html-page-1': { path: 'free-html-page-1', entries: [
      { name: 'index.html', type: 'file' },
      { name: 'app.js', type: 'file' },
    ] },
  };
  const files = await collectWorkspaceProducts(async (_session, path) => tree[path === '.' ? '.' : path], 'sess');
  assert.deepEqual(files.map(item => item.path).sort(), ['free-html-page-1/index.html', 'summary.pdf']);
});

test('classify htm/xlsx, keep colon in addresses, and join workspace paths', () => {
  assert.equal(classifyWorkspaceFile('page.HTM'), 'html');
  assert.equal(classifyWorkspaceFile('book.xlsx'), 'spreadsheet');
  assert.equal(classifyWorkspaceFile('legacy.xls'), 'spreadsheet');
  assert.equal(fileResourceAddress('s:1', './src\\a.ts'), 'dsh-resource://file/session/s:1/src/a.ts');
  assert.equal(joinWorkspacePath('.', 'a.html'), 'a.html');
  assert.equal(joinWorkspacePath('pkg/', 'index.html'), 'pkg/index.html');
  assert.equal(joinWorkspacePath('', 'root.html'), 'root.html');
  assert.equal(isSafeWorkspaceRelPath('../etc/passwd'), false);
  assert.equal(isSafeWorkspaceRelPath('/etc/passwd'), false);
  assert.equal(fileResourceAddress('s1', '../secret.html'), '');
  assert.deepEqual(
    workspaceEntriesToProducts('s1', { path: '.', entries: [
      { name: '..', type: 'directory' },
      { name: 'a/b.html', type: 'file' },
      { name: 'ok.html', type: 'file' },
    ] }).map(item => item.path),
    ['ok.html'],
  );
});

test('collect unwraps RemoteResult listings and skips failed envelopes', async () => {
  assert.equal(unwrapRemoteValue({ ok: false, error: { code: 'x' } }), null);
  const files = await collectWorkspaceProducts(async (_session, path) => {
    if (path === '.') {
      return { ok: true, value: { path: '', entries: [
        { name: 'week.html', type: 'file' },
        { name: 'pkg', type: 'directory' },
      ], truncated: false } };
    }
    return { ok: true, value: { path: 'pkg', entries: [{ name: 'index.html', type: 'file' }] } };
  }, 'sess');
  assert.deepEqual(files.map(item => item.path).sort(), ['pkg/index.html', 'week.html']);
  assert.deepEqual(await collectWorkspaceProducts(async () => ({ ok: false }), 'sess'), []);
});

test('collect skips hidden dirs, unreadable nested trees, and caps; merge drops incomplete rows', async () => {
  assert.deepEqual(await collectWorkspaceProducts(null, 'sess'), []);
  assert.deepEqual(await collectWorkspaceProducts(async () => ({ entries: [] }), ''), []);
  const tree = {
    '.': { path: '', entries: [
      { name: 'node_modules', type: 'directory' },
      { name: '.git', type: 'directory' },
      { name: '.context', type: 'directory' },
      { name: '', type: 'file' },
      { name: 'a.pdf', type: 'file' },
      { name: 'pkg', type: 'directory' },
      { name: 'sealed', type: 'directory' },
    ] },
    pkg: { path: 'pkg', entries: [
      { name: 'inner', type: 'directory' },
      { name: 'page.htm', type: 'file' },
    ] },
    'pkg/inner': { path: 'pkg/inner', entries: [{ name: 'deep.html', type: 'file' }] },
  };
  const listed = [];
  const files = await collectWorkspaceProducts(async (_session, path) => {
    listed.push(path);
    if (path === 'sealed') throw new Error('unreadable');
    return tree[path === '.' ? '.' : path];
  }, 'sess', { max: 2 });
  assert.deepEqual(files.map(item => item.path), ['a.pdf', 'pkg/page.htm']);
  assert.equal(listed.includes('pkg/inner'), false);
  assert.equal(listed.includes('node_modules'), false);
  const merged = mergeCockpitProducts({
    pages: [{ title: 'ghost' }, { page_id: 'page_x' }],
    boards: [{ title: 'ghost-board' }, { board_id: 'board_x' }],
    files: [
      { id: 'dir:s1:pkg', kind: 'directory', title: 'pkg' },
      { id: 'file:s1:a.pdf', kind: 'pdf', title: 'a.pdf' },
    ],
  });
  assert.equal(merged.find(item => item.id === 'page:page_x').title, 'page_x');
  assert.equal(merged.find(item => item.id === 'page:page_x').subtitle, undefined);
  assert.equal(merged.find(item => item.id === 'board:board_x').title, 'board_x');
  assert.equal(merged.some(item => item.kind === 'directory'), false);
  assert.equal(merged.some(item => item.title === 'ghost'), false);
  assert.deepEqual(mergeCockpitProducts(), []);
  assert.deepEqual(workspaceEntriesToProducts('s1', null), []);
});

test('collect walks two directory levels including ops-dashboard-live/web/index.html', async () => {
  const tree = {
    '.': { path: '', entries: [
      { name: 'ops-dashboard-live', type: 'directory' },
      { name: 'pkg', type: 'directory' },
    ] },
    'ops-dashboard-live': { path: 'ops-dashboard-live', entries: [
      { name: 'web', type: 'directory' },
      { name: 'snapshot.html', type: 'file' },
    ] },
    'ops-dashboard-live/web': { path: 'ops-dashboard-live/web', entries: [
      { name: 'index.html', type: 'file' },
    ] },
    pkg: { path: 'pkg', entries: [
      { name: 'inner', type: 'directory' },
      { name: 'page.htm', type: 'file' },
    ] },
    'pkg/inner': { path: 'pkg/inner', entries: [{ name: 'deep.html', type: 'file' }] },
  };
  const listed = [];
  const scan = await collectWorkspaceScan(async (_session, path) => {
    listed.push(path);
    return tree[path === '.' ? '.' : path];
  }, 'sess');
  assert.equal(scan.status, 'ready');
  assert.equal(scan.truncated, false);
  assert.deepEqual(scan.files.map(item => item.path).sort(), [
    'ops-dashboard-live/snapshot.html',
    'ops-dashboard-live/web/index.html',
    'pkg/inner/deep.html',
    'pkg/page.htm',
  ]);
  assert.ok(listed.includes('ops-dashboard-live/web'));
  assert.ok(listed.includes('pkg/inner'));
});

test('scan distinguishes empty, list failure, truncation, and no session', async () => {
  assert.equal((await collectWorkspaceScan(async () => ({ entries: [] }), 'sess')).status, 'empty');
  assert.equal((await collectWorkspaceScan(async () => ({ ok: false }), 'sess')).status, 'error');
  assert.equal((await collectWorkspaceScan(async () => ({ entries: [] }), '')).status, 'no-session');
  const many = {
    '.': { path: '', truncated: true, entries: [
      { name: 'a.html', type: 'file' },
      { name: 'b.html', type: 'file' },
    ] },
  };
  const capped = await collectWorkspaceScan(async () => many['.'], 'sess', { max: 1 });
  assert.equal(capped.truncated, true);
  assert.deepEqual(capped.files.map(item => item.path), ['a.html']);
});

test('readWorkspaceFileText pages to eof and rejects unsafe paths', async () => {
  const reads = [];
  const pages = {
    'paged.html': [
      { ok: true, value: { text: '<p>one</p>', eof: false, lines: 1, offset: 1 } },
      { ok: true, value: { text: '<p>two</p>', eof: true, lines: 1, offset: 2 } },
    ],
  };
  const read = async (sessionId, path, range) => {
    reads.push({ sessionId, path, range });
    if (path === 'paged.html') return pages['paged.html'].shift();
    if (path === 'direct.html') return { text: '<p>direct</p>' };
    if (path === 'empty.html') return { text: '' };
    throw new Error('missing');
  };
  assert.equal((await readWorkspaceFileText(read, 'sess', 'paged.html')).text, '<p>one</p>\n<p>two</p>');
  assert.equal((await readWorkspaceFileText(read, 'sess', 'direct.html')).status, 'ok');
  assert.equal((await readWorkspaceFileText(read, 'sess', 'empty.html')).status, 'empty');
  assert.equal((await readWorkspaceFileText(read, 'sess', '../secret.html')).reason, 'unsafe-path');
  assert.equal((await readWorkspaceFileText(read, '', 'a.html')).reason, 'no-session');
  assert.equal((await readWorkspaceFileText(read, 'sess', 'missing.html')).status, 'error');
  assert.equal(workspaceRelFromEventPath('/tmp/x.html'), null);
  assert.equal(workspaceRelFromEventPath('../x.html'), null);
  assert.equal(workspaceRelFromEventPath('ops-dashboard-live/web/index.html'), 'ops-dashboard-live/web/index.html');
  assert.equal(cockpitProductIdentity({ sessionId: 's1', path: 'a.html' }), 'file:s1:a.html');
});

test('explicit non-EOF and page bounds never masquerade as a complete file', async () => {
  const incomplete = await readWorkspaceFileText(async () => ({ text: 'partial', eof: false }), 's', 'a.html');
  assert.equal(incomplete.status, 'error'); assert.equal(incomplete.text, null); assert.equal(incomplete.eof, false);
  const bounded = await readWorkspaceFileText(async (_session, _path, range) => ({ text: 'partial', eof: false, lines: 1, offset: range.offset }), 's', 'a.html', { maxPages: 2 });
  assert.equal(bounded.reason, 'page-limit-before-eof'); assert.equal(bounded.text, null);
  const stalled = await readWorkspaceFileText(async () => ({ text: 'partial', eof: false, lines: 1, offset: 0 }), 's', 'a.html');
  assert.equal(stalled.status, 'error');
});
