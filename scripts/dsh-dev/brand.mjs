/** Fixed public identity assets for the native dev profile, no business routes. */
import { brandAssets } from '../dsh-b0/brand-assets.mjs';
import { repoRoot } from './paths.mjs';
export const name = 'analytics-dev-brand-assets';
export const inject = ['webServer'];
export async function apply(ctx) {
  const assets = await brandAssets(repoRoot);
  for (const [path, asset] of [
    ['/b0/brand/logo.png', assets.get('/b0/brand/logo.png')],
    ['/b0/brand/mark.svg', assets.get('/favicon.svg')],
  ]) {
    ctx.effect(() => ctx.webServer.register({ kind: 'exact', path, handler(req, res) {
      if (req.method !== 'GET' && req.method !== 'HEAD') { res.writeHead(405).end(); return; }
      res.writeHead(200, { 'content-type': asset.type, 'content-length': asset.bytes.length,
        'x-content-type-options': 'nosniff', 'cache-control': 'no-store' });
      res.end(req.method === 'HEAD' ? undefined : asset.bytes);
    } }));
  }
  ctx.on('webserver/index-inject', table => table.push({ kind: 'style',
    text: '.analytics-b0-mark { mask-image:url("/b0/brand/mark.svg"); }',
  }));
}
