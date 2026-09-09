import { DEFAULT_PRINCIPAL } from '../competition-board/c0-fixtures.mjs';
import { decodeCompetitionError } from '../competition-board/decode.mjs';
import {
  AUDIENCE_CONFLICT, AUDIENCE_EMPTY, AUDIENCE_FORBIDDEN, AUDIENCE_PARAM_ERROR,
  AUDIENCE_PARTIAL, AUDIENCE_SUCCESS,
} from './c0-fixtures.mjs';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}
function ok(status, body) { return { ok: true, status, body }; }
function fail(status, body) { return { ok: false, status, body }; }

const OPAQUE = /^[A-Za-z0-9_.:-]{1,128}$/;

export function decodeCandidateSet(value) {
  if (!value || value.schema_version !== 'competition-audience/v1') return null;
  if (!OPAQUE.test(value.candidate_set_id) || !OPAQUE.test(value.cohort_id)) return null;
  if (value.combine !== 'AND' && value.combine !== 'OR') return null;
  if (value.auto_send !== false) return null;
  if (!Array.isArray(value.customer_keys) || !Array.isArray(value.explanations)) return null;
  if (typeof value.unique_count !== 'number' || value.unique_count !== value.customer_keys.length) return null;
  const unique = new Set(value.customer_keys);
  if (unique.size !== value.customer_keys.length) return null;
  return value;
}

export function decodeActionDraft(value) {
  if (!value || value.schema_version !== 'competition-action/v1') return null;
  if (value.auto_send !== false) return null;
  if (value.existing_mission_export !== 'not-mission-draft-export') return null;
  if (value.currency !== 'CNY') return null;
  if (!['DRAFT', 'REVIEW_PENDING', 'EXPIRED', 'SUPERSEDED'].includes(value.status)) return null;
  if (value.expired_reason != null && value.expired_reason !== 'RULE_CHANGED' && value.expired_reason !== 'SOURCE_CHANGED') return null;
  return value;
}

export function createFixtureAudienceTransport(options = {}) {
  let scenario = options.scenario ?? 'success';
  let combine = 'AND';
  let draft = clone(AUDIENCE_SUCCESS.draft);
  let candidates = clone(AUDIENCE_SUCCESS.candidates);
  const cohort = clone(AUDIENCE_SUCCESS.cohort);

  return {
    kind: 'fixture',
    principal: options.principal ?? DEFAULT_PRINCIPAL,
    setScenario(next) { scenario = next; },
    getScenario() { return scenario; },

    async previewCandidates(_principal, payload = {}) {
      if (scenario === 'permission_denied') return fail(403, clone(AUDIENCE_FORBIDDEN));
      combine = payload.combine === 'OR' ? 'OR' : 'AND';
      if (payload.f_threshold != null) return fail(422, clone(AUDIENCE_PARTIAL.rejected));
      if (scenario === 'param_error' || payload.unique_count === 99) {
        return fail(422, {
          error: {
            code: AUDIENCE_PARAM_ERROR.expected.code,
            doc_ref: 'docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T12',
            http_status: 422,
            maps_to: 'backend.contracts.analytics.AnalyticsErrorDetail',
            message: 'unique_count 必须等于去重后的 customer_keys 长度。',
            param: AUDIENCE_PARAM_ERROR.expected.param,
            recovery_url: null,
            request_id: 'req_c0_422_unique',
            retry_after: null,
            retryable: false,
            schema_version: 'competition-error/v1',
          },
        });
      }
      if (scenario === 'empty' || payload.force_empty) {
        candidates = clone(AUDIENCE_EMPTY);
        candidates.combine = combine;
        return ok(200, { candidates, cohort, partial: null });
      }
      if (scenario === 'partial_success' || combine === 'OR') {
        const accepted = clone(AUDIENCE_PARTIAL.accepted);
        accepted.combine = 'OR';
        candidates = accepted;
        return ok(200, { candidates: accepted, cohort, partial: clone(AUDIENCE_PARTIAL) });
      }
      candidates = clone(AUDIENCE_SUCCESS.candidates);
      candidates.combine = combine;
      return ok(200, { candidates, cohort, partial: null });
    },

    async saveDraft(_principal, payload = {}) {
      if (scenario === 'conflict_409') return fail(409, clone(AUDIENCE_CONFLICT));
      if (scenario === 'permission_denied') return fail(403, clone(AUDIENCE_FORBIDDEN));
      const next = clone(draft);
      if (payload.copy_only_change) {
        next.copy_only_change = true;
        next.control_design = payload.control_design ?? next.control_design;
        next.stop_condition = payload.stop_condition ?? next.stop_condition;
        next.expired_reason = null;
        next.status = 'DRAFT';
      } else if (payload.rule_changed || payload.source_changed) {
        next.copy_only_change = false;
        next.status = 'EXPIRED';
        next.expired_reason = payload.rule_changed ? 'RULE_CHANGED' : 'SOURCE_CHANGED';
      }
      if (payload.reviewer_id) next.reviewer_id = payload.reviewer_id;
      if (payload.review_by) next.review_by = payload.review_by;
      if (payload.status === 'REVIEW_PENDING') next.status = 'REVIEW_PENDING';
      next.version += 1;
      next.auto_send = false;
      draft = next;
      return ok(200, next);
    },

    async loadDraft() {
      if (scenario === 'permission_denied') return fail(403, clone(AUDIENCE_FORBIDDEN));
      return ok(200, { candidates, cohort, draft });
    },
  };
}

