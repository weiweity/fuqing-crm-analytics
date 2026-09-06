/** Runtime code roots only; never widen a Seatbelt grant to a home or prefix. */
import assert from 'node:assert/strict';
import { realpathSync } from 'node:fs';
import { dirname, basename, sep } from 'node:path';

export function runtimeCodeRoot(binary) {
  const canonical = realpathSync(binary);
  const marker = `${sep}Cellar${sep}`;
  if (canonical.includes(marker)) return canonical.slice(0, canonical.indexOf(marker) + `${sep}Cellar`.length);
  assert.equal(basename(canonical), 'node', 'Pass the Node executable');
  assert.equal(basename(dirname(canonical)), 'bin', 'Unknown Node distribution layout');
  const root = dirname(dirname(canonical));
  assert.ok(root.split(sep).filter(Boolean).length >= 4, 'Refusing broad runtime read grant; use a versioned Node distribution');
  return root;
}
