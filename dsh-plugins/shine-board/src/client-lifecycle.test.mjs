import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { resolve, join } from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const repo = resolve(root, '../..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(repo, '.context/dsh-b0/upstream'));
const webRequire = createRequire(join(upstream, 'apps/web/package.json'));
const source = await readFile(join(root, 'lib/client.js'), 'utf8');

function loadClient() {
  const seed = new Map([
    ['react', webRequire('react')],
    ['react/jsx-runtime', webRequire('react/jsx-runtime')],
  ]);
  let factoryRow;
  const sandbox = {
    window: { __ModuleLoader__: { load: row => { factoryRow = row; } } },
  };
  sandbox.globalThis = sandbox;
  vm.runInNewContext(source, sandbox, { timeout: 1000 });
  const client = factoryRow.factory(spec => {
    assert.ok(seed.has(spec), `unexpected browser require: ${spec}`);
    return seed.get(spec);
  });
  return { client, sandbox };
}

test('apply marks the board pack present', () => {
  const { client, sandbox } = loadClient();
  client.apply({});
  assert.equal(sandbox.__SHINE_BOARD__, true);
});
