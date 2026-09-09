/** Replaceable board transport. Fixture is the default until A5 HTTP is wired. */

import {
  BOARD_CONFLICT, BOARD_EMPTY, BOARD_FORBIDDEN, BOARD_PARTIAL, BOARD_SUCCESS,
  DEFAULT_PRINCIPAL, RESULT_EMPTY, RESULT_FORBIDDEN, RESULT_SUCCESS,
} from './c0-fixtures.mjs';
import {
  canEndorse, decodeCompetitionBatchReceipt, decodeCompetitionBatchRequest,
  decodeCompetitionBoardSpec, decodeCompetitionError, decodeCompetitionPatchRequest,
  decodeCompetitionResultRef, looksLikeIllegalScript, toEndorsedResultRef,
  defaultBlockLayout,
  decodeBoardPatchRequest,
} from './decode.mjs';

export function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function ok(status, body) {
  return { ok: true, status, body };
}

function fail(status, body) {
  return { ok: false, status, body };
}

function fingerprint(payload) {
  const text = JSON.stringify(payload);
  let hash = 0xc0ffee;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 33 + text.charCodeAt(i)) >>> 0;
  return hash.toString(16).padStart(64, 'a').slice(0, 64);
}

export function createFixtureBoardTransport(options = {}) {
  let scenario = options.scenario ?? 'success';
  let board = clone(scenario === 'empty' ? BOARD_EMPTY : BOARD_SUCCESS.board);
  let preview = null;
  let pendingPatch = null;
  let applyCount = 0;
  const idempotency = new Map();
  const results = (options.results ?? [RESULT_SUCCESS, RESULT_EMPTY]).map(clone);
  function bindFixture(spec, refs = BOARD_SUCCESS.batch.operations[0].endorsed_result_refs) {
    spec.blocks = spec.block_ids.map((block_id, index) => {
      const ref = refs[index % refs.length];
      return { block_id, result_id: ref?.result_id,
        result: results.find(row => row.result_id === ref?.result_id),
        layout: defaultBlockLayout(index), plugin: index === 1 ? 'BAR' : 'TABLE',
        display_overrides: {}, source_status: 'OK' };
    });
    return spec;
  }
  bindFixture(board);

  const api = {
    kind: 'fixture',
    principal: options.principal ?? DEFAULT_PRINCIPAL,
    setScenario(next) { scenario = next; },
    getScenario() { return scenario; },
    getBoard() { return preview ?? board; },
    getSavedBoard() { return board; },
    getPendingPatch() { return pendingPatch; },
    getApplyCount() { return applyCount; },

    async listEndorseableResults() {
      if (scenario === 'result_forbidden') return fail(403, clone(RESULT_FORBIDDEN));
      return ok(200, results.map(decodeCompetitionResultRef));
    },

    async previewBatch(_principal, payload) {
      const decoded = decodeCompetitionBatchRequest(payload);
      if (!decoded) {
        return fail(422, {
          error: {
            code: 'INVALID_REQUEST',
            doc_ref: 'docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T09',
            http_status: 422,
            maps_to: 'backend.contracts.analytics.AnalyticsErrorDetail',
            message: '批量成板请求未通过 C0 BoardBatch 校验。',
            param: 'operations',
            recovery_url: null,
            request_id: 'req_c0_422_batch',
            retry_after: null,
            retryable: false,
            schema_version: 'competition-error/v1',
          },
        });
      }
      if (scenario === 'permission_denied') return fail(403, clone(BOARD_FORBIDDEN));
      if (scenario === 'partial_success') return ok(200, { board: clone(board), receipt: clone(BOARD_PARTIAL) });
      const next = clone(BOARD_SUCCESS.board);
      next.preview = true;
      next.persisted = false;
      next.layout_mode = decoded.layout_mode;
      next.batch_id = decoded.batch_id;
      next.operation_id = decoded.operations[0].operation_id;
      next.title = decoded.operations[0].title;
      bindFixture(next, decoded.operations[0].endorsed_result_refs);
      preview = next;
      return ok(200, { board: next, receipt: null });
    },

    async applyBatch(_principal, payload, headers = {}) {
      applyCount += 1;
      const decoded = decodeCompetitionBatchRequest(payload);
      if (!decoded) return fail(422, { error: { ...BOARD_CONFLICT.error, code: 'INVALID_REQUEST', http_status: 422 } });
      const key = headers['Idempotency-Key'] ?? headers['idempotency-key'] ?? decoded.operations[0].idempotency_key;
      const prior = idempotency.get(key);
      if (prior && prior.fingerprint !== fingerprint(payload)) return fail(409, clone(BOARD_CONFLICT));
      if (prior) return ok(200, prior.response);
      if (scenario === 'fail_once') {
        scenario = 'success';
        return fail(500, {
          error: {
            ...BOARD_CONFLICT.error,
            code: 'INTERNAL',
            http_status: 500,
            message: 'synthetic fail-once',
            retryable: true,
            request_id: 'req_c0_fail_once',
          },
        });
      }
      if (scenario === 'permission_denied') return fail(403, clone(BOARD_FORBIDDEN));
      if (scenario === 'partial_success') {
        const receipt = clone(BOARD_PARTIAL);
        idempotency.set(key, { fingerprint: fingerprint(payload), response: { board, receipt } });
        return ok(200, { board, receipt });
      }
      const next = clone(BOARD_SUCCESS.board);
      next.preview = false;
      next.persisted = true;
      next.layout_mode = decoded.layout_mode;
      next.batch_id = decoded.batch_id;
      next.operation_id = decoded.operations[0].operation_id;
      next.title = decoded.operations[0].title;
      bindFixture(next, decoded.operations[0].endorsed_result_refs);
      next.version = board.version + 1;
      next.base_version = board.version;
      board = next;
      preview = null;
      const receipt = {
        batch_id: decoded.batch_id,
        items: decoded.operations.map(op => ({
          board_id: next.board_id,
          error_code: null,
          operation_id: op.operation_id,
          retryable: false,
          status: 'SUCCEEDED',
          version: next.version,
        })),
        schema_version: 'competition-board-batch/v1',
        status: 'SUCCEEDED',
      };
      const response = { board: next, receipt };
      idempotency.set(key, { fingerprint: fingerprint(payload), response });
      return ok(201, response);
    },

    async previewPatch(_principal, payload) {
      if (looksLikeIllegalScript(payload)) {
        return fail(422, {
          error: {
            code: 'INVALID_REQUEST',
            doc_ref: 'docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T10',
            http_status: 422,
            maps_to: 'backend.contracts.analytics.AnalyticsErrorDetail',
            message: '拒绝任意 HTML/JS 或越权路径补丁。',
            param: 'intent',
            recovery_url: null,
            request_id: 'req_c0_422_patch',
            retry_after: null,
            retryable: false,
            schema_version: 'competition-error/v1',
          },
        });
      }
      const decoded = decodeBoardPatchRequest(payload);
      if (!decoded) return fail(422, { error: { ...BOARD_CONFLICT.error, code: 'INVALID_REQUEST', http_status: 422, param: 'intent' } });
      if (decoded.intent === 'FILTER_CHANGE') {
        return fail(422, {
          error: {
            code: 'NOT_CONNECTED',
            doc_ref: 'docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T10',
            http_status: 422,
            maps_to: 'backend.contracts.analytics.AnalyticsErrorDetail',
            message: '筛选改动会生成新分析。当前 cockpit HTTP 未接通 FILTER_CHANGE。',
            param: 'filter_change',
            recovery_url: null,
            request_id: 'req_c0_422_filter',
            retry_after: null,
            retryable: false,
            schema_version: 'competition-error/v1',
          },
        });
      }
      if (scenario === 'permission_denied') return fail(403, clone(BOARD_FORBIDDEN));
      const next = clone(board);
      next.preview = true;
      next.persisted = false;
      next.base_version = board.version;
      next.affected_block_ids = decoded.block_id ? [decoded.block_id] : next.block_ids;
      if (decoded.display_op?.display_overrides?.title && decoded.block_id) {
        next.title = board.title;
        const block = next.blocks?.find(row => row.block_id === decoded.block_id);
        if (block) block.display_overrides = clone(decoded.display_op.display_overrides);
      }
      if (decoded.cockpit_op?.op === 'layout') {
        const block = next.blocks?.find(row => row.block_id === decoded.cockpit_op.card_id);
        if (block) block.layout = clone(decoded.cockpit_op.layout);
      }
      if (decoded.schema_version === 'competition-board-chart-patch/v1') {
        const block = next.blocks?.find(row => row.block_id === decoded.block_id);
        if (!block) return fail(422, { error: { ...BOARD_CONFLICT.error, code: 'INVALID_REQUEST', http_status: 422 } });
        block.plugin = decoded.chart_type;
      }
      preview = next;
      pendingPatch = decoded;
      return ok(200, next);
    },

    async applyPatch(_principal, payload, headers = {}) {
      const decoded = decodeBoardPatchRequest(payload);
      if (!decoded) return fail(422, { error: { ...BOARD_CONFLICT.error, code: 'INVALID_REQUEST', http_status: 422 } });
      if (scenario === 'conflict_409' || Number(headers['If-Match'] ?? headers['if-match']) !== board.version) {
        return fail(409, clone(BOARD_CONFLICT));
      }
      if (scenario === 'permission_denied') return fail(403, clone(BOARD_FORBIDDEN));
      const next = clone(preview ?? board);
      next.preview = false;
      next.persisted = true;
      next.version = board.version + 1;
      next.base_version = board.version;
      board = next;
      preview = null;
      pendingPatch = null;
      return ok(201, next);
    },

    async undo(_principal, payload, headers = {}) {
      const restore = payload?.cockpit_op?.restore_from_version;
      if (!restore || restore >= board.version) {
        return fail(422, {
          error: {
            code: 'INVALID_REQUEST',
            doc_ref: 'docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T11',
            http_status: 422,
            maps_to: 'backend.contracts.analytics.AnalyticsErrorDetail',
            message: '没有可恢复的历史版本。',
            param: 'restore_from_version',
            recovery_url: null,
            request_id: 'req_c0_422_undo',
            retry_after: null,
            retryable: false,
            schema_version: 'competition-error/v1',
          },
        });
      }
      return api.previewPatch(_principal, payload, headers);
    },

    async loadBoard(boardId) {
      if (scenario === 'permission_denied') return fail(403, clone(BOARD_FORBIDDEN));
      if (boardId && boardId !== board.board_id) return fail(403, clone(BOARD_FORBIDDEN));
      return ok(200, clone(board));
    },

    discardPreview() {
      preview = null;
      pendingPatch = null;
    },
  };
  return api;
}

