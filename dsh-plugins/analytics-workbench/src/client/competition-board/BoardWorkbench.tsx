import Button from 'antd/es/button';
import Radio from 'antd/es/radio';
import Checkbox from 'antd/es/checkbox';
import Select from 'antd/es/select';
import TextArea from 'antd/es/input/TextArea';
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import {
  ConditionChips, ErrorState, EvidenceBlock, LayoutSlot, StatusBanner, ThemeProvider,
} from '../competition-shell/index.ts';
import { BOARD_LAYOUT_MODE_DEFAULT, DEFAULT_PRINCIPAL } from './c0-fixtures.mjs';
import { canEndorse, conditionChips, defaultBlockLayout, evidenceFields, formatResultRowCount, toEndorsedResultRef } from './decode.mjs';
import { applyLayoutAction, clampLayout, LAYOUT_ACTIONS, matchLayoutKeyboard, pointerDelta } from './layout.mjs';
import {
  beginInflight, disposeSelectionUi, endInflight, getInflight, getPatchTarget, setUiSelection,
  subscribeSelection,
} from './selection.mjs';
import { createBoardTransport } from './transport.mjs';
import { batchIntent, finishBatchIntent } from './batch-intent.mjs';
import { competitionHttpOptions } from '../competition-http.mjs';
import { competitionBoardCss } from './css.ts';
import type {
  BoardLayoutMode, BoardMountProps, BoardTransport, BoardPatchRequest, BlockView, CompetitionBoardSpec,
  CompetitionErrorDetail, CompetitionPatchRequest, CompetitionResultRef, LayoutBox,
  PatchIntent, Principal, RegisteredPlugin, SelectedEditEvent,
} from './types.ts';

const DRAFT_PREFIX = 'competition-a6-board-draft:';
const PLUGINS: RegisteredPlugin[] = ['TABLE', 'BAR', 'LINE', 'METRIC', 'EVIDENCE'];
const amount = (value: number | null) => value === null ? '暂无数据' : value.toLocaleString('zh-CN', { maximumFractionDigits: 4 });

function comparisonText(result: CompetitionResultRef): string {
  if (result.schema_version !== 'competition-computed-result/v1') return result.result_id;
  return `GSV 本期 ${amount(result.facts.current.gsv)} / 对比 ${amount(result.facts.comparison.gsv)}`;
}

function opaqueAttempt(): string {
  const bytes = globalThis.crypto?.getRandomValues?.(new Uint8Array(8));
  const suffix = bytes ? Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('') : String(Date.now());
  return `attempt_c0_${suffix}`;
}

function readLocalDraft(boardId: string): { patch: BoardPatchRequest; not_business_authority: true } | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_PREFIX + boardId);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { patch?: BoardPatchRequest; not_business_authority?: boolean };
    if (!parsed?.patch || parsed.not_business_authority !== true) return null;
    return { patch: parsed.patch, not_business_authority: true };
  } catch {
    return null;
  }
}

