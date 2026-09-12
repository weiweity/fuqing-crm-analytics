import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ensurePersistentRuntime, siblingRuntimes } from './persist-runtime.mjs';

test('ensurePersistentRuntime copies a source harness and keeps the larger credentials file', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-persist-'));
  const source = join(root, 'runtime-N8ZUob');
  const dest = join(root, 'runtime');
  await mkdir(join(source, 'harness/profiles/web'), { recursive: true, mode: 0o700 });
  await writeFile(join(source, 'harness/.credentials.yaml'), 'providers:\n  keep: old-secret-placeholder\n', { mode: 0o600 });
  await writeFile(join(source, 'harness/settings.yaml'), 'locale: zh\n', { mode: 0o600 });
  await writeFile(join(source, 'harness/profiles/web/package.json'), JSON.stringify({
    dependencies: { 'dsh-plugin': `link:${source}/harness/profiles/web/node_modules/dsh-plugin` },
  }), { mode: 0o600 });
  const got = await ensurePersistentRuntime({ dest, sources: [source] });
  assert.equal(got, dest);
  const cred = await readFile(join(dest, 'harness/.credentials.yaml'), 'utf8');
  assert.match(cred, /old-secret-placeholder/);
  const pkg = await readFile(join(dest, 'harness/profiles/web/package.json'), 'utf8');
  assert.match(pkg, new RegExp(dest.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.doesNotMatch(pkg, /runtime-N8ZUob/);
});

test('siblingRuntimes does not pin disposable runtime-* names', async () => {
  assert.deepEqual(siblingRuntimes(), []);
  const source = await readFile(fileURLToPath(new URL('./persist-runtime.mjs', import.meta.url)), 'utf8');
  assert.doesNotMatch(source, /runtime-84Hlmm/);
  assert.doesNotMatch(source, /runtime-N8ZUob/);
});

test('ensurePersistentRuntime does not clobber dest harness or a larger credentials file', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-persist-keep-'));
  const source = join(root, 'runtime-src');
  const dest = join(root, 'runtime');
  await mkdir(join(dest, 'harness/profiles/web'), { recursive: true, mode: 0o700 });
  await writeFile(join(dest, 'harness/profiles/web/package.json'), JSON.stringify({ name: 'dest-keep' }), { mode: 0o600 });
  await writeFile(join(dest, 'harness/.credentials.yaml'), 'providers:\n  keep: dest-secret-placeholder-longer\n', { mode: 0o600 });
  await mkdir(join(source, 'harness/profiles/web/node_modules/dsh-plugin'), { recursive: true, mode: 0o700 });
  await writeFile(join(source, 'harness/profiles/web/package.json'), JSON.stringify({ name: 'src-overwrite' }), { mode: 0o600 });
  await writeFile(join(source, 'harness/.credentials.yaml'), 'x\n', { mode: 0o600 });
  await writeFile(join(source, 'harness/profiles/web/node_modules/dsh-plugin/index.js'), 'export default 1\n', { mode: 0o600 });
  await ensurePersistentRuntime({ dest, sources: [source] });
  const pkg = JSON.parse(await readFile(join(dest, 'harness/profiles/web/package.json'), 'utf8'));
  assert.equal(pkg.name, 'dest-keep');
  const cred = await readFile(join(dest, 'harness/.credentials.yaml'), 'utf8');
  assert.match(cred, /dest-secret-placeholder-longer/);
  const plugin = await readFile(join(dest, 'harness/profiles/web/node_modules/dsh-plugin/index.js'), 'utf8');
  assert.match(plugin, /export default 1/);
});
