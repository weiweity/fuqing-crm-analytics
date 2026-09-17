/** Client slot lifecycle against a fake Cordis surface. Not a native Settings enable/disable run. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const source = await readFile(join(root, 'lib/client.js'), 'utf8');

function loadClient() {
  let factoryRow;
  vm.runInNewContext(source, {
    window: {
      __ModuleLoader__: { load: row => { factoryRow = row; } },
    },
  }, { timeout: 1000 });
  return factoryRow.factory(spec => {
    throw new Error(`unexpected browser require: ${spec}`);
  });
}

function mount(client) {
  const entries = [];
  const effects = [];
  client.apply({
    effect: factory => { effects.push(factory()); },
    slots: {
      inject: (_name, callback) => effects.push(callback()),
      register: (options, component) => {
        entries.push({ options, component });
        return () => {
          const index = entries.findIndex(row => row.options === options);
          if (index >= 0) entries.splice(index, 1);
        };
      },
    },
  });
  return { entries, effects };
}

test('apply registers sidebar.brand.name; dispose removes it', () => {
  const client = loadClient();
  const { entries, effects } = mount(client);
  assert.deepEqual(entries.map(row => row.options.name), ['sidebar.brand.name']);
  assert.equal(entries[0].options.priority, -10);
  for (const dispose of effects) if (typeof dispose === 'function') dispose();
  assert.equal(entries.length, 0);
});

test('client exports inject slots so Cordis does not throw on ctx.slots', () => {
  const client = loadClient();
  assert.equal(JSON.stringify(client.inject), '["slots"]');
});

test('built client factory does not require react', () => {
  assert.equal(source.includes('require('), false);
});
