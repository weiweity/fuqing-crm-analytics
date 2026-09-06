/** Build-time only. Reject undeclared files and symlinks before bundling bytes. */
import assert from 'node:assert/strict';
import { constants } from 'node:fs';
import { lstat, open, readdir, realpath } from 'node:fs/promises';
import { join, resolve, sep } from 'node:path';
import { freezeSkillPackage, PACKAGE_LIMITS, validateManifest } from './src/skill-package.mjs';

async function regularBytes(path, limit) {
  const info = await lstat(path);
  assert.ok(info.isFile() && !info.isSymbolicLink() && info.nlink === 1, 'Only standalone regular files allowed');
  assert.ok(info.size > 0 && info.size <= limit, 'Resource size limit');
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const before = await handle.stat();
    assert.ok(before.isFile() && before.ino === info.ino && before.dev === info.dev && before.size <= limit, 'Source changed during open');
    const buffer = Buffer.alloc(limit + 1);
    const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
    const after = await handle.stat();
    assert.ok(bytesRead === before.size && bytesRead <= limit && after.mtimeMs === before.mtimeMs && after.size === before.size, 'Source changed during read');
    const bytes = buffer.subarray(0, bytesRead);
    const content = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    assert.equal(Buffer.byteLength(content), bytesRead);
    return content;
  } finally { await handle.close(); }
}

export async function packSkills(plugin) {
  const manifest = JSON.parse(await regularBytes(join(plugin, 'skill-package.lock.json'), 8192));
  validateManifest(manifest);
  const root = resolve(plugin, 'skills', manifest.name);
  for (const path of [join(plugin, 'skills'), root]) {
    const info = await lstat(path);
    assert.ok(info.isDirectory() && !info.isSymbolicLink(), 'Skill roots cannot be symlinks');
  }
  const canonical = await realpath(root);
  const found = [];
  async function walk(directory, prefix = '') {
    const entries = await readdir(directory, { withFileTypes: true });
    assert.ok(entries.length <= PACKAGE_LIMITS.files, 'Too many package entries');
    for (const entry of entries) {
      const key = prefix + entry.name;
      const path = join(directory, entry.name);
      assert.ok(!entry.isSymbolicLink(), 'Skill symlinks are forbidden');
      if (entry.isDirectory()) {
        assert.ok(!prefix && ['references', 'assets'].includes(entry.name), 'Undeclared resource directory');
        await walk(path, key + '/');
      } else {
        assert.ok(entry.isFile() && Object.hasOwn(manifest.files, key), 'Unregistered package file');
        assert.ok((await realpath(path)).startsWith(canonical + sep), 'Resource escaped package');
        found.push(key);
      }
    }
  }
  await walk(root);
  assert.deepEqual(found.sort(), Object.keys(manifest.files).sort(), 'Missing package file');
  const contents = {};
  for (const key of found) contents[key] = await regularBytes(join(root, key), PACKAGE_LIMITS.fileBytes);
  const input = { manifest, contents };
  freezeSkillPackage(input);
  return input;
}
