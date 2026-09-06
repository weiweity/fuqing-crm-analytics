import test from 'node:test';
import assert from 'node:assert/strict';
import {
  FIXTURE, DEFAULT_TITLE, createEditor, changeDraft, previewTitle, applyTitle,
  decodeFixture, normalizeTitle, serializeTitle, restoreTitle, executeFixture,
} from '../src/model.mjs';

test('fixture has internally consistent synthetic counts and round-trips through presentation metadata', () => {
  assert.equal(FIXTURE.repeat_customers / FIXTURE.customers, FIXTURE.repeat_rate);
  assert.deepEqual(decodeFixture(JSON.parse(JSON.stringify(FIXTURE))), FIXTURE);
});
test('unknown, partial, extra, or altered metadata never becomes a successful card', () => {
  for (const value of [null, [], {}, { ...FIXTURE, schema_version: 'v2' }, { ...FIXTURE, customers: 99 }, { ...FIXTURE, owner: 'admin' }]) {
    assert.equal(decodeFixture(value), null);
  }
});
test('preview does not apply; apply changes only a UI title after explicit preview', () => {
  const original = createEditor();
  const preview = previewTitle(changeDraft(original, '  本周渠道  '));
  assert.equal(preview.title, DEFAULT_TITLE);
  assert.equal(preview.preview.title, '本周渠道');
  const applied = applyTitle(preview);
  assert.equal(applied.title, '本周渠道');
  assert.equal(applied.revision, 1);
  assert.equal(applied.preview, null);
  assert.equal(FIXTURE.customers, 100);
});
test('editing after preview invalidates it; stale revision also cannot apply', () => {
  const preview = previewTitle(changeDraft(createEditor(), '新标题'));
  assert.throws(() => applyTitle(changeDraft(preview, '又改标题')), /预览已失效/);
  assert.throws(() => applyTitle({ ...preview, revision: 9 }), /预览已失效/);
});
test('titles are bounded; plain text remains plain text without an HTML execution path', () => {
  for (const title of ['', ' '.repeat(2), '字'.repeat(41), 'bad\nvalue']) assert.throws(() => normalizeTitle(title));
  assert.equal(normalizeTitle('字'.repeat(40)).length, 40);
  assert.equal(normalizeTitle('<b>只是标题</b>'), '<b>只是标题</b>');
});
test('refresh restore persists only the title, never synthetic facts or business identity', () => {
  const wire = serializeTitle('恢复标题');
  assert.deepEqual(Object.keys(JSON.parse(wire)).sort(), ['schema_version', 'title']);
  assert.deepEqual(restoreTitle(wire), { title: '恢复标题', restored: true, invalid: false });
  assert.equal(restoreTitle(null).title, DEFAULT_TITLE);
});
test('corrupt or future preferences fall back safely', () => {
  for (const raw of ['{', 'null', '[]', '{"schema_version":"v2","title":"x"}', '{"schema_version":"analytics-b0-ui/v1","title":"x","customers":100}']) {
    assert.deepEqual(restoreTitle(raw), { title: DEFAULT_TITLE, restored: false, invalid: true });
  }
});
test('tool supports only the fixed query and honors cancellation', async () => {
  assert.deepEqual(await executeFixture('channel_repeat_rate', new AbortController().signal), FIXTURE);
  await assert.rejects(executeFixture('arbitrary_sql', new AbortController().signal), /B0_UNSUPPORTED_QUERY/);
  const aborted = new AbortController();
  aborted.abort();
  await assert.rejects(executeFixture('channel_repeat_rate', aborted.signal), { name: 'AbortError' });
});
