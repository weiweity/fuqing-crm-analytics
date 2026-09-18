import { fail, isIdentity } from './frozen-contract.mjs';

/**
 * Content-addressed cache. Every get re-checks actor/page/version permission.
 * A hash hit never upgrades the caller to another page's authorization.
 */
export function createResourceCache() {
  const byHash = new Map();
  const grants = new Map();

  function grantKey(actorId, pageId, version, resourceId) {
    return `${actorId}\0${pageId}\0${version}\0${resourceId}`;
  }

  function put({ actorId, pageId, version, resource }) {
    if (!isIdentity(actorId) || !isIdentity(pageId) || !Number.isSafeInteger(version) || version < 1) {
      return fail('INVALID_PAGE', '资源缓存写入缺少 actor/page/version');
    }
    if (!resource || !isIdentity(resource.resource_id) || typeof resource.sha256 !== 'string'
      || !(resource.bytes instanceof Uint8Array)) {
      return fail('INVALID_PAGE', '资源缓存写入缺少内容');
    }
    byHash.set(resource.sha256, {
      sha256: resource.sha256,
      bytes: resource.bytes,
      mime: resource.mime,
      type: resource.type,
      size: resource.size ?? resource.bytes.byteLength,
    });
    grants.set(grantKey(actorId, pageId, version, resource.resource_id), resource.sha256);
    return { ok: true, sha256: resource.sha256 };
  }

  function get({ actorId, pageId, version, resourceId, sha256 }) {
    if (!isIdentity(actorId) || !isIdentity(pageId) || !Number.isSafeInteger(version) || version < 1
      || !isIdentity(resourceId)) {
      return fail('FORBIDDEN', '资源读取未授权');
    }
    const expected = grants.get(grantKey(actorId, pageId, version, resourceId));
    if (!expected) return fail('FORBIDDEN', '当前页面版本未授权该资源');
    if (sha256 && sha256 !== expected) return fail('RESOURCE_HASH_MISMATCH', '请求的资源版本与授权清单不一致');
    const blob = byHash.get(expected);
    if (!blob) return fail('NOT_FOUND', '资源内容不可用');
    return { ok: true, value: { ...blob, resource_id: resourceId, version } };
  }

  function restoreVersion({ actorId, pageId, version, resources }) {
    if (!Array.isArray(resources)) return fail('INVALID_PAGE', '恢复资源清单非法');
    const restored = [];
    for (const item of resources) {
      const written = put({ actorId, pageId, version, resource: item });
      if (!written.ok) return written;
      restored.push(item.resource_id);
    }
    return { ok: true, value: restored };
  }

  return { put, get, restoreVersion, size: () => byHash.size };
}
