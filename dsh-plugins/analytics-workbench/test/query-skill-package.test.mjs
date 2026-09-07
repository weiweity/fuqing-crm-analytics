import test from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { packSkills } from '../pack-skills.mjs';
import { freezeSkillPackage, packageDigest } from '../src/skill-package.mjs';

const plugin = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const input = await packSkills(plugin, 'channel_followup');
const b0 = await packSkills(plugin);

test('query package is a second frozen family and does not change B0 digest', () => {
  const pack = freezeSkillPackage(input, 'channel_followup');
  const original = freezeSkillPackage(b0);
  assert.equal(pack.skillName, 'channel-followup-query');
  assert.equal(pack.resourceToolName, 'analytics_channel_followup_skill_resource');
  assert.equal(pack.digest, packageDigest(input.manifest, 'channel_followup'));
  assert.notEqual(pack.digest, original.digest);
  assert.equal(JSON.parse(pack.read('assets/result-example.json').content).numeric_values, null);
  assert.throws(() => freezeSkillPackage(input));
});
