/** Fixed public identity assets for the native dev profile, no business routes. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { constants, open } from 'node:fs/promises';
import { join } from 'node:path';
import { brandAssets } from '../dsh-b0/brand-assets.mjs';
import { BRAND_DIGESTS } from './constants.mjs';
import { repoRoot } from './paths.mjs';

export const name = 'analytics-dev-brand-assets';
export const inject = ['webServer'];

const LFS_PREFIX = 'version https://git-lfs.github.com/spec/v1';

async function readVerifiedAt(abs, type, digest, maxBytes) {
  const file = await open(abs, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const stat = await file.stat();
    assert.ok(stat.isFile() && stat.nlink === 1 && stat.size > 0 && stat.size < maxBytes, `Unexpected asset ${abs}`);
    const bytes = await file.readFile();
    if (bytes.subarray(0, LFS_PREFIX.length).toString('utf8') === LFS_PREFIX) {
      return { status: 'lfs_pointer', type, digest };
    }
    assert.equal(createHash('sha256').update(bytes).digest('hex'), digest, `Asset bytes changed: ${abs}`);
    return { status: 'ok', bytes, type, digest };
  } finally { await file.close(); }
}

async function readVerified(rel, type, digest, maxBytes) {
  return readVerifiedAt(join(repoRoot, rel), type, digest, maxBytes);
}

async function readRegular(rel, type, maxBytes) {
  const file = await open(join(repoRoot, rel), constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const stat = await file.stat();
    assert.ok(stat.isFile() && stat.nlink === 1 && stat.size > 0 && stat.size < maxBytes, `Unexpected asset ${rel}`);
    const bytes = await file.readFile();
    if (bytes.subarray(0, LFS_PREFIX.length).toString('utf8') === LFS_PREFIX) {
      return { status: 'lfs_pointer', type };
    }
    return { status: 'ok', bytes, type };
  } finally { await file.close(); }
}

function registerAsset(ctx, path, asset) {
  if (asset?.status !== 'ok') return;
  ctx.effect(() => ctx.webServer.register({ kind: 'exact', path, handler(req, res) {
    if (req.method !== 'GET' && req.method !== 'HEAD') { res.writeHead(405).end(); return; }
    res.writeHead(200, { 'content-type': asset.type, 'content-length': asset.bytes.length,
      'x-content-type-options': 'nosniff', 'cache-control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : asset.bytes);
  } }));
}

export async function apply(ctx) {
  const assets = await brandAssets(repoRoot);
  const logo = { status: 'ok', ...assets.get('/b0/brand/logo.png') };
  const mark = { status: 'ok', ...assets.get('/favicon.svg') };
  const outfit = await readVerified(
    'frontend-vue3/src/assets/fonts/Outfit-Variable.ttf', 'font/ttf', BRAND_DIGESTS.outfitTtf, 256 * 1024,
  );
  const ofl = await readRegular('frontend-vue3/public/licenses/Outfit-OFL.txt', 'text/plain; charset=utf-8', 16384);
  registerAsset(ctx, '/b0/brand/logo.png', logo);
  registerAsset(ctx, '/b0/brand/mark.svg', mark);
  registerAsset(ctx, '/favicon.svg', mark);
  registerAsset(ctx, '/b0/brand/outfit.ttf', outfit);
  registerAsset(ctx, '/b0/brand/outfit-ofl.txt', ofl);
  ctx.on('webserver/index-inject', table => table.push({ kind: 'style',
    text: [
      'html { color-scheme: dark; }',
      '.analytics-b0-mark { background-image:url("/b0/brand/logo.png"); background-repeat:no-repeat; background-size:auto 100%; background-position:0 50%; }',
      '.analytics-b0-logo { background-image:url("/b0/brand/logo.png"); background-repeat:no-repeat; background-size:contain; width:177px; height:32px; display:inline-block; }',
      '@font-face{font-family:"Outfit";src:url("/b0/brand/outfit.ttf") format("truetype");font-weight:100 900;font-style:normal;font-display:swap;}',
    ].join(''),
  }));
}
