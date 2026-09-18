import test from 'node:test';
import assert from 'node:assert/strict';
import { createResourceCache } from './resource-cache.mjs';
import { sha256Hex, utf8Bytes } from './bytes.mjs';

test('hash hit still requires matching actor/page/version; old version stays pinned', async () => {
  const cache = createResourceCache();
  const bytes = utf8Bytes('shared-bytes');
  const digest = await sha256Hex(bytes);
  const resource = {
    resource_id: 'logo_1', type: 'image', sha256: digest, bytes, mime: 'image/png', size: bytes.byteLength,
  };
  assert.equal(cache.put({ actorId: 'actor_a', pageId: 'page_one', version: 1, resource }).ok, true);
  assert.equal(cache.put({ actorId: 'actor_b', pageId: 'page_two', version: 1, resource }).ok, true);

  const allowed = cache.get({ actorId: 'actor_a', pageId: 'page_one', version: 1, resourceId: 'logo_1', sha256: digest });
  assert.equal(allowed.ok, true);
  assert.equal(allowed.value.sha256, digest);

  const cross = cache.get({ actorId: 'actor_b', pageId: 'page_one', version: 1, resourceId: 'logo_1', sha256: digest });
  assert.equal(cross.ok, false);
  assert.equal(cross.error.code, 'FORBIDDEN');

  const v2 = cache.get({ actorId: 'actor_a', pageId: 'page_one', version: 2, resourceId: 'logo_1', sha256: digest });
  assert.equal(v2.ok, false);
  assert.equal(v2.error.code, 'FORBIDDEN');

  const wrongHash = cache.get({
    actorId: 'actor_a', pageId: 'page_one', version: 1, resourceId: 'logo_1', sha256: 'ab'.repeat(32),
  });
  assert.equal(wrongHash.ok, false);
  assert.equal(wrongHash.error.code, 'RESOURCE_HASH_MISMATCH');

  const restored = cache.restoreVersion({
    actorId: 'actor_a', pageId: 'page_one', version: 3, resources: [resource],
  });
  assert.equal(restored.ok, true);
  assert.equal(cache.get({ actorId: 'actor_a', pageId: 'page_one', version: 3, resourceId: 'logo_1' }).ok, true);
  assert.equal(cache.get({ actorId: 'actor_a', pageId: 'page_one', version: 1, resourceId: 'logo_1' }).ok, true);
});
