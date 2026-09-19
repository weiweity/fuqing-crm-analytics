import test from 'node:test';
import assert from 'node:assert/strict';
import {
  classifyWorkspaceFile, fileResourceAddress, isSafeWorkspaceRelPath, joinWorkspacePath, mergeCockpitProducts,
  unwrapRemoteValue, workspaceEntriesToProducts, collectWorkspaceProducts,
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

test('merge prefers saved pages over duplicate workspace html names', () => {
  const items = mergeCockpitProducts({
    pages: [{ page_id: 'page_1', title: 'index.html', version: 2 }],
    boards: [{ board_id: 'board_1', title: '经营看板', version: 3 }],
    files: [
      { id: 'file:s1:index.html', kind: 'html', title: 'index.html', path: 'index.html', sessionId: 's1' },
      { id: 'file:s1:week.csv', kind: 'spreadsheet', title: 'week.csv', path: 'week.csv', sessionId: 's1' },
    ],
  });
  assert.equal(items.filter(item => item.title === 'index.html').length, 1);
  assert.equal(items.find(item => item.title === 'index.html').page_id, 'page_1');
  assert.ok(items.some(item => item.kind === 'board'));
  assert.ok(items.some(item => item.kind === 'spreadsheet'));
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
