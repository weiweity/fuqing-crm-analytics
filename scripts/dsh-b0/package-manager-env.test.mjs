import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { packageManagerEnv } from './package-manager-env.mjs';

test('nested upstream pnpm resolves through project-local Corepack with sanitized PATH', async () => {
  const root = fileURLToPath(new URL('../..', import.meta.url));
  const upstream = join(root, '.context/dsh-b0/upstream');
  const pin = JSON.parse(await readFile(join(root, 'dsh-plugins/analytics-workbench/toolchain.json')));
  const scratch = await mkdtemp(join(tmpdir(), 'b0-pnpm-test-'));
  try {
    const original = { HOME: process.env.HOME, PATH: `${dirname(process.execPath)}:/usr/bin:/bin`,
      COREPACK_ENABLE_NETWORK: '0', COREPACK_ENABLE_DOWNLOAD_PROMPT: '0' };
    const env = await packageManagerEnv(join(scratch, 'bin'), original, upstream);
    assert.equal(original.PATH.startsWith(scratch), false);
    // Real nested shell, as used by upstream build:web; cached fixed manager only.
    const child = spawnSync('/bin/sh', ['-c', 'pnpm --version'], { cwd: upstream, env, encoding: 'utf8', timeout: 30000 });
    assert.equal(child.status, 0, child.stderr);
    assert.equal(child.stdout.trim(), pin.pnpm);
    assert.ok(env.PATH.startsWith(join(scratch, 'bin') + ':'));
  } finally {
    await rm(scratch, { recursive: true, force: true });
  }
});