export function wrapAudiencePreviewPayload(payload = {}) {
  if (payload && typeof payload === 'object' && payload.cohort) return payload;
  const kinds = Array.isArray(payload.rules) && payload.rules.length
    ? payload.rules.filter(item => typeof item === 'string')
    : ['ORIGIN_CHANNEL_ABSENT'];
  const rules = kinds.map((kind, index) => ({
    rule_id: `rule_${String(kind).toLowerCase()}_${index}`,
    kind: 'NON_REPURCHASE',
    non_repurchase: kind,
    member_mark: 'UNKNOWN',
    f_threshold: null,
    f_grain_status: 'UNKNOWN',
    channel_ids: [],
    product_ids: [],
  }));
  return {
    cohort: {
      cohort_id: 'cohort_t05_ly_f4_10',
      enrollment_window: { start_date: '2025-01-01', end_date: '2025-12-31' },
      observation_window: { start_date: '2026-08-01', end_date: '2026-08-31' },
      enrollment_rule_version: 'competition-cohort-rule/v1',
      as_of: '2025-12-31T16:00:00.000000+00:00',
      published_at: '2026-08-31T16:00:00.000000+00:00',
      source_tense: 'PUBLISHED_SNAPSHOT',
      member_history_status: 'UNKNOWN',
      existing_family: 'none',
      rules,
      permission_scope: 'scope-brand-a',
      limitations: ['合成 customer_key，不导出真实名单；auto_send 恒为 false。'],
    },
    combine: payload.combine === 'OR' ? 'OR' : 'AND',
    source_result_ref: payload.source_result_ref || 'result_t05_gsv_20260831',
    permission_scope: payload.permission_scope || 'scope-brand-a',
    auto_send: false,
    candidate_set_id: payload.candidate_set_id,
  };
}

export function createHttpAudienceTransport({ fetchImpl, basePath = '/api/v1/analytics/competition' } = {}) {
  if (typeof fetchImpl !== 'function') {
    throw new Error('HTTP audience transport 需要注入 fetchImpl；默认 UI 使用 C0 fixture transport。');
  }
  let lastCandidateSetId = null;
  let lastDraftId = null;
  async function request(path, { method = 'GET', body } = {}) {
    const headers = {};
    if (body !== undefined) headers['content-type'] = 'application/json';
    const response = await fetchImpl(path, {
      method, credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let payload = null;
    try { payload = await response.json(); } catch { payload = null; }
    const error = decodeCompetitionError(payload);
    if (error) return fail(response.status, { error });
    return { ok: response.status >= 200 && response.status < 300, status: response.status, body: payload };
  }
  return {
    kind: 'http',
    async previewCandidates(_p, payload) {
      const body = wrapAudiencePreviewPayload(payload || {});
      const row = await request(`${basePath}/candidates/preview`, { method: 'POST', body });
      if (row.ok) lastCandidateSetId = row.body?.candidates?.candidate_set_id || lastCandidateSetId;
      return row;
    },
    async saveDraft(_p, payload = {}) {
      const body = {
        auto_send: false,
        permission_scope: payload.permission_scope || 'scope-brand-a',
        candidate_set_id: payload.candidate_set_id || lastCandidateSetId,
        draft_id: payload.draft_id || lastDraftId,
        copy_only_change: payload.copy_only_change === true,
        control_design: payload.control_design,
        stop_condition: payload.stop_condition,
        reviewer_id: payload.reviewer_id,
        review_by: payload.review_by,
        status: payload.status,
        owner_id: payload.owner_id,
      };
      const row = await request(`${basePath}/drafts`, { method: 'POST', body });
      if (row.ok) lastDraftId = row.body?.draft_id || lastDraftId;
      return row;
    },
    async loadDraft() { return request(`${basePath}/drafts/current`); },
  };
}

export function createAudienceTransport(options = {}) {
  if (options.http) return createHttpAudienceTransport(options.http);
  return createFixtureAudienceTransport(options);
}
