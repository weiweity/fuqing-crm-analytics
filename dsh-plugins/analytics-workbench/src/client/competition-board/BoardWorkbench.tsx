import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import {
  ConditionChips, ErrorState, EvidenceBlock, LayoutSlot, StatusBanner, ThemeProvider,
} from '../competition-shell/index.ts';
import { BOARD_LAYOUT_MODE_DEFAULT, DEFAULT_PRINCIPAL, RESULT_SUCCESS, RESULT_EMPTY } from './c0-fixtures.mjs';
import { canEndorse, conditionChips, defaultBlockLayout, evidenceFields, formatResultRowCount, toEndorsedResultRef } from './decode.mjs';
import { applyLayoutAction, clampLayout, LAYOUT_ACTIONS, matchLayoutKeyboard, pointerDelta } from './layout.mjs';
import {
  beginInflight, disposeSelectionUi, endInflight, getInflight, getPatchTarget, setUiSelection,
  subscribeSelection,
} from './selection.mjs';
import { createBoardTransport } from './transport.mjs';
import { competitionHttpOptions } from '../competition-http.mjs';
import { competitionBoardCss } from './css.ts';
import type {
  BoardLayoutMode, BoardMountProps, BoardTransport, BlockView, CompetitionBoardSpec,
  CompetitionErrorDetail, CompetitionPatchRequest, CompetitionResultRef, LayoutBox,
  PatchIntent, Principal, RegisteredPlugin, SelectedEditEvent,
} from './types.ts';

const DRAFT_PREFIX = 'competition-a6-board-draft:';
const PLUGINS: RegisteredPlugin[] = ['TABLE', 'BAR', 'LINE', 'METRIC', 'EVIDENCE'];

function opaqueAttempt(): string {
  const bytes = globalThis.crypto?.getRandomValues?.(new Uint8Array(8));
  const suffix = bytes ? Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('') : String(Date.now());
  return `attempt_c0_${suffix}`;
}

function readLocalDraft(boardId: string): { patch: CompetitionPatchRequest; not_business_authority: true } | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_PREFIX + boardId);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { patch?: CompetitionPatchRequest; not_business_authority?: boolean };
    if (!parsed?.patch || parsed.not_business_authority !== true) return null;
    return { patch: parsed.patch, not_business_authority: true };
  } catch {
    return null;
  }
}

function writeLocalDraft(boardId: string, patch: CompetitionPatchRequest | null) {
  try {
    if (!patch) {
      sessionStorage.removeItem(DRAFT_PREFIX + boardId);
      return;
    }
    sessionStorage.setItem(DRAFT_PREFIX + boardId, JSON.stringify({
      patch, not_business_authority: true, saved_at: new Date().toISOString(),
    }));
  } catch { /* browser storage optional */ }
}

function rowsFor(result: CompetitionResultRef | null): { label: string; value: string }[] {
  if (!result) return [];
  const resolved = result.resolved_condition;
  const current = resolved?.current_period;
  return [
    { label: '完整性', value: result.completeness ?? '—' },
    { label: '行数', value: formatResultRowCount(result) },
    { label: '空因', value: result.empty_reason ?? '—' },
    { label: '本期', value: current?.start_date && current?.end_date ? `${current.start_date}–${current.end_date}` : '—' },
    { label: '对比', value: resolved?.comparison_mode ?? '—' },
  ];
}

function blocksFrom(spec: CompetitionBoardSpec | null, results: CompetitionResultRef[]): BlockView[] {
  if (!spec) return [];
  return spec.block_ids.map((block_id, index) => {
    const result = results.find(row => row.completeness === 'COMPLETE') ?? results[0] ?? null;
    const plugin: RegisteredPlugin = index === 1 ? 'BAR' : 'TABLE';
    return {
      block_id,
      title: index === 0 && spec.title ? spec.title : `板块 ${index + 1}`,
      plugin,
      layout: defaultBlockLayout(index),
      result,
      rows: rowsFor(result),
      summary: result
        ? `${result.query_id} ${result.completeness}；截数 ${result.resolved_condition?.as_of ?? '—'}`
        : '无绑定结果',
    };
  });
}

