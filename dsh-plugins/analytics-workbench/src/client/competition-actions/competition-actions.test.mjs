import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import {
  AUDIENCE_CONFLICT, AUDIENCE_EMPTY, AUDIENCE_FORBIDDEN, AUDIENCE_PARTIAL, AUDIENCE_SUCCESS,
} from './c0-fixtures.mjs';
import { createFixtureAudienceTransport, decodeActionDraft, decodeCandidateSet } from './transport.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../../../../../');
const fixtures = join(repo, 'docs/hackathon/parallel-competition-2026-09-09/contracts/fixtures');

async function json(rel) {
  return JSON.parse(await readFile(join(fixtures, rel), 'utf8'));
}

test('embedded audience fixtures match frozen C0 JSON', async () => {
  assert.deepEqual(AUDIENCE_SUCCESS, await json('audience/success.json'));
  assert.deepEqual(AUDIENCE_EMPTY, await json('audience/empty.json'));
  assert.deepEqual(AUDIENCE_PARTIAL, await json('audience/partial_success.json'));
  assert.deepEqual(AUDIENCE_CONFLICT, await json('audience/conflict_409.json'));
  assert.deepEqual(AUDIENCE_FORBIDDEN, await json('audience/permission_denied.json'));
});

test('candidate decode requires unique_count to equal deduped keys and auto_send false', () => {
  assert.equal(decodeCandidateSet(AUDIENCE_SUCCESS.candidates).unique_count, 2);
  assert.equal(decodeCandidateSet(AUDIENCE_EMPTY).unique_count, 0);
  assert.equal(decodeCandidateSet({ ...AUDIENCE_SUCCESS.candidates, unique_count: 99 }), null);
  assert.equal(decodeCandidateSet({ ...AUDIENCE_SUCCESS.candidates, auto_send: true }), null);
  assert.equal(decodeCandidateSet({
    ...AUDIENCE_SUCCESS.candidates, customer_keys: ['cust_c0_1', 'cust_c0_1'], unique_count: 2,
  }), null);
  assert.equal(decodeActionDraft(AUDIENCE_SUCCESS.draft).existing_mission_export, 'not-mission-draft-export');
});

test('AND success, OR partial, zero audience, copy-only vs rule expiry, 409', async () => {
  const and = createFixtureAudienceTransport({ scenario: 'success' });
  const andRow = await and.previewCandidates(and.principal, { combine: 'AND' });
  assert.equal(andRow.body.candidates.combine, 'AND');
  assert.equal(andRow.body.candidates.unique_count, 2);
  assert.equal(andRow.body.candidates.auto_send, false);

  const or = createFixtureAudienceTransport({ scenario: 'success' });
  const orRow = await or.previewCandidates(or.principal, { combine: 'OR' });
  assert.equal(orRow.body.partial.status, 'PARTIAL');
  assert.equal(orRow.body.partial.rejected.rule_id, 'rule_f_ge_4');
  assert.equal(orRow.body.candidates.unique_count, 2);

  const empty = createFixtureAudienceTransport({ scenario: 'empty' });
  const zero = await empty.previewCandidates(empty.principal, { combine: 'AND' });
  assert.equal(zero.body.candidates.unique_count, 0);
  assert.equal(zero.body.candidates.customer_keys.length, 0);
  assert.match(zero.body.candidates.limitations[0], /零候选/);

  const threshold = await and.previewCandidates(and.principal, { f_threshold: 4 });
  assert.equal(threshold.ok, false);
  assert.equal(threshold.body.error.param, 'f_threshold');

  const draft = createFixtureAudienceTransport();
  const copy = await draft.saveDraft(draft.principal, { copy_only_change: true, control_design: '文案' });
  assert.equal(copy.body.status, 'DRAFT');
  assert.equal(copy.body.copy_only_change, true);
  assert.equal(copy.body.expired_reason, null);
  const expired = await draft.saveDraft(draft.principal, { rule_changed: true });
  assert.equal(expired.body.status, 'EXPIRED');
  assert.equal(expired.body.expired_reason, 'RULE_CHANGED');
  const review = await draft.saveDraft(draft.principal, { copy_only_change: true, status: 'REVIEW_PENDING' });
  assert.equal(review.body.status, 'REVIEW_PENDING');
  assert.equal(review.body.auto_send, false);

  const conflict = createFixtureAudienceTransport({ scenario: 'conflict_409' });
  assert.equal((await conflict.saveDraft(conflict.principal, { copy_only_change: true })).status, 409);
  const denied = createFixtureAudienceTransport({ scenario: 'permission_denied' });
  assert.equal((await denied.previewCandidates(denied.principal, { combine: 'AND' })).status, 403);
});

test('actions UI source covers AND/OR, zero, explanations, draft expiry and no auto send', async () => {
  const src = await readFile(join(here, 'ActionsWorkbench.tsx'), 'utf8');
  for (const token of [
    'AND', 'OR', 'NON_REPURCHASE', '零人群', '不自动发送', 'EXPIRED', 'REVIEW_PENDING',
    'ThemeProvider', 'LayoutSlot', 'sm-candidate-explanations', 'sm-draft-panel',
  ]) assert.match(src, new RegExp(token));
  const fixturesSrc = await readFile(join(here, 'c0-fixtures.mjs'), 'utf8');
  assert.match(fixturesSrc, /ORIGIN_PRODUCT_ABSENT/);
  assert.match(fixturesSrc, /STOREWIDE_ABSENT/);
  assert.doesNotMatch(src, /from 'antd'|from "antd"/);
  const mount = await readFile(join(here, 'mount.ts'), 'utf8');
  assert.match(mount, /export function mount/);
  assert.match(mount, /dispose/);
});
