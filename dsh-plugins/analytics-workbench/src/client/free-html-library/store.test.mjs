import test from 'node:test';
import assert from 'node:assert/strict';
import { createMockPageAdapters, escapeHtml } from './mock-adapters.mjs';
import { createFreeHtmlLibraryStore } from './store.mjs';
import { bindingLabel } from './host-visual.mjs';

test('empty library can generate without data; failure keeps the prompt', async () => {
  const ok = createFreeHtmlLibraryStore();
  ok.setPrompt('做一张本周收入波动复盘页');
  await ok.generate();
  assert.equal(ok.getSnapshot().view, 'workspace');
  assert.equal(ok.getSnapshot().current.binding_state, 'UNBOUND_SAMPLE');
  assert.equal(ok.getSnapshot().current.version, 1);
  assert.equal(ok.hasUnsavedChanges(), false);
  const failing = createFreeHtmlLibraryStore({ adapters: createMockPageAdapters({ fail: { generate: '离线，生成失败' } }) });
  failing.setPrompt('保留我');
  await failing.generate();
  assert.equal(failing.getSnapshot().prompt, '保留我');
  assert.equal(failing.getSnapshot().current, null);
  assert.match(failing.getSnapshot().message, /保留输入|离线|生成失败/);
});

test('browse vs edit: exit/cancel/close are not save; D6 and D9 each add one version', async () => {
  const store = createFreeHtmlLibraryStore();
  store.setPrompt('标题页');
  await store.generate();
  const v1 = store.getSnapshot().current.version;
  store.enterEdit();
  assert.equal(store.hasActiveEditContext(), false);
  store.selectLocatable({ node_id: 'n_title', mapping: 'valid' });
  assert.equal(store.hasActiveEditContext(), true);
  assert.equal(store.hasUnsavedChanges(), false, 'clean selection is not dirty');
  store.exitEdit();
  assert.equal(store.getSnapshot().current.version, v1);
  store.enterEdit();
  store.selectLocatable({ node_id: 'n_title', mapping: 'valid' });
  await store.previewPatch('新标题');
  assert.equal(store.hasUnsavedChanges(), true);
  await store.cancelPreview();
  assert.equal(store.getSnapshot().current.version, v1);
  assert.equal(store.getSnapshot().preview, null);
  store.selectLocatable({ node_id: 'n_title', mapping: 'valid' });
  await store.previewPatch('新标题');
  await store.confirmPatch();
  assert.equal(store.getSnapshot().current.version, v1 + 1);
  assert.match(store.getSnapshot().current.package.html, /新标题/);
  assert.doesNotMatch(store.getSnapshot().current.package.html, />标题页</);
  const afterPatch = store.getSnapshot().current.package.html;
  await store.saveDraft();
  assert.equal(store.getSnapshot().current.version, v1 + 2);
  await store.rollback(v1);
  assert.equal(store.getSnapshot().current.version, v1);
  assert.match(store.getSnapshot().current.package.html, /标题页/);
  assert.doesNotMatch(store.getSnapshot().current.package.html, /新标题/);
  assert.notEqual(store.getSnapshot().current.package.html, afterPatch);
});

test('generate HTML-escapes prompt and setRailOpen(true) expands the rail', async () => {
  const store = createFreeHtmlLibraryStore({ viewportWidth: 1440 });
  store.setPrompt('<img src=x onerror=alert(1)>');
  await store.generate();
  assert.match(store.getSnapshot().current.package.html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(store.getSnapshot().current.package.html, /<img src=x/);
  assert.equal(escapeHtml('<a>'), '&lt;a&gt;');
  store.setRailOpen(true);
  assert.equal(store.getSnapshot().railCollapsed, false);
  store.setRailOpen(false);
  assert.equal(store.getSnapshot().railCollapsed, true);
  store.toggleRail();
  assert.equal(store.getSnapshot().railCollapsed, false);
});

test('partial binding label requires unverified bindings, not merely a non-empty list', () => {
  assert.equal(bindingLabel('BOUND_VERIFIED', { partial: false }), '已绑定经营数据');
  assert.equal(bindingLabel('BOUND_VERIFIED', { partial: true }), '部分已绑定');
});

test('stale mapping requires reselect; dirty leave offers three choices', async () => {
  const store = createFreeHtmlLibraryStore();
  store.setPrompt('x');
  await store.generate();
  store.enterEdit();
  store.selectLocatable({ node_id: 'n_missing', mapping: 'stale' });
  assert.equal(store.getSnapshot().selection.requireReselect, true);
  assert.notEqual(store.getSnapshot().selection.scope, 'whole_package');
  store.markLocalDraft({ ...store.getSnapshot().current.package, html: '<p>draft</p>' });
  const leave = store.requestLeave('home');
  assert.equal(leave.blocked, true);
  assert.equal(store.getSnapshot().view, 'workspace');
  assert.equal(store.getSnapshot().pendingLeaveIntent, 'home');
  store.stayLeave();
  assert.equal(store.getSnapshot().view, 'workspace');
  assert.equal(store.getSnapshot().pendingLeaveIntent, null);
  store.requestLeave('home');
  const discarded = await store.discardAndLeave();
  assert.equal(discarded.navigated, true);
  assert.equal(store.getSnapshot().view, 'home');
  assert.equal(store.hasUnsavedChanges(), false);
});

test('save-and-leave creates one D9 version then navigates', async () => {
  const store = createFreeHtmlLibraryStore();
  store.setPrompt('x');
  await store.generate();
  const version = store.getSnapshot().current.version;
  store.markLocalDraft({ ...store.getSnapshot().current.package, html: '<p>draft</p>' });
  store.requestLeave('home');
  const saved = await store.saveAndLeave();
  assert.equal(saved.navigated, true);
  assert.equal(store.getSnapshot().view, 'home');
  const listed = store.getSnapshot().pages[0];
  assert.equal(listed.version, version + 1);
  assert.equal(store.hasUnsavedChanges(), false);
});

test('persistForLeave saves without navigating away from the workspace', async () => {
  const store = createFreeHtmlLibraryStore();
  store.setPrompt('x');
  await store.generate();
  store.markLocalDraft({ ...store.getSnapshot().current.package, html: '<p>draft</p>' });
  const persisted = await store.persistForLeave();
  assert.equal(persisted.ok, true);
  assert.equal(store.getSnapshot().view, 'workspace');
  assert.equal(store.hasUnsavedChanges(), false);
});

test('save-and-leave with a pending PATCH confirms D6 once, not a second D9', async () => {
  const store = createFreeHtmlLibraryStore();
  store.setPrompt('x');
  await store.generate();
  const version = store.getSnapshot().current.version;
  store.enterEdit();
  store.selectLocatable({ kind: 'static_element', node_id: 'n_title', mapping: 'valid' });
  await store.previewPatch('把标题改得更清楚');
  assert.equal(store.getSnapshot().preview.status, 'PENDING');
  store.requestLeave('home');
  const saved = await store.saveAndLeave();
  assert.equal(saved.navigated, true);
  assert.equal(store.getSnapshot().view, 'home');
  assert.equal(store.getSnapshot().pages[0].version, version + 1);
  assert.equal(store.hasUnsavedChanges(), false);
});
