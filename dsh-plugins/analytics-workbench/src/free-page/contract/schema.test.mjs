import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import fixture from './fixture.json' with { type: 'json' };
import {
  parsePageDocument, parsePagePackage, parseBridgeMessage, parseBindingManifest,
  FORBIDDEN_BRIDGE_OPS, PAGE_OPERATIONS, BINDING_STATE_VALUES,
} from './schema.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const frozen = JSON.parse(readFileSync(join(here,
  '../../../../../docs/hackathon/free-html-cockpit/fixtures/frozen-contract-v0.json'), 'utf8'));

const sampleDoc = {
  schema_version: 'free-page/v1',
  page_id: frozen.asset.page_id,
  session_id: frozen.asset.session_id,
  title: frozen.asset.title,
  version: 1,
  binding_state: 'UNBOUND_SAMPLE',
  package: fixture.package,
  binding_manifest: fixture.binding_manifest,
};

test('published fixture matches coordinator freeze on shared fields', () => {
  assert.equal(fixture.schema_version, frozen.asset.schema_version);
  assert.deepEqual(fixture.binding_states, frozen.asset.binding_states);
  assert.deepEqual(fixture.operations, frozen.operations);
  assert.deepEqual(fixture.package, frozen.asset.package);
  assert.equal(fixture.errors.INVALID_PAGE, 422);
  assert.equal(fixture.errors.INVALID_BOARD, undefined);
  assert.deepEqual(PAGE_OPERATIONS, ['GENERATE', 'PATCH', 'SAVE', 'ROLLBACK']);
  assert.deepEqual(BINDING_STATE_VALUES, ['UNBOUND_SAMPLE', 'BOUND_VERIFIED', 'BOUND_STALE']);
});

test('parsePageDocument accepts the unbound sample and free JS', () => {
  const got = parsePageDocument(sampleDoc);
  assert.equal(got.ok, true);
  assert.equal(got.value.package.js.includes('getContext'), true);
  const custom = parsePageDocument({
    ...sampleDoc,
    package: { ...fixture.package, html: '<html><body><script>window.x=1</script></body></html>', js: 'window.x=1' },
  });
  assert.equal(custom.ok, true);
});

test('parsePageDocument rejects BoardSpec fields, unknown keys and empty html', () => {
  assert.equal(parsePageDocument({ ...sampleDoc, blocks: [] }).error.code, 'INVALID_PAGE');
  assert.equal(parsePageDocument({ ...sampleDoc, board_id: 'board_x' }).error.code, 'INVALID_PAGE');
  assert.equal(parsePageDocument({ ...sampleDoc, owner: 'alice' }).error.code, 'INVALID_PAGE');
  assert.equal(parsePageDocument({ ...sampleDoc, binding_state: 'BOUND_SAMPLE' }).error.code, 'INVALID_PAGE');
  assert.equal(parsePagePackage({ ...fixture.package, html: '' }).error.code, 'INVALID_PAGE');
  assert.equal(parseBindingManifest({ bindings: [{ binding_id: 'b1', result_ref: 'missing' }], result_refs: [] }).ok, false);
  assert.equal(parseBindingManifest({
    result_refs: ['result_fixture_1'],
    bindings: [{ binding_id: 'b1', result_ref: 'result_fixture_1', mode: 'sql' }],
  }).error.code, 'INVALID_PAGE');
  assert.equal(parsePagePackage({
    ...fixture.package,
    resources: [{ resource_id: 'blob_1', content_type: 'image/png', sha256: 'zz', byte_length: 1 }],
  }).error.code, 'INVALID_PAGE');
  assert.equal(parsePageDocument({ ...sampleDoc, binding_state: 'BOUND_VERIFIED' }).error.code, 'INVALID_PAGE');
});

test('parseBridgeMessage covers unknown op, nonce, expiry and budget', () => {
  const session = { instance_id: 'inst_1', nonce: 'nonce_1' };
  const read = {
    protocol: 'free-page-bridge/v1', instance_id: 'inst_1', request_id: 'req_1',
    nonce: 'nonce_1', seq: 0, ...fixture.data_read,
  };
  assert.equal(parseBridgeMessage(read, session).ok, true);
  assert.equal(parseBridgeMessage({ ...read, op: 'sql' }, session).error.code, 'BRIDGE_UNKNOWN_OP');
  assert.equal(parseBridgeMessage({ ...read, op: 'save' }, session).error.code, 'BRIDGE_UNKNOWN_OP');
  assert.equal(parseBridgeMessage({ ...read, nonce: 'other' }, session).error.code, 'BRIDGE_NONCE');
  assert.equal(parseBridgeMessage(read, { ...session, expired: true }).error.code, 'BRIDGE_EXPIRED_INSTANCE');
  assert.equal(parseBridgeMessage({
    protocol: 'free-page-bridge/v1', instance_id: 'inst_1', request_id: 'req_1',
    nonce: 'nonce_1', seq: 0, op: 'data.chunk', byte_length: 65537,
  }, session).error.code, 'PACKAGE_TOO_LARGE');
  assert.equal(parseBridgeMessage({ ...read, owner: 'alice' }, session).error.code, 'INVALID_PAGE');
  assert.equal(parseBridgeMessage({ ...read, mode: 'sql' }, session).error.code, 'INVALID_PAGE');
  for (const op of FORBIDDEN_BRIDGE_OPS) {
    assert.equal(parseBridgeMessage({ ...read, op }, session).error.code, 'BRIDGE_UNKNOWN_OP');
  }
});
