/** Build-time packer for competition-growth. Does not modify plugin pack-skills.mjs. */
import assert from 'node:assert/strict';
import { constants } from 'node:fs';
import { lstat, open, readdir, realpath, writeFile } from 'node:fs/promises';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PACKAGE_LIMITS, SKILL_NAME, SKILL_VERSION, SCHEMA_VERSION, SCOPE } from './family.mjs';
import { freezeCompetitionSkillPackage, sha256, validateManifest } from './skill-package.mjs';

const here = dirname(fileURLToPath(import.meta.url));

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
    const content = new TextDecoder('utf-8', { fatal: true }).decode(buffer.subarray(0, bytesRead));
    assert.equal(Buffer.byteLength(content), bytesRead);
    return content;
  } finally { await handle.close(); }
}

export async function packCompetitionSkill(plugin) {
  const root = resolve(plugin, 'skills', SKILL_NAME);
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
        await walk(path, `${key}/`);
      } else {
        assert.ok(entry.isFile(), 'Unregistered package file');
        assert.ok((await realpath(path)).startsWith(canonical + sep), 'Resource escaped package');
        found.push(key);
      }
    }
  }
  await walk(root);
  const contents = {};
  const files = {};
  for (const key of found.sort()) {
    contents[key] = await regularBytes(join(root, key), PACKAGE_LIMITS.fileBytes);
    files[key] = sha256(contents[key]);
  }
  const manifest = {
    schema_version: SCHEMA_VERSION,
    name: SKILL_NAME,
    version: SKILL_VERSION,
    scope: SCOPE,
    description: 'Synthetic competition growth diagnosis method. Not a production SOP. No extra tools, data, or approval power.',
    files,
  };
  validateManifest(manifest);
  const input = { manifest, contents };
  freezeCompetitionSkillPackage(input);
  return input;
}

export async function writeSnapshots(plugin = resolve(here, '../..')) {
  const input = await packCompetitionSkill(plugin);
  const lockPath = join(here, 'skill-package.lock.json');
  const frozenPath = join(here, 'frozen-package.json');
  await writeFile(lockPath, `${JSON.stringify(input.manifest, null, 2)}\n`);
  await writeFile(frozenPath, `${JSON.stringify(input)}\n`);
  return input;
}
