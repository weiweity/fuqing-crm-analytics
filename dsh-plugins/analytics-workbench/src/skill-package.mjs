/** Pure, bounded content contract. No filesystem, model loop or mutable memory. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

export const SKILL_NAME = 'growth-analysis-b0';
export const RESOURCE_TOOL_NAME = 'analytics_b0_skill_resource';
export const PACKAGE_LIMITS = Object.freeze({ files: 16, fileBytes: 32768, totalBytes: 65536 });
export const sha256 = value => createHash('sha256').update(value).digest('hex');
const resourcePath = /^(?:SKILL\.md|(?:references|assets)\/[a-z0-9][a-z0-9-]*\.(?:md|json))$/;
const exactKeys = (value, keys) => assert.deepEqual(Object.keys(value).sort(), [...keys].sort(), 'Unexpected package fields');

export function validateManifest(manifest) {
  exactKeys(manifest, ['schema_version', 'name', 'version', 'scope', 'description', 'files']);
  assert.equal(manifest.schema_version, 'analytics-b0-skill-package/v1');
  assert.equal(manifest.name, SKILL_NAME);
  assert.match(manifest.version, /^b0-v[1-9][0-9]*$/);
  assert.equal(manifest.scope, 'B0_SYNTHETIC_ONLY');
  assert.ok(typeof manifest.description === 'string' && manifest.description.length > 0 && manifest.description.length <= 500);
  const paths = Object.keys(manifest.files);
  assert.ok(paths.length > 0 && paths.length <= PACKAGE_LIMITS.files && paths.includes('SKILL.md'));
  for (const path of paths) {
    assert.match(path, resourcePath, 'Undeclared or unsafe resource path');
    assert.match(manifest.files[path], /^[a-f0-9]{64}$/, 'Invalid content hash');
  }
}

export function packageDigest(manifest) {
  validateManifest(manifest);
  return sha256(JSON.stringify({ ...manifest, files: Object.fromEntries(Object.entries(manifest.files).sort(([a], [b]) => a.localeCompare(b))) }));
}

/** Detach all inputs, recheck every byte, then expose immutable read-only values. */
export function freezeSkillPackage(input) {
  exactKeys(input, ['manifest', 'contents']);
  const manifest = structuredClone(input.manifest);
  validateManifest(manifest);
  exactKeys(input.contents, Object.keys(manifest.files));
  const contents = {};
  let bytes = 0;
  for (const [path, digest] of Object.entries(manifest.files)) {
    const content = input.contents[path];
    assert.equal(typeof content, 'string');
    const size = Buffer.byteLength(content);
    assert.ok(size > 0 && size <= PACKAGE_LIMITS.fileBytes, 'Resource size limit');
    bytes += size;
    assert.ok(bytes <= PACKAGE_LIMITS.totalBytes, 'Package size limit');
    assert.equal(sha256(content), digest, `Skill content drift: ${path}`);
    contents[path] = content;
  }
  const digest = packageDigest(manifest);
  const resources = Object.freeze(Object.keys(contents).filter(path => path !== 'SKILL.md').sort());
  return Object.freeze({
    manifest: Object.freeze({ ...manifest, files: Object.freeze(manifest.files) }),
    digest, resources,
    definition: Object.freeze({
      name: manifest.name, description: manifest.description,
      source: 'bundled', provider: 'analytics-b0-approved-bundle',
      invocation: Object.freeze({ modelInvocable: true, userInvocable: false }),
      resourceBase: Object.freeze({ kind: 'opaque', description: `Use ${RESOURCE_TOOL_NAME} with an exact declared resource key. Package ${digest}. No filesystem or script access.` }),
      content: contents['SKILL.md'],
    }),
    read(resource) {
      assert.ok(resources.includes(resource), 'Resource is not registered');
      return Object.freeze({ schema_version: 'analytics-b0-skill-resource/v1', package_digest: digest,
        resource, content_digest: manifest.files[resource], content: contents[resource] });
    },
  });
}