function writeLocalDraft(boardId: string, patch: BoardPatchRequest | null) {
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
    ...(result.schema_version === 'competition-computed-result/v1' ? [
      { label: '本期 GSV', value: amount(result.facts.current.gsv) },
      { label: '对比期 GSV', value: amount(result.facts.comparison.gsv) },
      { label: 'GSV 变动额', value: amount(result.facts.difference) },
      { label: 'GSV 变动比例', value: result.facts.change_ratio === null
        ? (result.facts.change_ratio_unavailable_reason === 'ZERO_COMPARISON_GSV' ? '对比期为 0，比例不可计算' : '期间无可用数据')
        : `${(result.facts.change_ratio * 100).toFixed(2)}%` },
      { label: '本期有效订单数', value: String(result.facts.current.order_count) },
      { label: '本期实际截数', value: result.facts.current.through_date ?? '暂无数据' },
    ] : []),
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
    const saved = spec.blocks?.find(block => block.block_id === block_id);
    const result = saved?.source_status === 'UNAVAILABLE' ? null
      : saved?.result ?? results.find(row => row.result_id === saved?.result_id) ?? null;
    const plugin: RegisteredPlugin = saved?.plugin ?? 'TABLE';
    return {
      block_id,
      title: saved?.display_overrides?.title ?? (index === 0 && spec.title ? spec.title : `板块 ${index + 1}`),
      plugin,
      layout: saved?.layout ?? defaultBlockLayout(index),
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
  const facts = block.result?.schema_version === 'competition-computed-result/v1' ? block.result.facts : null;
  const values = facts && facts.current.gsv !== null && facts.comparison.gsv !== null
    ? [{ label: '对比期', value: facts.comparison.gsv }, { label: '本期', value: facts.current.gsv }] : null;
  const maximum = Math.max(1, ...(values?.map(item => item.value) ?? []));
  return (
    <div data-plugin={block.plugin} data-testid={`sm-chart-${block.block_id}`}>
      {empty ? <p>无可用样本：{block.result?.empty_reason}。缺分母不显示 0%。</p> : null}
      {!empty && !values && ['BAR', 'LINE', 'METRIC'].includes(block.plugin) ? (
        <p role="status" data-testid="sm-chart-no-series">当前结果仅提供元数据，暂无可绘制的数值序列。图表类型偏好可保存。</p>
      ) : null}
      {values && block.plugin === 'BAR' ? <div data-testid="sm-computed-bars" aria-label="GSV 两期柱形对比">
        {values.map(item => <div key={item.label}>
          <span>{item.label} {amount(item.value)}</span>
          <div className="sm-chart-bar-track"><div style={{ width: `${item.value / maximum * 100}%` }} /></div>
        </div>)}
      </div> : null}
      {values && block.plugin === 'LINE' ? <figure data-testid="sm-computed-line">
        <svg viewBox="0 0 260 130" role="img" aria-label={`GSV 两期连线：${values.map(item => `${item.label} ${item.value}`).join('，')}`}>
          <polyline points={values.map((item, index) => `${30 + index * 200},${110 - item.value / maximum * 90}`).join(' ')} />
          {values.map((item, index) => <circle key={item.label} cx={30 + index * 200} cy={110 - item.value / maximum * 90} r="4" />)}
        </svg><figcaption>两期数值对比，非每日趋势</figcaption>
      </figure> : null}
      {values && block.plugin === 'METRIC' ? <p data-testid="sm-computed-metric">本期 GSV {amount(values[1].value)}</p> : null}
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
  const selectedBoardKey = `competition-a6-board-selection:${transport.kind}:${principal.actor_id}`;
  const modelAvailable = props.modelAvailable === true;
  const [panel, setPanel] = useState<'endorse' | 'confirm' | 'board'>(props.initialPanel ?? 'endorse');
  const [results, setResults] = useState<CompetitionResultRef[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [layoutMode, setLayoutMode] = useState<BoardLayoutMode>(BOARD_LAYOUT_MODE_DEFAULT.value as BoardLayoutMode);
  const [board, setBoard] = useState<CompetitionBoardSpec | null>(null);
  const [boardChoices, setBoardChoices] = useState<CompetitionBoardSpec[]>([]);
  const [openingBoard, setOpeningBoard] = useState(true);
  const boardLoadSeq = useRef(0);
  const boardOpening = useRef(true);
  const [preview, setPreview] = useState<CompetitionBoardSpec | null>(null);
  const [pending, setPending] = useState<BoardPatchRequest | null>(null);
  const [layouts, setLayouts] = useState<Record<string, LayoutBox>>({});
  const [patchBusy, setPatchBusy] = useState(false);
  const [resultsLoaded, setResultsLoaded] = useState(false);
  const patchSending = useRef(false);
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [uiBlockId, setUiBlockId] = useState<string | null>(null);
  const [scopeMode, setScopeMode] = useState<'block' | 'board'>('block');
  const [instruction, setInstruction] = useState('');
  const [intent, setIntent] = useState<PatchIntent>('STYLE_ONLY');
  const [error, setError] = useState<CompetitionErrorDetail | null>(null);
  const [message, setMessage] = useState('');
  const [receipt, setReceipt] = useState<unknown>(null);
  const creationIntent = useRef<ReturnType<typeof batchIntent> | null>(null);
  const creating = useRef(false);
  const [restore, setRestore] = useState<BoardPatchRequest | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const dragCleanup = useRef<(() => void) | null>(null);
  const [, setSelectionTick] = useState(0);
  const inflight = getInflight();
  const shown = preview ?? board;

  const blocks = useMemo(() => {
    const list = blocksFrom(shown, results);
    return list.map(block => ({
      ...block,
      layout: layouts[block.block_id] ?? block.layout,
      title: titles[block.block_id] ?? block.title,
    }));
  }, [shown, results, layouts, titles]);

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
      setResultsLoaded(true);
    });
    const listed = typeof transport.listBoards === 'function'
      ? transport.listBoards()
      : Promise.resolve({ ok: false, status: 404, body: null });
    void listed.then(async row => {
      if (cancelled) return;
      if (!row.ok) {
        if (row.body?.error) setError(row.body.error);
        return;
      }
      const items = row.ok && Array.isArray(row.body) ? row.body : [];
      setBoardChoices(items.filter(item => item?.board_id));
      let preferred: string | null = null;
      try { preferred = sessionStorage.getItem(selectedBoardKey); } catch { /* optional UI preference */ }
      const first = items.find(item => item?.board_id === preferred) ?? items.find(item => item?.board_id) ?? null;
      const targetId = first?.board_id;
      if (!targetId) return;
      const seq = ++boardLoadSeq.current;
      boardOpening.current = true; setOpeningBoard(true);
      const loaded = await transport.loadBoard(targetId);
      if (cancelled || seq !== boardLoadSeq.current) return;
      boardOpening.current = false; setOpeningBoard(false);
      if (!loaded.ok) { setError(loaded.body.error); return; }
      setBoard(loaded.body);
      const local = readLocalDraft(loaded.body.board_id);
      if (local) setRestore(local.patch);
    }).catch(() => {
      if (!cancelled) setMessage('读取看板失败，请重新打开后重试。');
    }).finally(() => {
      if (!cancelled) { boardOpening.current = false; setOpeningBoard(false); }
    });
    return () => { cancelled = true; boardLoadSeq.current += 1; };
  }, []);

  function rememberBoard(next: CompetitionBoardSpec) {
    setBoard(next);
    try { sessionStorage.setItem(selectedBoardKey, next.board_id); } catch { /* optional UI preference */ }
    setBoardChoices(current => current.some(item => item.board_id === next.board_id)
      ? current.map(item => item.board_id === next.board_id ? next : item)
      : [...current, next]);
  }

  async function selectSavedBoard(boardId: string) {
    if (boardId === board?.board_id || pending || restore || patchSending.current || boardOpening.current || getInflight()) return;
    const seq = ++boardLoadSeq.current;
    boardOpening.current = true; setOpeningBoard(true);
    try {
      const loaded = await transport.loadBoard(boardId);
      if (seq !== boardLoadSeq.current) return;
      if (!loaded.ok) { setError(loaded.body.error); return; }
      rememberBoard(loaded.body);
      setUiSelection(null); setUiBlockId(null); setScopeMode('block');
      setLayouts({}); setTitles({}); setInstruction(''); setPreview(null);
      setRestore(readLocalDraft(loaded.body.board_id)?.patch ?? null);
      setError(null); setMessage('');
    } catch {
      if (seq === boardLoadSeq.current) setMessage('读取看板失败，仍保留原看板，请重试。');
    } finally {
      if (seq === boardLoadSeq.current) { boardOpening.current = false; setOpeningBoard(false); }
    }
  }

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

  async function runPatch(next: BoardPatchRequest, kind: 'preview' | 'apply' | 'undo') {
    if (patchSending.current || boardOpening.current) return;
    if (pending && pending.attempt_id !== next.attempt_id) {
      setMessage('请先保存或放弃当前预览，再进行下一次编辑。');
      return;
    }
    patchSending.current = true; setPatchBusy(true);
    const target = getPatchTarget();
    const payload: BoardPatchRequest = next.schema_version === 'competition-board-chart-patch/v1' ? next : {
      ...next,
      board_id: target?.board_id ?? next.board_id,
      block_id: next.intent === 'STYLE_ONLY' || next.intent === 'FILTER_CHANGE'
        ? (target?.block_id ?? next.block_id)
        : next.block_id,
      base_version: target?.base_version ?? next.base_version,
    };
    try {
      setError(null);
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
        rememberBoard(row.body);
        setPreview(null);
        setPending(null);
        setLayouts({}); setTitles({});
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
    } catch {
      setMessage('请求未确认，请重试；已保存版本以服务端重读为准。');
      setPending(payload);
      writeLocalDraft(payload.board_id, payload);
    } finally {
      patchSending.current = false; setPatchBusy(false);
    }
  }

  async function chartCommit(blockId: string, chartType: RegisteredPlugin) {
    if (!board || patchBusy || pending || getInflight()) return;
    selectBlock(blockId);
    const attempt = opaqueAttempt();
    await runPatch({
      schema_version: 'competition-board-chart-patch/v1',
      attempt_id: attempt, idempotency_key: attempt, intent: 'STYLE_ONLY',
      board_id: board.board_id, block_id: blockId, base_version: board.version, chart_type: chartType,
    }, 'preview');
  }

  function buildPatch(partial: Partial<CompetitionPatchRequest> & { intent: PatchIntent }): CompetitionPatchRequest {
    const spec = shown;
    const blockId = partial.block_id !== undefined ? partial.block_id : scopeMode === 'board' ? null : uiBlockId;
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
    if (pending || restore || patchSending.current) {
      setMessage('请先保存或放弃当前预览，再进行下一次编辑。');
      return;
    }
    setLayouts(current => ({ ...current, [blockId]: layout }));
    await runPatch(buildPatch({
      intent: 'STRUCTURE',
      block_id: blockId,
      cockpit_op: { op: 'layout', card_id: blockId, layout },
      idempotency_key: `layout-${blockId}-v${shown?.version ?? 1}`,
    }), 'preview');
  }

  function onPointer(block: BlockView, axis: 'x' | 'w', event: ReactPointerEvent<HTMLElement>) {
    if (pending || restore || patchSending.current) return;
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
    if (creating.current || boardOpening.current) return;
    creating.current = true;
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
      creationIntent.current = batchIntent(principal, layoutMode, endorsed, creationIntent.current);
      const payload = creationIntent.current.payload;
      const operations = payload.operations;
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
        status?: string;
        receipt?: { status: string };
      };
      if (transport.listBoards) {
        const listed = await transport.listBoards();
        if (listed.ok && Array.isArray(listed.body)) setBoardChoices(listed.body.filter(item => item?.board_id));
      }
      function completeIntent() {
        if ((applied.receipt?.status ?? applied.status) === 'SUCCEEDED') {
          finishBatchIntent(principal, creationIntent.current);
          creationIntent.current = null;
        }
      }
      if (transport.kind === 'fixture' && applied.board?.schema_version === 'competition-board/v1') {
        setError(null);
        rememberBoard(applied.board);
        setPreview(null);
        setPanel('board');
        completeIntent();
        setMessage('已按认可结果成板。同结果多视图共享 result_id，不重复计算。');
        return;
      }
      const createdId = applied.board?.board_id ?? applied.spec?.board_id ?? applied.items?.[0]?.board_id;
      if (createdId) {
        const loaded = await transport.loadBoard(createdId);
        if (loaded.ok && loaded.body?.board_id) {
          setError(null);
          rememberBoard(loaded.body);
          setLayouts({}); setTitles({});
          setPreview(null);
          setPanel('board');
          completeIntent();
          setMessage('已按认可结果成板。同结果多视图共享 result_id，不重复计算。');
        } else {
          if (!loaded.ok) setError(loaded.body.error);
          setMessage('成板请求已返回，读取已存看板失败。可重试原请求，不会重复建板。');
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
    } finally {
      creating.current = false;
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
            kind="synthetic"
            message={modelAvailable
              ? '合成数据，仅用于验收。'
              : '合成数据 · 此看板入口提供手动编辑。'}
          />
          {error ? <>
            <ErrorState
              kind={errorKind(error)}
              title={error.http_status === 409 ? '版本冲突（409）' : error.code}
              detail={error.message}
              actionLabel={error.http_status === 409 ? '重读后再保存' : undefined}
              onAction={error.http_status === 409 ? () => { setError(null); setMessage('已保留本地草案，请核对差异后重做。'); } : undefined}
            />
            <details className="sm-board-details" data-testid="sm-board-error-details">
              <summary>错误详情</summary>
              <p>code={error.code} param={error.param ?? '—'} request_id={error.request_id}</p>
            </details>
          </> : null}
          {restore && shown ? (
            <section className="sm-leave-restore" data-testid="sm-leave-restore" role="status">
              <p>浏览器草稿可恢复，不是经营事实权威。board {shown.board_id} · attempt {restore.attempt_id}</p>
              <Button htmlType="button" onClick={() => { void runPatch(restore, 'preview'); setRestore(null); }}>继续编辑草稿</Button>
              <Button htmlType="button" onClick={() => {
                transport.discardPreview?.();
                writeLocalDraft(shown.board_id, null); endInflight(restore.attempt_id); setRestore(null);
              }}>放弃浏览器草稿</Button>
            </section>
          ) : null}
          {confirmLeave ? (
            <section className="sm-leave-restore" data-testid="sm-leave-confirm" role="alert">
              <p>预览尚未保存。放弃预览不等于撤销已保存版本。</p>
              <Button htmlType="button" onClick={() => setConfirmLeave(false)}>继续编辑</Button>
              <Button htmlType="button" data-testid="sm-discard-preview" onClick={() => {
                transport.discardPreview?.();
                setPending(null); setPreview(null); setConfirmLeave(false);
                setLayouts({}); setTitles({});
                if (shown) writeLocalDraft(shown.board_id, null);
                if (pending) endInflight(pending.attempt_id);
                setMessage('已放弃预览。已保存版本未变。');
              }}>放弃预览</Button>
            </section>
          ) : null}
          <div className="sm-competition-toolbar">
            <Button htmlType="button" data-current={panel === 'endorse' ? '1' : '0'} onClick={() => setPanel('endorse')}>选择结果</Button>
            <Button htmlType="button" data-current={panel === 'confirm' ? '1' : '0'} onClick={() => setPanel('confirm')}>确认摘要</Button>
            <Button htmlType="button" data-current={panel === 'board' ? '1' : '0'} data-testid="sm-open-board" onClick={() => setPanel('board')}>编辑看板</Button>
          </div>
          {message ? <p role="status" data-testid="sm-board-status">{message}</p> : null}

          {panel === 'endorse' || panel === 'confirm' ? (
            <section className="sm-endorsement" data-testid="sm-endorsement">
              <p>认可对象是勾选的成功结果，不是整段聊天。空结果可查看，不能成板。</p>
              <fieldset>
                <legend>成板模式（默认待确认）</legend>
                <Radio name="layout-mode" checked={layoutMode === 'ONE_BOARD_MULTI_BLOCK'}
                    onChange={() => setLayoutMode('ONE_BOARD_MULTI_BLOCK')}>
                  一板多块
                </Radio>
                <Radio name="layout-mode" checked={layoutMode === 'BATCH_MULTI_BOARD'}
                    onChange={() => setLayoutMode('BATCH_MULTI_BOARD')}>
                  批量分板
                </Radio>
                <small>{BOARD_LAYOUT_MODE_DEFAULT.note}</small>
              </fieldset>
              <ul className="sm-endorsement-list" data-testid="sm-result-list">
                {results.map(result => {
                  const eligible = canEndorse(result);
                  return (
                    <li key={result.result_id} data-completeness={result.completeness}>
                        <Checkbox
                          disabled={!eligible}
                          checked={selectedIds.includes(result.result_id)}
                          onChange={event => {
                            setSelectedIds(current => event.target.checked
                              ? [...current, result.result_id]
                              : current.filter(id => id !== result.result_id));
                          }}
                        >
                        <span>
                          <strong>{comparisonText(result)}</strong> · {result.completeness}
                          {result.empty_reason ? ` · ${result.empty_reason}` : ''}
                          <br />query {result.query_id} · {result.resolved_condition?.metric_type ?? '—'}
                        </span>
                        </Checkbox>
                    </li>
                  );
                })}
              </ul>
              {resultsLoaded && !error && results.length === 0 ? <ErrorState kind="empty" title="还没有可认可的结果"
                detail="先在原生聊天完成一次诊断，再回到这里选择结果。当前没有可成板的数据。" /> : null}
              {panel === 'confirm' && selectedResult.map(result => (
                <article key={result.result_id} data-testid="sm-confirm-summary">
                  <h3>确认摘要 {result.result_id}</h3>
                  <ConditionChips items={conditionChips(result)} />
                  <EvidenceBlock {...evidenceFields(result)} />
                  {result.schema_version === 'competition-computed-result/v1' ? <p>{comparisonText(result)}</p> : null}
                  <p>历史范围 {result.resolved_condition?.history_scope?.kind ?? '—'} · 销售范围 {result.resolved_condition?.sales_scope?.kind ?? '—'}</p>
                </article>
              ))}
              <Button htmlType="button" data-testid="sm-confirm-boards" disabled={selectedIds.length === 0} onClick={event => {
                event.preventDefault();
                event.stopPropagation();
                setPanel('confirm');
                void confirmBoards();
              }}>
                按认可结果成板
              </Button>
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
              <label className="sm-board-picker">
                已保存看板
                <Select
                  aria-label="选择已保存看板"
                  value={board?.board_id}
                  placeholder="还没有已保存看板"
                  options={boardChoices.map(item => ({ value: item.board_id, label: `${item.title} · ${item.board_id.slice(-8)}` }))}
                  virtual={false}
                  getPopupContainer={trigger => trigger.parentElement ?? trigger}
                  disabled={boardChoices.length === 0 || Boolean(pending || restore || inflight) || patchBusy || openingBoard}
                  onChange={value => void selectSavedBoard(value)}
                />
              </label>
              {openingBoard ? <p role="status">正在读取看板…</p> : !shown ? (
                <ErrorState kind="empty" title="还没有已保存看板"
                  detail="先在聊天完成诊断，再选择成功结果成板。"
                  actionLabel="选择结果" onAction={() => setPanel('endorse')} />
              ) : <>
              <div className="sm-competition-toolbar" aria-label="保存与撤销">
                <Button htmlType="button" data-testid="sm-board-save" disabled={!pending || patchBusy} onClick={() => pending && void runPatch(pending, 'apply')}>保存新版本</Button>
                <Button htmlType="button" data-testid="sm-board-undo" disabled={Boolean(pending || restore) || patchBusy} onClick={() => {
                  if (!board || board.version < 2) { setMessage('没有可恢复的历史版本。'); return; }
                  void runPatch(buildPatch({
                    intent: 'STRUCTURE',
                    cockpit_op: { op: 'undo', scope: 'board', restore_from_version: board.version - 1 },
                    idempotency_key: `undo-to-${board.version - 1}-from-${board.version}`,
                  }), 'undo');
                }}>撤销已保存</Button>
                <Button htmlType="button" disabled={!dirty || patchBusy} onClick={() => setConfirmLeave(true)}>放弃预览</Button>
              </div>
              {!shown.block_ids?.length ? (
                <ErrorState kind="empty" title="看板暂无板块"
                  detail="这是已保存的空看板。可选择成功结果创建新看板。"
                  actionLabel="选择结果" onAction={() => setPanel('endorse')} />
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
                      {block.result ? <ConditionChips items={conditionChips(block.result).filter(item => item.id === 'sales' || item.id === 'sample')} /> : null}
                      <RegisteredChart block={block} />
                      {block.result ? <details className="sm-board-details" data-testid="sm-saved-board-evidence">
                        <summary>条件与证据</summary>
                        <ConditionChips items={conditionChips(block.result)} />
                        <EvidenceBlock {...evidenceFields(block.result)} />
                      </details> : null}
                      <details className="sm-board-details">
                        <summary>板块标识与布局</summary>
                        <p>{block.block_id} · {block.plugin} · x{layout.x}/y{layout.y}/w{layout.w}/h{layout.h}</p>
                      </details>
                      <div className="sm-block-controls"><label>
                        图表类型
                        <select
                          value={block.plugin}
                          disabled={Boolean(pending || restore) || patchBusy}
                          onChange={event => void chartCommit(block.block_id, event.target.value as RegisteredPlugin)}
                        >
                          {PLUGINS.map(name => <option key={name} value={name}>{name}</option>)}
                        </select>
                      </label>
                      <Button htmlType="button" className="sm-drag-handle" data-testid={`sm-drag-${block.block_id}`}
                        onPointerDown={event => onPointer(block, 'x', event)}>拖动列</Button>
                      <Button htmlType="button" className="sm-resize-handle" data-testid={`sm-resize-${block.block_id}`}
                        onPointerDown={event => onPointer(block, 'w', event)}>缩放宽</Button>
                      </div>
                    </article>
                  );
                })}
              </div>
              {uiBlockId ? (
                <div className="sm-layout-controls" data-testid="sm-layout-controls">
                  {Object.entries(LAYOUT_ACTIONS).map(([action, spec]) => (
                    <Button key={action} htmlType="button" aria-keyshortcuts={spec.shortcut}
                      className={action === 'up' || action === 'down' ? 'sm-phone-only' : undefined}
                      onClick={() => {
                        const current = layouts[uiBlockId] ?? blocks.find(row => row.block_id === uiBlockId)?.layout;
                        if (current) void layoutCommit(uiBlockId, applyLayoutAction(current, action));
                      }}>{spec.label}</Button>
                  ))}
                </div>
              ) : null}
              <div className="sm-scope-chat" data-testid="sm-scope-chat">
                <p>{scopeMode === 'block' ? '聊天范围：只改此板块' : '聊天范围：整板'} · 在途目标 {inflight ? `${inflight.board_id}/${inflight.block_id}` : '无'}</p>
                <p>切选中不改变在途 attempt。切到整板需明确操作。</p>
                <Button htmlType="button" data-testid="sm-scope-block" onClick={() => uiBlockId && selectBlock(uiBlockId)}>只改此板块</Button>
                <Button htmlType="button" data-testid="sm-scope-board" onClick={selectWholeBoard}>切换为整板</Button>
                <fieldset>
                  <legend>补丁意图</legend>
                  <Radio name="intent" checked={intent === 'STYLE_ONLY'} onChange={() => setIntent('STYLE_ONLY')} >STYLE_ONLY（不查询）</Radio>
                  <Radio name="intent" checked={intent === 'FILTER_CHANGE'} onChange={() => setIntent('FILTER_CHANGE')} >FILTER_CHANGE（新 run，当前未接通）</Radio>
                  <Radio name="intent" checked={intent === 'STRUCTURE'} onChange={() => setIntent('STRUCTURE')} >STRUCTURE</Radio>
                </fieldset>
                <TextArea
                  aria-label={scopeMode === 'block' ? '只改此板块' : '整板编辑'}
                  value={instruction}
                  onChange={event => setInstruction(event.target.value)}
                  placeholder="例：这一块只看直播，其他不动"
                />
                <Button htmlType="button" data-testid="sm-scope-send" onClick={submitChat}>发送局部编辑</Button>
              </div>
              </>}
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