function RegisteredChart({ block }: { block: BlockView }) {
  const empty = block.result?.completeness === 'EMPTY';
  return (
    <div data-plugin={block.plugin} data-testid={`sm-chart-${block.block_id}`}>
      {empty ? <p>无可用样本：{block.result?.empty_reason}。缺分母不显示 0%。</p> : null}
      {!empty && block.plugin === 'BAR' ? (
        <div className="sm-chart-bar" aria-hidden="true">
          {block.rows.map(row => (
            <div key={row.label}>
              <span>{row.label}</span>
              <span className="sm-chart-bar-track"><i style={{ width: row.label === '行数' ? '40%' : '18%' }} /></span>
            </div>
          ))}
        </div>
      ) : null}
      {!empty && block.plugin === 'LINE' ? (
        <svg viewBox="0 0 120 36" width="100%" height="36" role="img" aria-label={block.summary}>
          <polyline fill="none" stroke="currentColor" strokeWidth="2" points="0,28 24,20 48,22 72,12 96,16 120,8" />
        </svg>
      ) : null}
      <table className="sm-chart-table">
        <caption>{block.summary}</caption>
        <thead><tr><th>字段</th><th>值</th></tr></thead>
        <tbody>
          {block.rows.map(row => (
            <tr key={row.label} data-field={row.label}><th scope="row">{row.label}</th><td>{row.value}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function errorKind(error: CompetitionErrorDetail | null): 'conflict' | 'forbidden' | 'failed' | 'empty' {
  if (!error) return 'failed';
  if (error.http_status === 409) return 'conflict';
  if (error.http_status === 403) return 'forbidden';
  if (error.http_status === 404) return 'empty';
  return 'failed';
}

export function BoardWorkbench(props: BoardMountProps) {
  const httpOptions = competitionHttpOptions();
  const transportRef = useRef<BoardTransport>(props.transport ?? createBoardTransport(httpOptions ? { http: httpOptions } : {}));
  const transport = props.transport ?? transportRef.current;
  const principal: Principal = props.principal ?? DEFAULT_PRINCIPAL;
  const modelAvailable = props.modelAvailable === true;
  const [panel, setPanel] = useState<'endorse' | 'confirm' | 'board'>('endorse');
  const [results, setResults] = useState<CompetitionResultRef[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [layoutMode, setLayoutMode] = useState<BoardLayoutMode>(BOARD_LAYOUT_MODE_DEFAULT.value as BoardLayoutMode);
  const [board, setBoard] = useState<CompetitionBoardSpec | null>(null);
  const [preview, setPreview] = useState<CompetitionBoardSpec | null>(null);
  const [pending, setPending] = useState<CompetitionPatchRequest | null>(null);
  const [layouts, setLayouts] = useState<Record<string, LayoutBox>>({});
  const [plugins, setPlugins] = useState<Record<string, RegisteredPlugin>>({});
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [uiBlockId, setUiBlockId] = useState<string | null>(null);
  const [scopeMode, setScopeMode] = useState<'block' | 'board'>('block');
  const [instruction, setInstruction] = useState('');
  const [intent, setIntent] = useState<PatchIntent>('STYLE_ONLY');
  const [error, setError] = useState<CompetitionErrorDetail | null>(null);
  const [message, setMessage] = useState('');
  const [receipt, setReceipt] = useState<unknown>(null);
  const [restore, setRestore] = useState<CompetitionPatchRequest | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const dragCleanup = useRef<(() => void) | null>(null);
  const [, setSelectionTick] = useState(0);
  const inflight = getInflight();
  const shown = preview ?? board;

  const blocks = useMemo(() => {
    const list = blocksFrom(shown, results.length ? results : [RESULT_SUCCESS, RESULT_EMPTY]);
    return list.map(block => ({
      ...block,
      layout: layouts[block.block_id] ?? block.layout,
      plugin: plugins[block.block_id] ?? block.plugin,
      title: titles[block.block_id] ?? block.title,
    }));
  }, [shown, results, layouts, plugins, titles]);

  useEffect(() => {
    let cancelled = false;
    void transport.listEndorseableResults(principal).then(row => {
      if (cancelled) return;
      if (!row.ok) {
        setError(row.body.error);
        setResults([]);
        return;
      }
      setResults(row.body.filter(Boolean));
    });
    const listed = typeof transport.listBoards === 'function'
      ? transport.listBoards()
      : Promise.resolve({ ok: false, status: 404, body: null });
    void listed.then(async row => {
      if (cancelled) return;
      const items = row.ok && Array.isArray(row.body) ? row.body : [];
      const first = items.find(item => item?.board_id) ?? null;
      const targetId = first?.board_id;
      if (!targetId) return;
      const loaded = await transport.loadBoard(targetId);
      if (cancelled || !loaded.ok) return;
      setBoard(loaded.body);
      const local = readLocalDraft(loaded.body.board_id);
      if (local) setRestore(local.patch);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => subscribeSelection(() => setSelectionTick(value => value + 1)), []);
  useEffect(() => () => {
    dragCleanup.current?.();
    disposeSelectionUi();
  }, []);

  function selectBlock(blockId: string) {
    const spec = shown;
    setUiBlockId(blockId);
    setScopeMode('block');
    if (spec) setUiSelection({ board_id: spec.board_id, block_id: blockId, base_version: spec.version });
  }

  function selectWholeBoard() {
    const spec = shown;
    setScopeMode('board');
    if (spec) setUiSelection({ board_id: spec.board_id, block_id: null, base_version: spec.version });
  }

  async function runPatch(next: CompetitionPatchRequest, kind: 'preview' | 'apply' | 'undo') {
    const target = getPatchTarget();
    const payload = {
      ...next,
      board_id: target?.board_id ?? next.board_id,
      block_id: next.intent === 'STYLE_ONLY' || next.intent === 'FILTER_CHANGE'
        ? (target?.block_id ?? next.block_id)
        : next.block_id,
      base_version: target?.base_version ?? next.base_version,
    };
    beginInflight({
      board_id: payload.board_id,
      block_id: payload.block_id,
      base_version: payload.base_version,
      attempt_id: payload.attempt_id,
    });
    const headers = { 'If-Match': String(payload.base_version), 'Idempotency-Key': payload.idempotency_key };
    const method = kind === 'apply' ? transport.applyPatch : kind === 'undo' ? transport.undo : transport.previewPatch;
    const row = await method(principal, payload, headers);
    if (!row.ok) {
      setError(row.body.error);
      if (row.status === 409) writeLocalDraft(payload.board_id, payload);
      if (row.status !== 409) endInflight(payload.attempt_id);
      return;
    }
    if (kind === 'apply') {
      setBoard(row.body);
      setPreview(null);
      setPending(null);
      writeLocalDraft(payload.board_id, null);
      setMessage('已保存新版本。撤销走版本检查，不是放弃预览。');
      endInflight(payload.attempt_id);
      return;
    }
    setPreview(row.body);
    setPending(payload);
    writeLocalDraft(payload.board_id, payload);
    setMessage(kind === 'undo' ? '预览整板恢复。尚未保存。' : '预览未保存，不会写入驾驶舱。');
    setPanel('board');
  }

  function buildPatch(partial: Partial<CompetitionPatchRequest> & { intent: PatchIntent }): CompetitionPatchRequest {
    const spec = shown;
    const blockId = scopeMode === 'board' ? null : uiBlockId;
    return {
      schema_version: 'competition-board-patch/v1',
      attempt_id: opaqueAttempt(),
      base_version: spec?.version ?? 1,
      block_id: blockId,
      board_id: spec?.board_id ?? 'dash_c0_board_a',
      cockpit_op: partial.cockpit_op ?? null,
      display_op: partial.display_op ?? null,
      filter_change: partial.filter_change ?? null,
      idempotency_key: partial.idempotency_key ?? `patch-${blockId ?? 'board'}-${spec?.version ?? 1}`,
      intent: partial.intent,
    };
  }

  async function layoutCommit(blockId: string, layout: LayoutBox) {
    setLayouts(current => ({ ...current, [blockId]: layout }));
    await runPatch(buildPatch({
      intent: 'STRUCTURE',
      block_id: blockId,
      cockpit_op: { op: 'layout', card_id: blockId, layout },
      idempotency_key: `layout-${blockId}-v${shown?.version ?? 1}`,
    }), 'preview');
  }

  function onPointer(block: BlockView, axis: 'x' | 'w', event: ReactPointerEvent<HTMLButtonElement>) {
    const origin = block.layout;
    const start = event.clientX;
    function move(ev: PointerEvent) {
      const next = pointerDelta(start, ev.clientX, origin, axis);
      setDrag({ x: next.x, y: next.y });
      setLayouts(current => ({ ...current, [block.block_id]: next }));
    }
    function finish(ev: PointerEvent) {
      dragCleanup.current?.();
      dragCleanup.current = null;
      const next = pointerDelta(start, ev.clientX, origin, axis);
      setDrag(null);
      if (next.x !== origin.x || next.w !== origin.w) void layoutCommit(block.block_id, next);
    }
    dragCleanup.current?.();
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', finish);
    window.addEventListener('pointercancel', finish);
    dragCleanup.current = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', finish);
      window.removeEventListener('pointercancel', finish);
    };
  }

  function onBoardKey(event: { key: string; altKey: boolean; shiftKey: boolean; ctrlKey?: boolean; metaKey?: boolean; preventDefault(): void }) {
    const action = matchLayoutKeyboard(event);
    if (!action || !uiBlockId) return;
    event.preventDefault();
    const current = layouts[uiBlockId] ?? blocks.find(row => row.block_id === uiBlockId)?.layout;
    if (!current) return;
    void layoutCommit(uiBlockId, applyLayoutAction(current, action));
  }

  async function confirmBoards() {
    try {
      setError(null);
      const endorsed = selectedIds
        .map(id => results.find(row => row.result_id === id))
        .map(row => row ? toEndorsedResultRef(row) : null)
        .filter((row): row is NonNullable<typeof row> => Boolean(row));
      if (endorsed.length === 0) {
        setMessage('只能认可 completeness=COMPLETE 的成功结果。');
        return;
      }
      const operations = layoutMode === 'BATCH_MULTI_BOARD'
        ? endorsed.map((ref, index) => ({
          board_id: null,
          endorsed_result_refs: [ref],
          idempotency_key: `board-create-${ref.result_id}`,
          layout_mode: layoutMode,
          operation_id: `op_c0_board_${index + 1}`,
          request_fingerprint: ref.evidence_digest,
          title: `认可 ${ref.result_id}`,
        }))
        : [{
          board_id: null,
          endorsed_result_refs: endorsed,
          idempotency_key: 'board-create-a',
          layout_mode: layoutMode,
          operation_id: 'op_c0_board_a',
          request_fingerprint: endorsed[0].evidence_digest,
          title: '8月GSV诊断板',
        }];
      const payload = {
        schema_version: 'competition-board-batch/v1' as const,
        batch_id: layoutMode === 'BATCH_MULTI_BOARD' ? 'batch_c0_multi' : 'batch_c0_1',
        layout_mode: layoutMode,
        operations,
      };
      const previewRow = await transport.previewBatch(principal, payload);
      if (!previewRow.ok) {
        setError(previewRow.body.error);
        return;
      }
      if (previewRow.body.receipt) {
        setReceipt(previewRow.body.receipt);
        setMessage('批量回执为部分成功。失败项不可冒充成功，只重试失败 operation_id。');
      }
      const applyRow = await transport.applyBatch(principal, payload, { 'Idempotency-Key': operations[0].idempotency_key });
      if (!applyRow.ok) {
        setError(applyRow.body.error);
        setMessage('成板未完成。驾驶舱保持打开，可重试；相同幂等键不会重复建板。');
        return;
      }
      if (applyRow.body.receipt) setReceipt(applyRow.body.receipt);
      const applied = applyRow.body as {
        board?: CompetitionBoardSpec | null;
        spec?: CompetitionBoardSpec;
        items?: Array<{ board_id?: string }>;
      };
      if (applied.board?.schema_version === 'competition-board/v1') {
        setError(null);
        setBoard(applied.board);
        setPreview(null);
        setPanel('board');
        setMessage('已按认可结果成板。同结果多视图共享 result_id，不重复计算。');
        return;
      }
      const createdId = applied.board?.board_id ?? applied.spec?.board_id ?? applied.items?.[0]?.board_id;
      if (createdId) {
        const loaded = await transport.loadBoard(createdId);
        if (loaded.ok && loaded.body?.board_id) {
          setError(null);
          setBoard(loaded.body);
          setPreview(null);
          setPanel('board');
          setMessage('已按认可结果成板。同结果多视图共享 result_id，不重复计算。');
        }
      }
    } catch (caught) {
      setError({
        schema_version: 'competition-error/v1',
        code: 'FAILED',
        message: caught instanceof Error ? caught.message : '成板失败',
        http_status: 500,
        maps_to: 'backend.contracts.analytics.AnalyticsErrorDetail',
        request_id: 'req_board_confirm_catch',
        retryable: true,
      } as CompetitionErrorDetail);
      setMessage('成板未完成。驾驶舱保持打开，可重试；相同幂等键不会重复建板。');
    }
  }

  function submitChat() {
    const spec = shown;
    if (!spec) return;
    const target = getPatchTarget() ?? { board_id: spec.board_id, block_id: uiBlockId, base_version: spec.version };
    const event: SelectedEditEvent = {
      board_id: target.board_id,
      block_id: scopeMode === 'board' ? null : target.block_id,
      base_version: target.base_version,
      intent,
      instruction,
    };
    props.onSelectedEdit?.(event);
    if (intent === 'FILTER_CHANGE') {
      void runPatch(buildPatch({
        intent: 'FILTER_CHANGE',
        filter_change: { op: 'filter_change', card_id: event.block_id ?? spec.block_ids[0], local_filters: { channel_ids: ['A'] } },
      }), 'preview');
      return;
    }
    if (intent === 'STYLE_ONLY' && event.block_id) {
      const title = instruction.trim() || '渠道贡献（样式）';
      setTitles(current => ({ ...current, [event.block_id as string]: title }));
      void runPatch(buildPatch({
        intent: 'STYLE_ONLY',
        display_op: { op: 'display', card_id: event.block_id, display_overrides: { title } },
        idempotency_key: 'patch-style-1',
      }), 'preview');
    }
  }

  const selectedResult = results.filter(row => selectedIds.includes(row.result_id));
  const dirty = pending !== null;

  return (
    <ThemeProvider>
      <style>{competitionBoardCss}</style>
      <LayoutSlot name="cockpit">
        <div
          className="sm-competition-board"
          data-testid="sm-competition-board"
          data-model={modelAvailable ? '1' : '0'}
          data-transport={transport.kind}
          data-layout-mode={layoutMode}
          data-preview={preview ? '1' : '0'}
          data-inflight={inflight?.attempt_id ?? ''}
          data-scope={scopeMode}
          onKeyDown={event => onBoardKey(event)}
        >
          <h2>认可结果与可编辑看板</h2>
          <StatusBanner
            kind={modelAvailable ? 'synthetic' : 'model_unavailable'}
            message={modelAvailable
              ? 'SYNTHETIC · C0 fixture。经营事实以后端校验为准。'
              : '模型不可用。仍可查看已存板并手动拖拽/键盘改布局。'}
          />
          {error ? (
            <ErrorState
              kind={errorKind(error)}
              title={error.http_status === 409 ? '版本冲突（409）' : error.code}
              detail={`${error.message} param=${error.param ?? '—'} request_id=${error.request_id}`}
              actionLabel={error.http_status === 409 ? '重读后再保存' : undefined}
              onAction={error.http_status === 409 ? () => { setError(null); setMessage('已保留本地草案，请核对差异后重做。'); } : undefined}
            />
          ) : null}
          {restore && shown ? (
            <section className="sm-leave-restore" data-testid="sm-leave-restore" role="status">
              <p>浏览器草稿可恢复，不是经营事实权威。board {shown.board_id} · attempt {restore.attempt_id}</p>
              <button type="button" onClick={() => { setPending(restore); setRestore(null); setPanel('board'); }}>继续编辑草稿</button>
              <button type="button" onClick={() => { writeLocalDraft(shown.board_id, null); setRestore(null); }}>放弃浏览器草稿</button>
            </section>
          ) : null}
          {confirmLeave ? (
            <section className="sm-leave-restore" data-testid="sm-leave-confirm" role="alert">
              <p>预览尚未保存。放弃预览不等于撤销已保存版本。</p>
              <button type="button" onClick={() => setConfirmLeave(false)}>继续编辑</button>
              <button type="button" data-testid="sm-discard-preview" onClick={() => {
                transport.discardPreview?.();
                setPending(null); setPreview(null); setConfirmLeave(false);
                if (shown) writeLocalDraft(shown.board_id, null);
                if (pending) endInflight(pending.attempt_id);
                setMessage('已放弃预览。已保存版本未变。');
              }}>放弃预览</button>
            </section>
          ) : null}
          <div className="sm-competition-toolbar">
            <button type="button" data-current={panel === 'endorse' ? '1' : '0'} onClick={() => setPanel('endorse')}>选择结果</button>
            <button type="button" data-current={panel === 'confirm' ? '1' : '0'} onClick={() => setPanel('confirm')}>确认摘要</button>
            <button type="button" data-current={panel === 'board' ? '1' : '0'} data-testid="sm-open-board" onClick={() => setPanel('board')}>编辑看板</button>
            <button type="button" data-testid="sm-board-save" disabled={!pending} onClick={() => pending && void runPatch(pending, 'apply')}>保存新版本</button>
            <button type="button" data-testid="sm-board-undo" onClick={() => {
              if (!board || board.version < 2) { setMessage('没有可恢复的历史版本。'); return; }
              void runPatch(buildPatch({
                intent: 'STRUCTURE',
                cockpit_op: { op: 'undo', scope: 'board', restore_from_version: board.version - 1 },
                idempotency_key: `undo-to-${board.version - 1}-from-${board.version}`,
              }), 'undo');
            }}>撤销已保存</button>
            <button type="button" disabled={!dirty} onClick={() => setConfirmLeave(true)}>放弃预览</button>
          </div>
          {message ? <p role="status" data-testid="sm-board-status">{message}</p> : null}

          {panel === 'endorse' || panel === 'confirm' ? (
            <section className="sm-endorsement" data-testid="sm-endorsement">
              <p>认可对象是勾选的成功结果，不是整段聊天。空结果可查看，不能成板。</p>
              <fieldset>
                <legend>成板模式（默认待确认）</legend>
                <label>
                  <input type="radio" name="layout-mode" checked={layoutMode === 'ONE_BOARD_MULTI_BLOCK'}
                    onChange={() => setLayoutMode('ONE_BOARD_MULTI_BLOCK')} />
                  一板多块
                </label>
                <label>
                  <input type="radio" name="layout-mode" checked={layoutMode === 'BATCH_MULTI_BOARD'}
                    onChange={() => setLayoutMode('BATCH_MULTI_BOARD')} />
                  批量分板
                </label>
                <small>{BOARD_LAYOUT_MODE_DEFAULT.note}</small>
              </fieldset>
              <ul className="sm-endorsement-list" data-testid="sm-result-list">
                {results.map(result => {
                  const eligible = canEndorse(result);
                  return (
                    <li key={result.result_id} data-completeness={result.completeness}>
                      <label>
                        <input
                          type="checkbox"
                          disabled={!eligible}
                          checked={selectedIds.includes(result.result_id)}
                          onChange={event => {
                            setSelectedIds(current => event.target.checked
                              ? [...current, result.result_id]
                              : current.filter(id => id !== result.result_id));
                          }}
                        />
                        <span>
                          <strong>{result.result_id}</strong> · {result.completeness}
                          {result.empty_reason ? ` · ${result.empty_reason}` : ''}
                          <br />query {result.query_id} · {result.resolved_condition?.metric_type ?? '—'}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
              {panel === 'confirm' && selectedResult.map(result => (
                <article key={result.result_id} data-testid="sm-confirm-summary">
                  <h3>确认摘要 {result.result_id}</h3>
                  <ConditionChips items={conditionChips(result)} />
                  <EvidenceBlock {...evidenceFields(result)} />
                  <p>历史范围 {result.resolved_condition?.history_scope?.kind ?? '—'} · 销售范围 {result.resolved_condition?.sales_scope?.kind ?? '—'}</p>
                </article>
              ))}
              <button type="button" data-testid="sm-confirm-boards" onClick={event => {
                event.preventDefault();
                event.stopPropagation();
                setPanel('confirm');
                void confirmBoards();
              }}>
                按认可结果成板
              </button>
            </section>
          ) : null}

          {receipt && typeof receipt === 'object' ? (
            <section data-testid="sm-batch-receipt">
              <h3>逐板回执</h3>
              <ul className="sm-receipt-list">
                {(receipt as { items?: { operation_id: string; status: string; error_code: string | null }[] }).items?.map(item => (
                  <li key={item.operation_id} data-status={item.status}>
                    {item.operation_id} · {item.status}{item.error_code ? ` · ${item.error_code}` : ''}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {panel === 'board' ? (
            <section data-testid="sm-board-editor">
              {!shown || !shown.block_ids?.length ? (
                <ErrorState kind="empty" title="空板" detail="无块的已存板仍合法。从已保存分析添加，不预填假 KPI。" />
              ) : null}
              {preview ? <p className="sm-diff" data-testid="sm-preview-hint">预览未保存。受影响板块 {shown?.affected_block_ids?.join(', ') || '—'}</p> : null}
              {pending && board ? (
                <div className="sm-diff" data-testid="sm-diff">
                  <p>本地草案 intent={pending.intent} base_version={pending.base_version}；已保存版本 v{board.version}。</p>
                  <p>放弃预览 ≠ 撤销。409 不覆盖，保留草案。</p>
                </div>
              ) : null}
              <div className="sm-board-grid" data-testid="sm-board-grid">
                {blocks.map(block => {
                  const layout = drag && uiBlockId === block.block_id
                    ? { ...block.layout, x: drag.x }
                    : block.layout;
                  const selected = uiBlockId === block.block_id && scopeMode === 'block';
                  const affected = Boolean(shown?.affected_block_ids?.includes(block.block_id));
                  const inflightHere = inflight?.block_id === block.block_id;
                  return (
                    <article
                      key={block.block_id}
                      className="sm-block"
                      data-testid={`sm-block-${block.block_id}`}
                      data-block-id={block.block_id}
                      data-selected={selected ? '1' : '0'}
                      data-affected={affected ? '1' : '0'}
                      data-inflight={inflightHere ? '1' : '0'}
                      data-plugin={block.plugin}
                      style={{
                        gridColumn: `${layout.x + 1} / span ${layout.w}`,
                        gridRow: `${layout.y + 1} / span ${layout.h}`,
                      }}
                      onClick={() => selectBlock(block.block_id)}
                    >
                      {selected ? <p className="sm-block-selected-label">已选中 · 只改此板块</p> : null}
                      <h3>{block.title}</h3>
                      <p>{block.plugin} · x{layout.x}/y{layout.y}/w{layout.w}/h{layout.h}</p>
                      <RegisteredChart block={block} />
                      <label>
                        登记图表
                        <select
                          value={block.plugin}
                          onChange={event => setPlugins(current => ({
                            ...current, [block.block_id]: event.target.value as RegisteredPlugin,
                          }))}
                        >
                          {PLUGINS.map(name => <option key={name} value={name}>{name}</option>)}
                        </select>
                      </label>
                      <button type="button" className="sm-drag-handle" data-testid={`sm-drag-${block.block_id}`}
                        onPointerDown={event => onPointer(block, 'x', event)}>拖动列</button>
                      <button type="button" className="sm-resize-handle" data-testid={`sm-resize-${block.block_id}`}
                        onPointerDown={event => onPointer(block, 'w', event)}>缩放宽</button>
                    </article>
                  );
                })}
              </div>
              {uiBlockId ? (
                <div className="sm-layout-controls" data-testid="sm-layout-controls">
                  {Object.entries(LAYOUT_ACTIONS).map(([action, spec]) => (
                    <button key={action} type="button" aria-keyshortcuts={spec.shortcut}
                      className={action === 'up' || action === 'down' ? 'sm-phone-only' : undefined}
                      onClick={() => {
                        const current = layouts[uiBlockId] ?? blocks.find(row => row.block_id === uiBlockId)?.layout;
                        if (current) void layoutCommit(uiBlockId, applyLayoutAction(current, action));
                      }}>{spec.label}</button>
                  ))}
                </div>
              ) : null}
              <div className="sm-scope-chat" data-testid="sm-scope-chat">
                <p>{scopeMode === 'block' ? '聊天范围：只改此板块' : '聊天范围：整板'} · 在途目标 {inflight ? `${inflight.board_id}/${inflight.block_id}` : '无'}</p>
                <p>切选中不改变在途 attempt。切到整板需明确操作。</p>
                <button type="button" data-testid="sm-scope-block" onClick={() => uiBlockId && selectBlock(uiBlockId)}>只改此板块</button>
                <button type="button" data-testid="sm-scope-board" onClick={selectWholeBoard}>切换为整板</button>
                <fieldset>
                  <legend>补丁意图</legend>
                  <label><input type="radio" name="intent" checked={intent === 'STYLE_ONLY'} onChange={() => setIntent('STYLE_ONLY')} /> STYLE_ONLY（不查询）</label>
                  <label><input type="radio" name="intent" checked={intent === 'FILTER_CHANGE'} onChange={() => setIntent('FILTER_CHANGE')} /> FILTER_CHANGE（新 run，当前未接通）</label>
                  <label><input type="radio" name="intent" checked={intent === 'STRUCTURE'} onChange={() => setIntent('STRUCTURE')} /> STRUCTURE</label>
                </fieldset>
                <textarea
                  aria-label={scopeMode === 'block' ? '只改此板块' : '整板编辑'}
                  value={instruction}
                  onChange={event => setInstruction(event.target.value)}
                  placeholder="例：这一块只看直播，其他不动"
                />
                <button type="button" data-testid="sm-scope-send" onClick={submitChat}>发送局部编辑</button>
              </div>
            </section>
          ) : null}
        </div>
      </LayoutSlot>
    </ThemeProvider>
  );
}

export function clampBoardLayout(layout: LayoutBox, patch: Partial<LayoutBox>): LayoutBox {
  return clampLayout(layout, patch);
}
