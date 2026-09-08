import { useEffect, useRef, useState } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import { css } from './styles.ts';
import { COCKPIT_CSS } from '../cockpit-model.mjs';
import {
  addIntentKey, assetRequest, decodeAssetError, decodeHttpAnalysisList, decodeHttpDashboard, formatCard,
} from '../asset-http.mjs';

type DashboardDoc = NonNullable<ReturnType<typeof decodeHttpDashboard>>;
type AnalysisItem = { analysis_id: string; version: number; title: string; observation_days?: number; as_of?: string };
type OverlayProps = PropsRuntime<'shell.overlay'> & {
  useStore<T>(selector: (state: { open: boolean; confirmClose: boolean }) => T): T;
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
  const confirmClose = props.useStore((state: { confirmClose: boolean }) => state.confirmClose);
  const selectedSession = props.useSessions(state => state.current);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const focusFrame = useRef<number | undefined>(undefined);
  const [panel, setPanel] = useState<'board' | 'analyses'>('board');
  const [dashboard, setDashboard] = useState<DashboardDoc | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisItem[]>([]);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingOp | null>(null);
  const [preview, setPreview] = useState<DashboardDoc | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [dragX, setDragX] = useState<number | null>(null);
  const previewSeq = useRef(0);
  const dirtyRef = useRef(false);
  const dragCleanup = useRef<(() => void) | null>(null);

  const shown = preview ?? dashboard;
  const dirty = pending !== null;
  dirtyRef.current = dirty;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
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
        if (items.length === 0) setDashboard(null);
        else {
          const row = await assetRequest(`/b0/dashboards/${items[0].dashboard_id}`);
          setDashboard(decodeHttpDashboard(row.payload));
        }
      } else {
        setDashboard(null);
        setMessage(decodeAssetError(boards.payload).message);
      }
      setPreview(null);
      setPending(null);
      setConfirmDiscard(false);
      setDragX(null);
    } catch {
      setMessage('资产请求失败。');
    } finally {
      setLoading(false);
    }
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
      setDashboard(decoded);
      return decoded;
    } catch {
      setMessage('资产请求失败。');
      return null;
    }
  }

  async function runPreview(op: PendingOp, board = dashboard) {
    if (!board) return;
    const seq = ++previewSeq.current;
    setLoading(true);
    try {
      const row = await assetRequest(`/b0/dashboards/${board.dashboard_id}/preview`, {
        method: 'POST', body: op.body, etag: board.version,
      });
      if (previewSeq.current !== seq) return;
      if (row.status === 409) {
        setMessage('版本已变化，已重新读取，请再预览。');
        await refresh();
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
    if (!pending || !dashboard) return;
    setLoading(true);
    try {
      const row = await assetRequest(`/b0/dashboards/${dashboard.dashboard_id}/versions`, {
        method: 'POST', body: pending.body, key: pending.key, etag: dashboard.version,
      });
      if (row.status === 409) {
        setMessage('版本冲突，未覆盖。请读取当前驾驶舱后再试。');
        await refresh();
        return;
      }
      if (row.status !== 200 && row.status !== 201) {
        setMessage(decodeAssetError(row.payload).message);
        return;
      }
      setDashboard(decodeHttpDashboard(row.payload));
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
    const board = dashboard ?? await createBoard();
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
    if (!dashboard || dashboard.version < 2) {
      setMessage('没有可恢复的历史版本。');
      return;
    }
    const restore = dashboard.version - 1;
    await runPreview({
      op: 'undo',
      body: { op: 'undo', scope: 'board', restore_from_version: restore },
      key: `undo-to-${restore}-from-${dashboard.version}`,
      label: `整板恢复到版本 ${restore}`,
    });
  }

  const rawCards = Array.isArray(shown?.cards) ? shown.cards as unknown[] : [];
  const cards = rawCards.map(formatCard);
  const selected = cards.find(card => card.card_id === selectedCardId) ?? null;

  async function layoutPatch(patch: Record<string, number>) {
    if (!selected || selected.kind !== 'ok' || !dashboard) return;
    const layout = clampLayout(selected.layout, patch);
    await runPreview({
      op: 'layout',
      body: { op: 'layout', card_id: selected.card_id, layout },
      key: `layout-${selected.card_id}-v${dashboard.version}`,
      label: '调整布局',
    });
  }

  return <>
    <style>{css + COCKPIT_CSS + `
      .analytics-b0-dialog.analytics-cockpit-http { width:min(1100px,calc(100vw - 32px)); }
      .analytics-cockpit-toolbar { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
      .analytics-cockpit-card[data-selected="1"] { outline:2px solid currentColor; }
    `}</style>
    <dialog ref={dialogRef} className="analytics-b0-dialog analytics-cockpit-http" aria-labelledby="analytics-b0-heading"
      data-testid="analytics-b0-dialog" data-http="CONNECTED" data-asset="1"
      data-session={selectedSession ? '1' : '0'} data-preview={pending ? '1' : '0'}
      onCancel={event => { event.preventDefault(); requestClose(); }}
      onClose={afterClose}>
      <header>
        <div>
          <span className="analytics-b0-logo" role="img" aria-label="SHINE MAGE 原始 Logo" data-testid="analytics-b0-logo" />
          <h2 id="analytics-b0-heading">伸美 · 我的驾驶舱</h2>
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
      <div className="analytics-cockpit-toolbar">
        <button type="button" data-testid="analytics-asset-board" onClick={() => setPanel('board')}>驾驶舱</button>
        <button type="button" data-testid="analytics-asset-analyses" onClick={() => setPanel('analyses')}>已保存分析</button>
        <button type="button" data-testid="analytics-asset-refresh" onClick={() => void refresh()}>重新读取</button>
      </div>
      {loading && <p role="status">正在读取资产…</p>}
      {message && <p role="status" data-testid="analytics-asset-status">{message}</p>}
      {pending && <p className="analytics-b0-preview" data-testid="analytics-cockpit-preview">{pending.label} · 预览未保存</p>}
      {panel === 'analyses' && <section data-testid="analytics-saved-analysis-view">
        {analyses.length === 0
          ? <p data-testid="analytics-saved-analysis-empty">从一次成功查询保存分析后，可加入驾驶舱。</p>
          : <ul data-testid="analytics-saved-analysis-list">{analyses.map(item => <li key={item.analysis_id}>
            <strong>{item.title}</strong> · v{item.version} · N={item.observation_days} · {item.as_of}
            <br />固定历史快照 / 合成数据
            <button type="button" data-testid={`analytics-join-${item.analysis_id}`}
              onClick={() => void addAnalysis(item)}>加入我的驾驶舱</button>
          </li>)}</ul>}
      </section>}
      {panel === 'board' && <section data-testid="analytics-cockpit-view" data-http="CONNECTED">
        {!shown && <p data-testid="analytics-cockpit-empty">从已保存分析添加</p>}
        {shown && <p>版本 v{shown.version}{shown.preview ? ' · 预览' : ''}</p>}
        <div className="analytics-cockpit-toolbar">
          <button type="button" data-action="add" data-testid="analytics-cockpit-add"
            onClick={() => setPanel('analyses')}>从已保存分析添加</button>
          <button type="button" data-testid="analytics-cockpit-save" disabled={!pending} onClick={() => void savePending()}>保存</button>
          <button type="button" data-testid="analytics-cockpit-undo" onClick={() => void undoBoard()}>撤销整板</button>
        </div>
        <div className="analytics-cockpit-grid" data-testid="analytics-cockpit-grid">
          {cards.map(card => card.kind === 'error'
            ? <article key={card.card_id || 'broken'} className="analytics-b0-card analytics-cockpit-card"
                data-card-id={card.card_id} data-card-error="1" data-source="UNAVAILABLE" role="status">
                固定历史快照不可用：{card.message}
                {card.card_id && <button type="button" data-testid={`analytics-remove-${card.card_id}`} onClick={() => void runPreview({
                  op: 'remove', body: { op: 'remove', card_id: card.card_id },
                  key: `remove-${card.card_id}-v${dashboard?.version}`, label: '移除错误卡',
                })}>移除板块</button>}
              </article>
            : <article key={card.card_id} className="analytics-b0-card analytics-query-card analytics-cockpit-card"
                data-card-id={card.card_id} data-card-error="0" data-source="OK" data-observation-days={card.days}
                data-selected={selectedCardId === card.card_id ? '1' : '0'}
                data-run-id={card.run_id}
                style={{
                  gridColumn: `${(dragX !== null && card.card_id === selectedCardId ? dragX : card.layout.x) + 1} / span ${card.layout.w}`,
                  gridRow: `${card.layout.y + 1} / span ${card.layout.h}`,
                }}
                onClick={() => setSelectedCardId(card.card_id)}>
                <h3>{card.title}</h3>
                <p>固定历史快照 · N={card.days} · 渠道 {card.channels || '全部'} · as_of {card.as_of}</p>
                {card.totals && <p>成熟 {card.totals.channel_mature_cohort_count} / 二单 {card.totals.channel_repeat_count}</p>}
                <small>run {card.run_id} · 合成数据</small>
                <p>
                  <button type="button" data-action="copy" onClick={event => { event.stopPropagation(); void runPreview({
                    op: 'copy', body: { op: 'copy', card_id: card.card_id }, key: `copy-${card.card_id}-v${dashboard?.version}`,
                    label: '复制板块',
                  }); }}>复制板块</button>
                  <button type="button" data-action="remove" onClick={event => { event.stopPropagation(); void runPreview({
                    op: 'remove', body: { op: 'remove', card_id: card.card_id }, key: `remove-${card.card_id}-v${dashboard?.version}`,
                    label: '移除板块',
                  }); }}>移除板块</button>
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
