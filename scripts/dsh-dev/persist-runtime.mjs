/** Durable dsh-dev home. --fresh must not be the daily reload path. */
import { cp, mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { defaultRuntimeRoot } from './paths.mjs';

const EXTRA_PLUGINS = Object.freeze(['dsh-plugin', '@xmanrui/dsh-im']);

export function siblingRuntimes() {
  return [];
}

async function fileSize(path) {
  try {
    return (await stat(path)).size;
  } catch {
    return 0;
  }
}

async function copyIfMissing(from, to) {
  if (!from || await fileSize(from) <= 0) return false;
  if (await fileSize(to) > 0) return false;
  await mkdir(dirname(to), { recursive: true, mode: 0o700 });
  await cp(from, to, { recursive: true, force: false });
  return true;
}

async function preferLarger(from, to) {
  const src = await fileSize(from);
  const dst = await fileSize(to);
  if (src <= dst) return false;
  await mkdir(dirname(to), { recursive: true, mode: 0o700 });
  await cp(from, to, { recursive: true, force: true });
  return true;
}

function rewriteRuntimeLinks(text, dest) {
  return String(text).replace(
    /link:[^"\s]+\/harness\/profiles\/web\/node_modules\//g,
    `link:${join(dest, 'harness/profiles/web/node_modules')}/`,
  );
}

export async function ensurePersistentRuntime({ dest = defaultRuntimeRoot(), sources = siblingRuntimes() } = {}) {
  await mkdir(dest, { recursive: true, mode: 0o700 });
  const destPkg = join(dest, 'harness/profiles/web/package.json');
  if (await fileSize(destPkg) <= 0) {
    for (const source of sources) {
      const pkg = join(source, 'harness/profiles/web/package.json');
      if (await fileSize(pkg) > 0) {
        await cp(join(source, 'harness'), join(dest, 'harness'), { recursive: true, force: false });
        const overlay = join(source, 'plugin.patch.yml');
        if (await fileSize(overlay) > 0) await cp(overlay, join(dest, 'plugin.patch.yml'), { force: false });
        break;
      }
    }
  }
  for (const source of sources) {
    await preferLarger(join(source, 'harness/.credentials.yaml'), join(dest, 'harness/.credentials.yaml'));
    await preferLarger(join(source, 'harness/settings.yaml'), join(dest, 'harness/settings.yaml'));
    const webMods = join(source, 'harness/profiles/web/node_modules');
    for (const name of EXTRA_PLUGINS) {
      await copyIfMissing(join(webMods, name), join(dest, 'harness/profiles/web/node_modules', name));
    }
  }
  if (await fileSize(destPkg) > 0) {
    const next = rewriteRuntimeLinks(await readFile(destPkg, 'utf8'), dest);
    await writeFile(destPkg, next, { mode: 0o600 });
  }
  return dest;
}
