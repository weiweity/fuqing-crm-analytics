/** Verify the pinned public DSH checkout. Never fetch, switch, or reset it. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, access } from 'node:fs/promises';
import { join } from 'node:path';
import { PINNED_SHA, NODE_MAJOR } from './constants.mjs';

export async function readToolchain(repoRoot) {
  const pin = JSON.parse(await readFile(join(repoRoot, 'dsh-plugins/analytics-workbench/toolchain.json'), 'utf8'));
  assert.equal(pin.upstream_sha, PINNED_SHA, 'toolchain.json drifted from the fixed upstream SHA');
  assert.equal(pin.node_major, NODE_MAJOR);
  return pin;
}

function git(upstream, args) {
  const result = spawnSync('git', ['-C', upstream, ...args], { encoding: 'utf8', timeout: 15000, maxBuffer: 1024 * 1024 });
  assert.ok(!result.error && result.status === 0, `upstream git failed: ${result.error?.message ?? result.stderr}`);
  return result.stdout.trim();
}

export async function verifyUpstream(upstream, pin) {
  assert.equal(Number(process.versions.node.split('.')[0]), NODE_MAJOR, `Use Node ${NODE_MAJOR}`);
  await access(join(upstream, 'apps/cli/lib/bin.js'));
  await access(join(upstream, 'pnpm-lock.yaml'));
  assert.equal(git(upstream, ['rev-parse', 'HEAD']), pin.upstream_sha, 'Pinned upstream SHA mismatch');
  assert.equal(git(upstream, ['status', '--porcelain', '--untracked-files=no']), '', 'Refusing locally modified upstream');
  const lock = createHash('sha256').update(await readFile(join(upstream, 'pnpm-lock.yaml'))).digest('hex');
  assert.equal(lock, pin.upstream_lock_sha256, 'Pinned upstream lockfile SHA-256 mismatch');
  assert.equal(JSON.parse(await readFile(join(upstream, 'package.json'), 'utf8')).packageManager, `pnpm@${pin.pnpm}`);
  return {
    upstream_sha: pin.upstream_sha,
    upstream_lock_sha256: pin.upstream_lock_sha256,
    pnpm: pin.pnpm,
    node: process.version,
  };
}
