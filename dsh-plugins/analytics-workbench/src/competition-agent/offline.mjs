/** Offline eval via the Python adapter. Never binds 4327/8000/5173. */

import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const plugin = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const repo = resolve(plugin, '../..');

export function repoRoot() {
  return repo;
}

export function runOfflineEval() {
  const result = spawnSync(process.env.PYTHON || 'python3', [
    '-m', 'backend.services.analytics.competition_diagnosis.eval',
  ], {
    cwd: repo,
    encoding: 'utf8',
    env: {
      PATH: process.env.PATH,
      PYTHONPATH: repo,
      PYTHONNOUSERSITE: '1',
      PYTHONDONTWRITEBYTECODE: '1',
    },
  });
  if (result.status !== 0) {
    throw new Error(`offline eval failed: ${result.status}\n${result.stdout}\n${result.stderr}`);
  }
  return JSON.parse(result.stdout);
}
