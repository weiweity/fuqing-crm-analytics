/** Fixed original brand bytes only. No filesystem path comes from HTTP input. */
import assert from 'node:assert/strict';
import { open, constants } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join } from 'node:path';

export async function brandAssets(root) {
  const entries = [
    ['/b0/brand/logo.png', 'frontend-vue3/src/assets/brand/shine-mage.png', 'image/png',
      '21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000'],
    ['/favicon.svg', 'frontend-vue3/public/shine-mage-mark.svg', 'image/svg+xml',
      '1bcd095360e42081429d23972e25f8d4a831a241df565d920c020d27aab8f4a8'],
  ];
  const result = new Map();
  for (const [url, path, type, digest] of entries) {
    const file = await open(join(root, path), constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      const stat = await file.stat();
      assert.ok(stat.isFile() && stat.nlink === 1 && stat.size > 0 && stat.size < 16384, 'Unexpected brand asset');
      const bytes = await file.readFile();
      assert.equal(createHash('sha256').update(bytes).digest('hex'), digest, 'Original brand bytes changed');
      result.set(url, { bytes, type, digest });
    } finally { await file.close(); }
  }
  return result;
}
