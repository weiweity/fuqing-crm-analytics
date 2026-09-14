/** Real pinned SlotCore boundary checks, not a native-chat/browser acceptance test. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';

const plugin = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const pin = JSON.parse(await readFile(join(plugin, 'toolchain.json'), 'utf8'));
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: upstream, encoding: 'utf8' }).trim(), pin.upstream_sha);
const { SlotCore } = await import(pathToFileURL(join(upstream, 'packages/client/ui-slots/lib/index.js')).href);

function fixture() {
  const core = new SlotCore();
  core.register({ name: 'root', children: {
    main: { kind: 'keyed', scope: 'root' },
    rightbar: { kind: 'single', scope: 'root' },
    'shell.overlay': { kind: 'list', scope: 'root' },
  } }, () => null);
  core.register({ name: 'main', key: 'conversation', children: {
    'main.conversation': { kind: 'single', scope: 'session-maybe' },
  } }, () => null);
  core.register({ name: 'main.conversation' }, () => null);
  core.register({ name: 'rightbar' }, () => null);
  return core;
}

test('pinned core refuses a cockpit declaring the already-owned native conversation child', () => {
  const core = fixture();
  const nativeEntries = core.entries('main.conversation');
  assert.throws(() => core.register({ name: 'main', key: 'cockpit', children: {
    'main.conversation': { kind: 'single', scope: 'session-maybe' },
  } }, () => null), /already declared/);
  assert.equal(core.entries('main.conversation'), nativeEntries);
  assert.deepEqual(core.entriesOfSlot('main').map(e => e.options.key), ['conversation']);
});

test('rightbar is a single occupied seat: priority override shadows rather than appends native content', () => {
  const core = fixture();
  const native = core.entriesOfSlot('rightbar')[0];
  assert.throws(() => core.register({ name: 'rightbar' }, () => null), /already has/);
  const dispose = core.register({ name: 'rightbar', priority: -10 }, () => null);
  assert.equal(core.entriesOfSlot('rightbar').length, 1);
  assert.notEqual(core.entriesOfSlot('rightbar')[0], native);
  dispose();
  assert.equal(core.entriesOfSlot('rightbar')[0], native);
});

test('additive business overlay can unload without removing the native main or rightbar', () => {
  const core = fixture();
  const native = core.entriesOfSlot('main')[0];
  const right = core.entriesOfSlot('rightbar')[0];
  const dispose = core.register({ name: 'shell.overlay', id: 'shine-mage.cockpit-composition' }, () => null);
  assert.equal(core.entriesOfSlot('shell.overlay').length, 1);
  dispose();
  assert.equal(core.entriesOfSlot('shell.overlay').length, 0);
  assert.equal(core.entriesOfSlot('main')[0], native);
  assert.equal(core.entriesOfSlot('rightbar')[0], right);
});
