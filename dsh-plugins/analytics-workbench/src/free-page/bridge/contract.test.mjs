import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  BINDING_STATES, ERRORS, FORBIDDEN_OPS, HANDSHAKE_FIELDS, HOST_TO_PAGE_EVENTS,
  MAX_CUMULATIVE_ROWS, MAX_RESPONSE_BYTES, PAGE_TO_HOST_OPS, PROTOCOL, SUMMARY_FIELDS, TRANSPORT,
} from './contract.mjs';

const frozen = JSON.parse(readFileSync(join(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../docs/hackathon/free-html-cockpit/fixtures/frozen-contract-v0.json',
), 'utf8'));

test('bridge constants match frozen-contract-v0.json', () => {
  assert.equal(frozen.approved_plan_sha256,
    '47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb');
  assert.equal(frozen.bridge.protocol, PROTOCOL);
  assert.equal(frozen.bridge.transport, TRANSPORT);
  assert.deepEqual(frozen.bridge.handshake, [...HANDSHAKE_FIELDS]);
  assert.deepEqual(frozen.bridge.page_to_host_ops, [...PAGE_TO_HOST_OPS]);
  assert.deepEqual(frozen.bridge.host_to_page_events, [...HOST_TO_PAGE_EVENTS]);
  assert.deepEqual(frozen.bridge.forbidden_ops, [...FORBIDDEN_OPS]);
  assert.deepEqual(frozen.data_read.response_summary_fields, [...SUMMARY_FIELDS]);
  assert.deepEqual(frozen.data_read.budget, {
    max_response_bytes: MAX_RESPONSE_BYTES,
    max_cumulative_rows: MAX_CUMULATIVE_ROWS,
  });
  assert.deepEqual(frozen.asset.binding_states, [...BINDING_STATES]);
  assert.equal(frozen.errors.RESULT_REVOKED, ERRORS.RESULT_REVOKED);
  assert.equal(frozen.errors.BRIDGE_UNKNOWN_OP, ERRORS.BRIDGE_UNKNOWN_OP);
  assert.equal(frozen.errors.BRIDGE_NONCE, ERRORS.BRIDGE_NONCE);
  assert.equal(frozen.asset.page_id, 'page_fixture_unbound');
  assert.equal(frozen.asset.binding_state, 'UNBOUND_SAMPLE');
});
