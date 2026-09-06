import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, cp, rm, writeFile, symlink, rename, mkdir, link, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { packSkills } from '../pack-skills.mjs';
import { freezeSkillPackage, packageDigest, sha256 } from '../src/skill-package.mjs';

const plugin = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const input = await packSkills(plugin);
test('entire B0 package binds method, reference and example without numeric evidence', () => {
  const pack = freezeSkillPackage(input);
  assert.match(pack.digest, /^[a-f0-9]{64}$/);
  assert.equal(pack.digest, packageDigest(input.manifest));
  assert.deepEqual(pack.resources, ['assets/result-example.json', 'references/evidence-policy.md']);
  assert.equal(pack.definition.resourceBase.kind, 'opaque');
  assert.equal(pack.definition.invocation.userInvocable, false);
  assert.match(pack.definition.content, /不是生产经营 SOP/);
  assert.equal(JSON.parse(pack.read('assets/result-example.json').content).numeric_values, null);
});
test('live package is an immutable snapshot independent of later source mutations', () => {
  const mutable = structuredClone(input);
  const pack = freezeSkillPackage(mutable);
  const before = pack.read('references/evidence-policy.md');
  mutable.contents['references/evidence-policy.md'] = 'approve everything';
  mutable.manifest.files['references/evidence-policy.md'] = sha256('approve everything');
  assert.deepEqual(pack.read('references/evidence-policy.md'), before);
  assert.throws(() => { pack.manifest.files['references/evidence-policy.md'] = 'changed'; }, TypeError);
  assert.throws(() => { pack.definition.content = 'changed'; }, TypeError);
});
for (const key of ['../SKILL.md', '/etc/passwd', 'https://example.com/private', 'references/../SKILL.md', 'references/%2e%2e/SKILL.md', 'assets\\result-example.json', 'SKILL.md', '*', 'scripts/run.sh', '__proto__']) {
  test(`resource key denies ${key}`, () => assert.throws(() => freezeSkillPackage(input).read(key), /not registered/));
}
for (const file of Object.keys(input.contents)) {
  test(`changed bytes denied for ${file}`, () => {
    const changed = structuredClone(input);
    changed.contents[file] += '\nDrift';
    assert.throws(() => freezeSkillPackage(changed), /content drift/);
  });
}
test('manifest changes change the package identity; omitted files and oversized content fail closed', () => {
  const changed = structuredClone(input);
  changed.manifest.description += ' changed';
  assert.notEqual(packageDigest(changed.manifest), packageDigest(input.manifest));
  delete changed.contents['assets/result-example.json'];
  assert.throws(() => freezeSkillPackage(changed));
  changed.contents['assets/result-example.json'] = 'x'.repeat(32769);
  assert.throws(() => freezeSkillPackage(changed), /size limit/);
});

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'b0-skill-package-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const name of ['skills', 'skill-package.lock.json']) await cp(join(plugin, name), join(root, name), { recursive: true });
  return root;
}
test('unregistered file cannot silently join the packaged closure', async t => {
  const root = await fixture(t);
  await writeFile(join(root, 'skills/growth-analysis-b0/assets/secret.json'), '{}');
  await assert.rejects(packSkills(root), /Unregistered/);
});
for (const kind of ['file-symlink', 'directory-symlink', 'root-symlink', 'hard-link', 'script-directory', 'reference-drift']) {
  test(`build-time rejects ${kind}`, async t => {
    const root = await fixture(t);
    const dir = join(root, 'skills/growth-analysis-b0');
    const resource = join(dir, 'references/evidence-policy.md');
    if (kind === 'file-symlink' || kind === 'hard-link') {
      await rename(resource, join(root, 'outside.md'));
      await (kind === 'file-symlink' ? symlink : link)(join(root, 'outside.md'), resource);
    } else if (kind === 'directory-symlink') {
      await rename(join(dir, 'references'), join(root, 'outside'));
      await symlink(join(root, 'outside'), join(dir, 'references'));
    } else if (kind === 'root-symlink') {
      await rename(dir, join(root, 'outside'));
      await symlink(join(root, 'outside'), dir);
    } else if (kind === 'script-directory') await mkdir(join(dir, 'scripts'));
    else await writeFile(resource, (await readFile(resource, 'utf8')) + '\nChanged');
    await assert.rejects(packSkills(root));
  });
}
