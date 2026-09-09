import { useEffect, useRef, useState } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import { css } from './styles.ts';
import { trapDialogTab } from './focus.ts';
import { COCKPIT_CSS } from '../cockpit-model.mjs';
import {
  addIntentKey, assetRequest, decodeAssetError, decodeHttpAnalysisList, decodeHttpDashboard, formatCard,
} from '../asset-http.mjs';
import { BoardWorkbench } from './competition-board/index.ts';
import { ActionsWorkbench } from './competition-actions/index.ts';
import { OverlayErrorBoundary } from './overlay-error-boundary.mjs';
import { createHttpBoardTransport } from './competition-board/transport.mjs';
import { createHttpAudienceTransport } from './competition-actions/transport.mjs';
import { competitionHttpOptions } from './competition-http.mjs';

type DashboardDoc = NonNullable<ReturnType<typeof decodeHttpDashboard>>;
type AnalysisItem = { analysis_id: string; version: number; title: string; observation_days?: number; as_of?: string };
type OverlayProps = PropsRuntime<'shell.overlay'> & {
  useStore<T>(selector: (state: { open: boolean; confirmClose: boolean; openTick?: number }) => T): T;
  actions: {
    close(): void;
    requestClose(): void;
    keepEditing(): void;
    discardAndClose(): void;
  };
  useSessions<T>(selector: (state: { current?: string }) => T): T;
  detachSelection(): void;
  restoreSelection(): void;
};

type PendingOp = { op: string; body: Record<string, unknown>; key: string; label: string };

function clampLayout(layout: { x: number; y: number; w: number; h: number }, patch: Partial<typeof layout>) {
  const next = { ...layout, ...patch };
  next.w = Math.min(12, Math.max(2, next.w));
  next.h = Math.min(12, Math.max(2, next.h));
  next.x = Math.min(12 - next.w, Math.max(0, next.x));
  next.y = Math.min(240, Math.max(0, next.y));
  return next;
}