export function createHttpBoardTransport({ fetchImpl, basePath = '/api/v1/analytics/competition' } = {}) {
  if (typeof fetchImpl !== 'function') {
    throw new Error('HTTP transport 需要注入 fetchImpl；默认 UI 使用 C0 fixture transport。');
  }
  async function request(path, { method = 'GET', body, etag, key } = {}) {
    const headers = {};
    if (body !== undefined) headers['content-type'] = 'application/json';
    if (key) headers['idempotency-key'] = key;
    if (etag !== undefined && etag !== null) headers['if-match'] = String(etag);
    const response = await fetchImpl(path, {
      method, credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let payload = null;
    try { payload = await response.json(); } catch { payload = null; }
    const error = decodeCompetitionError(payload);
    if (error) return fail(response.status, { error });
    const bodyValue = payload?.spec?.schema_version === 'competition-board/v1'
      ? { ...payload.spec, blocks: Array.isArray(payload.blocks) ? payload.blocks : [] }
      : payload;
    return { ok: response.status >= 200 && response.status < 300, status: response.status, body: bodyValue };
  }
  return {
    kind: 'http',
    async listEndorseableResults() {
      const row = await request(`${basePath}/results`);
      if (!row.ok) return row;
      const items = Array.isArray(row.body) ? row.body : (row.body?.items || []);
      return { ...row, body: items };
    },
    async previewBatch(_p, payload) {
      return decodeCompetitionBatchRequest(payload) ? ok(200, { board: null, receipt: null })
        : fail(422, { error: { ...BOARD_CONFLICT.error, code: 'INVALID_REQUEST', http_status: 422 } });
    },
    async applyBatch(_p, payload, headers = {}) {
      return request(`${basePath}/batches`, {
        method: 'POST', body: payload, key: headers['Idempotency-Key'] ?? headers['idempotency-key'],
      });
    },
    async previewPatch(_p, payload, headers = {}) {
      return request(`${basePath}/boards/${payload.board_id}/preview`, {
        method: 'POST', body: payload, etag: headers['If-Match'] ?? payload.base_version,
      });
    },
    async applyPatch(_p, payload, headers = {}) {
      return request(`${basePath}/boards/${payload.board_id}/versions`, {
        method: 'POST', body: payload,
        etag: headers['If-Match'] ?? payload.base_version,
        key: headers['Idempotency-Key'] ?? payload.idempotency_key,
      });
    },
    async undo(_p, payload, headers = {}) {
      return request(`${basePath}/boards/${payload.board_id}/preview`, {
        method: 'POST', body: payload, etag: headers['If-Match'] ?? payload.base_version,
      });
    },
    async listBoards() {
      const row = await request(`${basePath}/boards`);
      if (!row.ok) return row;
      const items = Array.isArray(row.body) ? row.body : (row.body?.items || []);
      return { ...row, body: items };
    },
    async loadBoard(boardId) {
      const row = await request(`${basePath}/boards/${boardId}`);
      if (!row.ok) return row;
      const spec = row.body?.spec && row.body.spec.schema_version === 'competition-board/v1'
        ? row.body.spec
        : row.body;
      return { ...row, body: spec };
    },
  };
}

export function createBoardTransport(options = {}) {
  if (options.http) return createHttpBoardTransport(options.http);
  return createFixtureBoardTransport(options);
}

export {
  canEndorse, decodeCompetitionBatchReceipt, decodeCompetitionBoardSpec,
  decodeCompetitionError, decodeCompetitionPatchRequest, decodeCompetitionResultRef,
  toEndorsedResultRef,
};
