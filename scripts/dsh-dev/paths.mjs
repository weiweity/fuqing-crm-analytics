/** Resolve repo, upstream, runtime, and plugin paths. Never copy node_modules. */
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { access, mkdir } from 'node:fs/promises';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const repoRoot = resolve(fileURLToPath(new URL('../..', import.meta.url)));

export function resolveUpstream(explicit) {
  const candidates = [
    explicit,
    process.env.DSH_DEV_UPSTREAM,
    join(repoRoot, '.context/dsh-b0/upstream'),
  ].filter(value => typeof value === 'string' && value.length > 0);
  for (const candidate of candidates) {
    const upstream = resolve(candidate);
    assert.ok(isAbsolute(upstream), 'upstream path must be absolute');
    if (existsSync(join(upstream, 'apps/cli/lib/bin.js'))) return upstream;
    if (explicit && upstream === resolve(explicit)) {
      throw new Error(`--upstream is not a built pinned DSH checkout: ${upstream}`);
    }
  }
  throw new Error('pass --upstream /absolute/pinned/dsh or set DSH_DEV_UPSTREAM; do not copy node_modules or the upstream tree');
}

export function defaultPluginPath() {
  return join(repoRoot, 'dsh-plugins/analytics-workbench');
}

export function contextRoot() {
  return join(repoRoot, '.context/dsh-dev');
}

export function currentPath() {
  return join(contextRoot(), 'current.json');
}

export function defaultRuntimeRoot() {
  return join(contextRoot(), 'runtime');
}

export async function ensureDir(path) {
  await mkdir(path, { recursive: true, mode: 0o700 });
  return path;
}

export async function assertCli(upstream) {
  const cli = join(upstream, 'apps/cli/lib/bin.js');
  await access(cli);
  return cli;
}

export { dirname, join, resolve };
