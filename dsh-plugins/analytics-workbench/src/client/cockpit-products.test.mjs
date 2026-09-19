import test from 'node:test';
import assert from 'node:assert/strict';
import {
  classifyWorkspaceFile, fileResourceAddress, mergeCockpitProducts,
  workspaceEntriesToProducts, collectWorkspaceProducts,
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