export function HttpAssetOverlay(props: OverlayProps) {
  const open = props.useStore((state: { open: boolean }) => state.open);
  const openTick = props.useStore((state: { openTick?: number }) => state.openTick ?? 0);
  const confirmClose = props.useStore((state: { confirmClose: boolean }) => state.confirmClose);
  const selectedSession = props.useSessions(state => state.current);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const focusFrame = useRef<number | undefined>(undefined);
  const [panel, setPanel] = useState<'board' | 'analyses' | 'competition-board' | 'competition-actions'>('board');
  const [dashboard, setDashboard] = useState<DashboardDoc | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisItem[]>([]);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const competitionHttp = competitionHttpOptions();
  const [pending, setPending] = useState<PendingOp | null>(null);
  const [preview, setPreview] = useState<DashboardDoc | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [visited, setVisited] = useState<{ board: boolean; actions: boolean }>({ board: false, actions: false });
  const [dragX, setDragX] = useState<number | null>(null);
  const previewSeq = useRef(0);
  const dirtyRef = useRef(false);
  const dragCleanup = useRef<(() => void) | null>(null);
  const boardRef = useRef<DashboardDoc | null>(null);

  const shown = preview ?? dashboard;
  const dirty = pending !== null;
  dirtyRef.current = dirty;

  function commitBoard(next: DashboardDoc | null) {
    boardRef.current = next;
    setDashboard(next);
  }

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open, openTick]);
  useEffect(() => () => {
    dragCleanup.current?.();
    dragCleanup.current = null;
    if (focusFrame.current !== undefined) cancelAnimationFrame(focusFrame.current);
    dialogRef.current?.close();
  }, []);
  useEffect(() => {
    if (!open) {
      dragCleanup.current?.();
      dragCleanup.current = null;
      setDragX(null);
    }
  }, [open]);
  useEffect(() => {
    if (open && !dirtyRef.current) void refresh();
  }, [open]);
  useEffect(() => {
    function onSaved() { if (open && !dirtyRef.current) void refresh(); }
    window.addEventListener('analytics-asset-changed', onSaved);
    return () => window.removeEventListener('analytics-asset-changed', onSaved);
  }, [open]);

  async function refresh() {
    previewSeq.current += 1;
    setLoading(true);
    try {
      const [boards, list] = await Promise.all([
        assetRequest('/b0/dashboards'),
        assetRequest('/b0/analyses'),
      ]);
      setAnalyses(decodeHttpAnalysisList(list.payload) ?? []);
      if (boards.status === 200) {
        const items = Array.isArray(boards.payload?.items) ? boards.payload.items : [];
        const pinnedId = boardRef.current?.dashboard_id;
        const listed = pinnedId
          ? items.find((row: { dashboard_id?: string }) => row?.dashboard_id === pinnedId)
          : items[0];
        const targetId = (listed && typeof listed.dashboard_id === 'string' && listed.dashboard_id)
          || pinnedId
          || (items[0] && typeof items[0].dashboard_id === 'string' ? items[0].dashboard_id : undefined);
        if (!targetId) commitBoard(null);
        else {
          const row = await assetRequest(`/b0/dashboards/${targetId}`);
          const decoded = decodeHttpDashboard(row.payload);
          if (decoded) commitBoard(decoded);
          else if (!pinnedId) commitBoard(null);
        }
        setMessage(competitionHttp
          ? 'B0 /b0/assets 与比赛 /api/v1/analytics/competition 分开。比赛成板走合成 HTTP。'
          : '');
      } else if (competitionHttp) {
        if (!boardRef.current) commitBoard(null);
        setMessage('B0 同域 /b0/dashboards 未接线。比赛资产走合成 HTTP，不把 /b0/assets 404 写成比赛失败。');
      } else {
        if (!boardRef.current) commitBoard(null);
        setMessage(decodeAssetError(boards.payload).message);
      }
      setPreview(null);
      setPending(null);
      setConfirmDiscard(false);
      setDragX(null);
    } catch {
      setMessage(competitionHttp
        ? 'B0 同域资产不可达。比赛 HTTP 仍可在「认可成板」使用。'
        : '资产请求失败。');
    } finally {
      setLoading(false);
    }
  }

  function keepDialogOpen() {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) {
      try { dialog.showModal(); } catch { /* already in top layer */ }
    }
  }

  function handleDialogClose(event: { preventDefault(): void }) {
    if (open) {
      event.preventDefault();
      keepDialogOpen();
      return;
    }
    afterClose();
  }

  function selectPanel(next: 'board' | 'analyses' | 'competition-board' | 'competition-actions') {
    if (next === 'competition-board') setVisited(current => ({ ...current, board: true }));
    if (next === 'competition-actions') setVisited(current => ({ ...current, actions: true }));
    window.setTimeout(() => {
      setPanel(next);
      keepDialogOpen();
    }, 0);
  }

  function afterClose() {
    props.actions.close();
    props.restoreSelection();
    if (focusFrame.current !== undefined) cancelAnimationFrame(focusFrame.current);
    focusFrame.current = requestAnimationFrame(() => {
      focusFrame.current = requestAnimationFrame(() => {
        focusFrame.current = undefined;
        if (!dialogRef.current?.open) {
          document.querySelector<HTMLButtonElement>('[data-testid="analytics-b0-open"]')?.focus({ preventScroll: true });
        }
      });
    });
  }

  function requestClose() {
    if (dirty) {
      setConfirmDiscard(true);
      return;
    }
    props.actions.close();
  }

  async function createBoard() {
    try {
      const created = await assetRequest('/b0/dashboards', {
        method: 'POST', body: { title: '我的驾驶舱' }, key: 'board-owner',
      });
      if (created.status !== 200 && created.status !== 201) {
        setMessage(decodeAssetError(created.payload).message);
        return null;
      }
      const decoded = decodeHttpDashboard(created.payload);
      commitBoard(decoded);
      return decoded;
    } catch {
      setMessage('资产请求失败。');
      return null;
    }
  }

  async function runPreview(op: PendingOp, board = boardRef.current) {
    if (!board) return;
    const dashboardId = board.dashboard_id;
    const etag = board.version;
    const seq = ++previewSeq.current;
    setLoading(true);
    try {
      const row = await assetRequest(`/b0/dashboards/${dashboardId}/preview`, {
        method: 'POST', body: op.body, etag,
      });
      if (previewSeq.current !== seq) return;
      if (row.status === 409) {
        await refresh();
        setMessage('版本已变化，已重新读取，请再预览。');
        return;
      }
      if (row.status !== 200) {
        setMessage(decodeAssetError(row.payload).message);
        return;
      }
      setPending(op);
      setPreview(decodeHttpDashboard(row.payload));
      setMessage(`预览：${op.label}。尚未保存。`);
    } catch {
      if (previewSeq.current !== seq) return;
      setMessage('资产请求失败。');
    } finally {
      if (previewSeq.current === seq) setLoading(false);
    }
  }

  async function savePending() {
    const board = boardRef.current;
    if (!pending || !board) return;
    const dashboardId = board.dashboard_id;
    const etag = board.version;
    setLoading(true);
    try {
      const row = await assetRequest(`/b0/dashboards/${dashboardId}/versions`, {
        method: 'POST', body: pending.body, key: pending.key, etag,
      });
      if (row.status === 409) {
        await refresh();
        setMessage('版本冲突，未覆盖。请读取当前驾驶舱后再试。');
        return;
      }
      if (row.status !== 200 && row.status !== 201) {
        setMessage(decodeAssetError(row.payload).message);
        return;
      }
      const decoded = decodeHttpDashboard(row.payload);
      if (decoded) commitBoard(decoded);
      setPreview(null);
      setPending(null);
      setMessage('已保存固定历史快照。');
      window.dispatchEvent(new Event('analytics-asset-changed'));
    } catch {
      setMessage('资产请求失败。');
    } finally {
      setLoading(false);
    }
  }

  async function addAnalysis(item: { analysis_id: string; version: number; title: string }) {
    const board = boardRef.current ?? await createBoard();
    if (!board) return;
    const key = addIntentKey(item.analysis_id, item.version, board.version);
    if (!key) {
      setMessage('资产请求失败。');
      return;
    }
    await runPreview({
      op: 'add',
      body: { op: 'add', analysis_ref: { analysis_id: item.analysis_id, version: item.version } },
      key,
      label: `添加 ${item.title}`,
    }, board);
    setPanel('board');
  }

  async function undoBoard() {
    const board = boardRef.current;
    if (!board || board.version < 2) {
      setMessage('没有可恢复的历史版本。');
      return;
    }
    const restore = board.version - 1;
    await runPreview({
      op: 'undo',
      body: { op: 'undo', scope: 'board', restore_from_version: restore },
      key: `undo-to-${restore}-from-${board.version}`,
      label: `整板恢复到版本 ${restore}`,
    }, board);
  }

  const rawCards = Array.isArray(shown?.cards) ? shown.cards as unknown[] : [];
  const cards = rawCards.map(formatCard);
  const selected = cards.find(card => card.card_id === selectedCardId) ?? null;

  function showAnalyses() {
    previewSeq.current += 1;
    setLoading(false);
    selectPanel('analyses');
  }

  async function layoutPatch(patch: Record<string, number>) {
    const board = boardRef.current;
    if (!selected || selected.kind !== 'ok' || !board) return;
    const layout = clampLayout(selected.layout, patch);
    await runPreview({
      op: 'layout',
      body: { op: 'layout', card_id: selected.card_id, layout },
      key: `layout-${selected.card_id}-v${board.version}`,
      label: '调整布局',
    }, board);
  }

  return <>
    <style>{css + COCKPIT_CSS + `
      .analytics-cockpit-card[data-selected="1"] { outline:2px solid var(--dsw-alias-brand-primary,currentColor); outline-offset:2px; }
    `}</style>
    <dialog ref={dialogRef} className="analytics-b0-dialog analytics-cockpit-http" aria-labelledby="analytics-b0-heading"
      data-testid="analytics-b0-dialog" data-dsh-native-chrome="1" data-http="CONNECTED" data-asset="1" data-panel="assets" data-competition-panel={panel}
      data-dashboard-id={shown?.dashboard_id ?? ''}
      data-session={selectedSession ? '1' : '0'} data-preview={pending ? '1' : '0'}
      {...{ closedby: 'none' }}
      onKeyDown={trapDialogTab}
      onCancel={event => { event.preventDefault(); requestClose(); }}
      onClose={handleDialogClose}>
      <header>
        <div>
          <span className="analytics-b0-logo" role="img" aria-label="SHINE MAGE 原始 Logo" data-testid="analytics-b0-logo" />
          <h2 id="analytics-b0-heading">伸美 AI 增长董事会</h2>
        </div>
        <button type="button" data-testid="analytics-b0-close" onClick={requestClose}>返回聊天</button>
      </header>
      {(confirmDiscard || confirmClose) && <section className="analytics-b0-preview" role="alert" data-testid="analytics-b0-close-confirm">
        <p>预览尚未保存，是否放弃本次修改？</p>
        <div className="analytics-b0-actions">
          <button type="button" onClick={() => { setConfirmDiscard(false); props.actions.keepEditing(); }}>继续编辑</button>
          <button type="button" data-testid="analytics-asset-discard" onClick={() => {
            setPending(null); setPreview(null); setConfirmDiscard(false); setDragX(null);
            props.actions.discardAndClose();
          }}>放弃草稿并返回</button>
        </div>
      </section>}
      <p><strong>固定历史快照 / 合成数据</strong> · 无活动会话、模型不可用时仍可读已保存资产。</p>
      <p data-testid="analytics-b0-selection">{selectedSession ? '原会话仍保留；此资产不依赖会话。' : '当前无活动会话；固定资产仍可读。'}</p>
      <button type="button" data-testid="analytics-b0-detach" disabled={!selectedSession}
        onClick={() => props.detachSelection()}>脱离会话阅读</button>
      <div className="analytics-cockpit-toolbar" onMouseDown={event => event.stopPropagation()}>
        <button type="button" data-testid="analytics-asset-board" onClick={event => { event.stopPropagation(); selectPanel('board'); }}>驾驶舱</button>
        <button type="button" data-testid="analytics-asset-analyses" onClick={event => { event.stopPropagation(); showAnalyses(); }}>已保存分析</button>
        <button type="button" data-testid="analytics-competition-board" onClick={event => { event.stopPropagation(); selectPanel('competition-board'); }}>认可成板</button>
        <button type="button" data-testid="analytics-competition-actions" onClick={event => { event.stopPropagation(); selectPanel('competition-actions'); }}>人群行动</button>
        <button type="button" data-testid="analytics-asset-refresh" onClick={event => { event.stopPropagation(); void refresh(); }}>重新读取</button>
      </div>
      {loading && <p role="status">正在读取资产…</p>}
      {message && <p role="status" data-testid="analytics-asset-status">{message}</p>}
      {pending && <p className="analytics-b0-preview" data-testid="analytics-cockpit-preview">{pending.label} · 预览未保存</p>}
      {(panel === 'competition-board' || visited.board) && <section hidden={panel !== 'competition-board'} data-panel="competition-board" data-testid="analytics-competition-board-view">
        <OverlayErrorBoundary resetKey={openTick}>
          <BoardWorkbench key={openTick} modelAvailable={false} transport={competitionHttp ? createHttpBoardTransport(competitionHttp) : undefined} />
        </OverlayErrorBoundary>
      </section>}
      {(panel === 'competition-actions' || visited.actions) && <section hidden={panel !== 'competition-actions'} data-panel="competition-actions" data-testid="analytics-competition-actions-view">
        <ActionsWorkbench modelAvailable={false} transport={competitionHttp ? createHttpAudienceTransport(competitionHttp) : undefined} />
      </section>}
      {panel === 'analyses' && <section data-panel="analyses" data-testid="analytics-saved-analysis-view">
        {analyses.length === 0
          ? <p data-testid="analytics-saved-analysis-empty">从一次成功查询保存分析后，可加入驾驶舱。</p>
          : <ul data-testid="analytics-saved-analysis-list">{analyses.map(item => <li key={item.analysis_id}>
            <strong>{item.title}</strong> · v{item.version} · N={item.observation_days} · {item.as_of}
            <br />固定历史快照 / 合成数据
            <button type="button" data-testid={`analytics-join-${item.analysis_id}`}
              onClick={() => void addAnalysis(item)}>加入我的驾驶舱</button>
          </li>)}</ul>}
      </section>}
      {panel === 'board' && <section data-panel="board" data-testid="analytics-cockpit-view" data-http="CONNECTED">
        {!shown && <p data-testid="analytics-cockpit-empty">从已保存分析添加</p>}
        {shown && <p>版本 v{shown.version}{shown.preview ? ' · 预览' : ''}</p>}
        <div className="analytics-cockpit-toolbar">
          <button type="button" data-action="add" data-testid="analytics-cockpit-add"
            onClick={showAnalyses}>从已保存分析添加</button>
          <button type="button" data-testid="analytics-cockpit-save" disabled={!pending} onClick={() => void savePending()}>保存</button>
          {panel === 'board' && <button type="button" data-testid="analytics-cockpit-undo" onClick={() => void undoBoard()}>撤销整板</button>}
        </div>
        <div className="analytics-cockpit-grid" data-testid="analytics-cockpit-grid">
          {cards.map(card => card.kind === 'error'
            ? <article key={card.card_id || 'broken'} className="analytics-b0-card analytics-cockpit-card"
                data-card-id={card.card_id} data-card-error="1" data-source="UNAVAILABLE" role="status"
                style={{ gridColumn: '1 / -1' }}>
                固定历史快照不可用：{card.message}
                {card.card_id && <button type="button" data-testid={`analytics-remove-${card.card_id}`} onClick={() => void runPreview({
                  op: 'remove', body: { op: 'remove', card_id: card.card_id },
                  key: `remove-${card.card_id}-v${boardRef.current?.version}`, label: '移除错误卡',
                }, boardRef.current ?? undefined)}>移除板块</button>}
              </article>
            : <article key={card.card_id} className="analytics-b0-card analytics-query-card analytics-cockpit-card"
                data-card-id={card.card_id} data-card-error="0" data-source="OK" data-observation-days={card.days}
                data-selected={selectedCardId === card.card_id ? '1' : '0'}
                data-run-id={card.run_id} data-family={card.family}
                style={{
                  gridColumn: `${(dragX !== null && card.card_id === selectedCardId ? dragX : card.layout.x) + 1} / span ${card.layout.w}`,
                  gridRow: `${card.layout.y + 1} / span ${card.layout.h}`,
                }}
                onClick={() => setSelectedCardId(card.card_id)}>
                <h3>{card.title}</h3>
                {card.family === 'first_purchase'
                  ? <p>固定历史快照 · 首购商品路径 · N={card.days} · as_of {card.as_of}</p>
                  : <p>固定历史快照 · N={card.days} · 渠道 {card.channels || '全部'} · as_of {card.as_of}</p>}
                {card.family === 'first_purchase'
                  ? <p>成熟 {card.cohortMature ?? 0} · {card.displayName}</p>
                  : card.totals && <p>成熟 {card.totals.channel_mature_cohort_count} / 二单 {card.totals.channel_repeat_count}</p>}
                <small>run {card.run_id} · 合成数据</small>
                <p>
                  <button type="button" data-action="copy" onClick={event => { event.stopPropagation(); void runPreview({
                    op: 'copy', body: { op: 'copy', card_id: card.card_id }, key: `copy-${card.card_id}-v${boardRef.current?.version}`,
                    label: '复制板块',
                  }, boardRef.current ?? undefined); }}>复制板块</button>
                  <button type="button" data-action="remove" onClick={event => { event.stopPropagation(); void runPreview({
                    op: 'remove', body: { op: 'remove', card_id: card.card_id }, key: `remove-${card.card_id}-v${boardRef.current?.version}`,
                    label: '移除板块',
                  }, boardRef.current ?? undefined); }}>移除板块</button>
                </p>
              </article>)}
        </div>
        {selected?.kind === 'ok' && <div className="analytics-cockpit-toolbar" data-testid="analytics-layout-controls">
          <button type="button" onClick={() => void layoutPatch({ x: selected.layout.x - 1 })}>左移</button>
          <button type="button" onClick={() => void layoutPatch({ x: selected.layout.x + 1 })}>右移</button>
          <button type="button" onClick={() => void layoutPatch({ y: selected.layout.y - 1 })}>上移</button>
          <button type="button" onClick={() => void layoutPatch({ y: selected.layout.y + 1 })}>下移</button>
          <button type="button" onClick={() => void layoutPatch({ w: selected.layout.w + 1 })}>加宽</button>
          <button type="button" onClick={() => void layoutPatch({ w: selected.layout.w - 1 })}>减宽</button>
          <button type="button" data-testid="analytics-layout-drag"
            onPointerDown={event => {
              const originLayout = selected.layout;
              const startX = event.clientX;
              const origin = originLayout.x;
              function move(ev: PointerEvent) {
                const next = clampLayout(originLayout, { x: origin + Math.round((ev.clientX - startX) / 48) });
                setDragX(next.x);
              }
              function finish(ev: PointerEvent) {
                dragCleanup.current?.();
                dragCleanup.current = null;
                const next = clampLayout(originLayout, { x: origin + Math.round((ev.clientX - startX) / 48) });
                setDragX(null);
                if (next.x !== origin) void layoutPatch({ x: next.x });
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
            }}>拖动列</button>
        </div>}
        {pending && dashboard && <p>撤销将整板恢复到版本 {dashboard.version} 的已保存配置，不是单卡编辑。</p>}
      </section>}
      <p><small>SYNTHETIC · HTTP CONNECTED · 浏览器不缓存 facts。每次打开重新鉴权读取。</small></p>
    </dialog>
  </>;
}
