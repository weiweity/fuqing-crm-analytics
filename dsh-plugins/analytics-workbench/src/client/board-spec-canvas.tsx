import { useEffect, useMemo, useState } from 'react';
import {
  cancelPatch, confirmPatch, createCanvasState, previousHistoryVersion, rollbackPrevious, selectBlock, setAsk, setTab,
  visibleBlocks,
} from '../board-spec/canvas-state.mjs';
import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from '../board-spec/fixture.mjs';
import { BOARD_SPEC_KINDS } from '../board-spec/kinds.mjs';
import { interpretBoard } from '../board-spec/interpret.mjs';
import { HTML_SANDBOX, htmlSandboxFrame, httpsSandboxFrame, openHttpsLink, refreshSandboxHtml } from '../board-spec/html-sandbox.mjs';
import { proposeAsk, proposeAskLocal } from '../board-spec/ask.mjs';

const ADD_KINDS = BOARD_SPEC_KINDS.filter((kind) => kind !== 'LINK');
const TABS = [
  { id: 'board' as const, label: '看板' },
  { id: 'browser' as const, label: '浏览器' },
  { id: 'links' as const, label: '链接' },
];

const css = `
.sm-spec-shell { display:flex; min-height:0; flex:1; background:var(--sm-bg); color:var(--sm-ink); position:relative; }
.sm-spec-center { flex:1; min-width:0; display:flex; flex-direction:column; }
.sm-spec-chrome {
  padding:16px 24px 14px; border-bottom:1px solid var(--sm-line); display:flex; flex-direction:column; gap:10px;
}
.sm-spec-title { display:flex; align-items:center; gap:12px; }
.sm-spec-back {
  border:1px solid var(--sm-purple); background:transparent; color:var(--sm-purple);
  border-radius:4px; min-height:24px; padding:0 8px; font:400 14px/22px var(--sm-font-body); cursor:pointer;
}
.sm-spec-titles { display:flex; flex-direction:column; gap:2px; min-width:0; }
.sm-spec-titles h1 { margin:0; font:400 18px/25px var(--sm-font-body); }
.sm-spec-titles p { margin:0; font:400 12px/17px var(--sm-font-body); color:var(--sm-muted); }
.sm-spec-rollback {
  margin-left:auto; border:0; background:var(--sm-nav-active); color:var(--sm-purple);
  border-radius:6px; padding:4px 10px; font:500 12px/14px var(--sm-font-body); cursor:pointer;
}
.sm-spec-rollback:disabled { opacity:.45; cursor:default; }
.sm-spec-tabs { display:flex; gap:20px; }
.sm-spec-tabs button {
  border:0; background:transparent; color:var(--sm-muted); font:400 14px/20px var(--sm-font-body);
  padding:0 0 6px; cursor:pointer;
}
.sm-spec-tabs button[data-on="1"] { color:var(--sm-ink); font-weight:500; box-shadow:inset 0 -2px 0 var(--sm-ink); }
.sm-spec-add { display:flex; flex-wrap:wrap; gap:8px; align-items:center; color:var(--sm-muted); font:12px/18px var(--sm-font-body); }
.sm-spec-add button[data-kind] {
  border:1px solid var(--sm-line); border-radius:6px; padding:4px 8px; background:var(--sm-bg);
  color:var(--sm-ink); font:500 11px/13px var(--sm-font-display); cursor:pointer;
}
.sm-spec-url {
  width:100%; min-height:32px; border:1px solid var(--sm-line); border-radius:6px; padding:4px 11px;
  background:transparent; color:var(--sm-ink); font:400 14px/22px var(--sm-font-body);
}
.sm-spec-canvas { flex:1; min-height:0; overflow:auto; padding:16px 24px 20px; display:flex; flex-direction:column; gap:12px; }
.sm-spec-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:12px; }
.sm-spec-card {
  text-align:left; border:1px solid transparent; border-radius:12px; padding:14px; background:var(--sm-bg-top);
  color:inherit; cursor:pointer; display:flex; flex-direction:column; gap:8px;
}
.sm-spec-card[data-kind="LINK"] { background:var(--sm-bg); border-color:var(--sm-line); padding:14px 16px; }
.sm-spec-card[data-on="1"] { border:1.5px solid var(--sm-purple); }
.sm-spec-card-h { display:flex; gap:8px; align-items:center; }
.sm-spec-card h2 { margin:0; font:700 14px/20px var(--sm-font-body); }
.sm-spec-kind {
  background:var(--sm-nav-active); color:var(--sm-purple); border-radius:6px; padding:1px 6px;
  font:500 10px/14px var(--sm-font-display);
}
.sm-spec-metric { font:500 32px/40px var(--sm-font-display); margin:0; }
.sm-spec-caption, .sm-spec-empty { margin:0; color:var(--sm-muted); font:13px/18px var(--sm-font-body); }
.sm-spec-src {
  align-self:flex-start; border:1px solid var(--sm-line); border-radius:8px; padding:2px 8px;
  background:var(--sm-bg); color:var(--sm-muted); font:400 11px/15px var(--sm-font-body);
}
.sm-spec-bar { height:10px; border-radius:4px; background:var(--sm-purple); margin:4px 0 8px; }
.sm-spec-html-preview { border:1px solid var(--sm-line); border-radius:8px; padding:8px; background:var(--sm-bg); display:flex; flex-direction:column; gap:6px; }
.sm-spec-html-preview i { display:block; height:8px; border-radius:4px; background:var(--sm-purple); font-style:normal; }
.sm-spec-chips { display:flex; flex-wrap:wrap; gap:6px; }
.sm-spec-chips span { background:var(--sm-nav-active); border-radius:4px; padding:2px 8px; font:400 11px/16px var(--sm-font-body); }
.sm-spec-link-k { margin:0; color:var(--sm-purple); font:400 11px/13px var(--sm-font-body); }
.sm-spec-add-slot {
  border:1px dashed var(--sm-line); border-radius:12px; padding:20px 16px; text-align:center;
  color:var(--sm-muted); font:400 13px/16px var(--sm-font-body);
}
.sm-spec-browser h2 { margin:0 0 8px; font:500 16px/19px var(--sm-font-body); }
.sm-spec-iframe {
  width:100%; min-height:480px; border:1px solid var(--sm-line); border-radius:12px; background:var(--sm-bg);
}
.sm-spec-refresh {
  align-self:flex-start; border:1px solid var(--sm-line); background:var(--sm-bg); color:var(--sm-purple);
  border-radius:6px; padding:4px 10px; cursor:pointer; font:500 12px/16px var(--sm-font-body);
}
.sm-spec-dim {
  position:absolute; inset:0; background:rgba(9,5,13,.4); display:flex; align-items:center; justify-content:center; z-index:2;
}
.sm-spec-modal {
  width:min(520px, 92%); background:var(--sm-bg); border:1px solid var(--sm-line); border-radius:12px;
  padding:20px 24px; display:flex; flex-direction:column; gap:12px;
}
.sm-spec-modal h2 { margin:0; font:500 16px/19px var(--sm-font-body); }
.sm-spec-modal pre { margin:0; color:var(--sm-muted); font:12px/16px var(--sm-font-mono); white-space:pre-wrap; }
.sm-spec-modal-actions { display:flex; justify-content:flex-end; gap:8px; }
.sm-spec-cancel {
  border:1px solid var(--sm-line); background:transparent; color:var(--sm-muted);
  border-radius:6px; padding:6px 12px; cursor:pointer; font:400 12px/14px var(--sm-font-body);
}
.sm-spec-write {
  border:0; background:var(--sm-purple); color:var(--sm-bg);
  border-radius:6px; padding:6px 12px; cursor:pointer; font:500 12px/14px var(--sm-font-body);
}
.sm-spec-open { color:var(--sm-purple); font:400 12px/16px var(--sm-font-body); }
.sm-spec-ask {
  width:min(400px, 38%); min-width:280px; border-left:1px solid var(--sm-line); padding:0 0 12px;
  display:flex; flex-direction:column; background:var(--sm-bg); position:relative;
}
.sm-spec-ask[data-collapsed="1"] { width:12px; min-width:12px; padding:0; overflow:hidden; }
.sm-spec-ask[data-collapsed="1"] .sm-spec-ask-body { display:none; }
.sm-spec-ask-head, .sm-spec-ask-tabs { display:flex; align-items:center; gap:8px; padding:10px 12px 8px; }
.sm-spec-ask-head h2 { margin:0; font:500 14px/20px var(--sm-font-body); }
.sm-spec-ask-head p { margin:0; color:var(--sm-muted); font:400 12px/18px var(--sm-font-body); }
.sm-spec-booth { margin-left:auto; border:0; background:transparent; color:var(--sm-ink); width:28px; height:28px; border-radius:14px; cursor:pointer; }
.sm-spec-ask-tabs { gap:16px; padding-top:0; }
.sm-spec-ask-tabs button { border:0; background:transparent; color:var(--sm-muted); font:400 13px/20px var(--sm-font-body); padding:0 0 4px; cursor:pointer; }
.sm-spec-ask-tabs button[data-on="1"] { color:var(--sm-ink); font-weight:500; box-shadow:inset 0 -2px 0 var(--sm-ink); }
.sm-spec-ask-body { flex:1; min-height:0; display:flex; flex-direction:column; }
.sm-spec-msgs { flex:1; min-height:0; overflow:auto; padding:12px; display:flex; flex-direction:column; gap:12px; }
.sm-spec-bubble { align-self:flex-end; background:var(--sm-nav-active); border-radius:12px; padding:8px 12px; font:400 13px/20px var(--sm-font-body); }
.sm-spec-hint { margin:0; color:var(--sm-muted); font:400 12px/18px var(--sm-font-body); }
.sm-spec-hint + p { margin:4px 0 0; font:400 13px/20px var(--sm-font-body); }
.sm-spec-composer { margin:0 12px; border:1px solid var(--sm-line); border-radius:16px; padding:10px 12px; display:flex; flex-direction:column; gap:8px; }
.sm-spec-composer textarea {
  width:100%; min-height:40px; resize:vertical; border:0; background:transparent; color:var(--sm-ink);
  font:400 12px/18px var(--sm-font-body); padding:0;
}
.sm-spec-composer-foot { display:flex; align-items:center; gap:8px; color:var(--sm-muted); font:400 12px/18px var(--sm-font-body); }
.sm-spec-send {
  margin-left:auto; width:28px; height:28px; border:0; border-radius:14px; background:var(--sm-purple);
  color:var(--sm-bg); cursor:pointer; font:600 12px/28px var(--sm-font-body);
}
.sm-spec-grabber { position:absolute; left:0; top:0; bottom:0; width:8px; cursor:ew-resize; }
`;

function kindLabel(kind: string) {
  return kind === 'html_sandbox' ? 'HTML' : kind;
}

function metricCaption(paint: Record<string, unknown>) {
  const series = Array.isArray(paint.series) ? paint.series as { label: string; value: number }[] : [];
  if (series.length < 2) return null;
  const comparison = series[0].value;
  const current = series[1].value;
  const pct = comparison === 0 ? null : ((current - comparison) / comparison) * 100;
  const pctText = pct == null ? '' : ` · ${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`;
  return `本期 ${current} · 对比 ${comparison}${pctText}`;
}

function paintBody(block: { kind: string; bind: string; source_result_id: string | null; paint: Record<string, unknown> }) {
  if (block.bind !== 'bound' && block.kind !== 'LINK' && block.kind !== 'EVIDENCE' && block.kind !== 'html_sandbox') {
    return <p className="sm-spec-empty" data-testid="sm-board-spec-unbound">未绑定结果，不显示 0%</p>;
  }
  const paint = block.paint;
  if (block.kind === 'METRIC' && typeof paint.headline === 'number') {
    return <>
      <p className="sm-spec-metric" data-testid="sm-board-spec-metric-headline">{paint.headline}</p>
      <p className="sm-spec-caption">{metricCaption(paint)}</p>
      {block.bind === 'bound' ? <span className="sm-spec-src">出处 · 合成 GSV 快照</span> : null}
    </>;
  }
  if ((block.kind === 'BAR' || block.kind === 'LINE') && Array.isArray(paint.series)) {
    const series = paint.series as { label: string; value: number }[];
    const max = Math.max(1, ...series.map((s) => s.value));
    return <div data-testid={`sm-board-spec-${block.kind.toLowerCase()}`}>
      {block.kind === 'BAR' ? <p className="sm-spec-caption">换展示不换口径</p> : null}
      {series.map((s) => (
        <div key={s.label}>
          <span className="sm-spec-caption">{s.label} {s.value}</span>
          <div className="sm-spec-bar" style={{ width: `${(s.value / max) * 100}%` }} />
        </div>
      ))}
    </div>;
  }
  if (block.kind === 'TABLE' && Array.isArray(paint.rows)) {
    return <table data-testid="sm-board-spec-table"><tbody>
      {(paint.rows as { label: string; value: number | null }[]).map((row) => (
        <tr key={row.label}><th>{row.label}</th><td>{row.value}</td></tr>
      ))}
    </tbody></table>;
  }
  if (block.kind === 'EVIDENCE' && Array.isArray(paint.chips)) {
    const chips = paint.chips as string[];
    return <>
      <p className="sm-spec-caption" data-testid="sm-board-spec-evidence">{chips.join(' / ')}</p>
      <div className="sm-spec-chips">{chips.map((chip) => <span key={chip}>{chip}</span>)}</div>
    </>;
  }
  if (block.kind === 'html_sandbox') {
    return <>
      <p className="sm-spec-caption" data-testid="sm-board-spec-html">沙箱 HTML。点这块改标题、图标，不改口径。</p>
      <div className="sm-spec-html-preview" aria-hidden="true">
        <i style={{ width: '80%' }} /><i style={{ width: '54%' }} /><i style={{ width: '35%' }} />
      </div>
      <span className="sm-spec-src">出处 · 同一次成板</span>
    </>;
  }
  if (block.kind === 'LINK' && typeof paint.url === 'string') {
    const open = openHttpsLink(paint.url);
    return <>
      <p className="sm-spec-link-k">链接</p>
      <p data-testid="sm-board-spec-link">{typeof paint.title === 'string' && paint.title ? paint.title : paint.url}</p>
      {typeof paint.note === 'string' && paint.note ? <p className="sm-spec-caption">{paint.note}</p> : null}
      {open.ok ? (
        <a className="sm-spec-open" data-testid="sm-board-spec-open-link" href={open.href} target={open.target} rel={open.rel}
          onClick={(event) => event.stopPropagation()}>打开</a>
      ) : null}
    </>;
  }
  return <p className="sm-spec-empty">无可绘制序列</p>;
}

function SandboxFrames({ spec, url, overrides, onRefresh }: {
  spec: { blocks?: object[] };
  url: string;
  overrides: Record<string, string>;
  onRefresh(block: { block_id?: string; refresh_url?: string }): void;
}) {
  const https = httpsSandboxFrame(url);
  if (https.ok && 'src' in https) {
    return <iframe title="沙箱链接" data-testid="sm-board-spec-iframe" className="sm-spec-iframe"
      src={https.src} sandbox={https.sandbox} referrerPolicy={https.referrerPolicy} />;
  }
  const frames: {
    id: string;
    srcdoc?: string;
    sandbox: string;
    referrerPolicy: 'no-referrer';
    refresh_url?: string;
  }[] = [];
  if (Array.isArray(spec.blocks)) {
    spec.blocks.forEach((block) => {
      const row = block as { block_id?: string; kind?: string; refresh_url?: string };
      const frame = htmlSandboxFrame(block);
      const id = typeof row.block_id === 'string' ? row.block_id : '';
      const override = id ? overrides[id] : '';
      if (override) {
        frames.push({ id, srcdoc: override, sandbox: HTML_SANDBOX, referrerPolicy: 'no-referrer', refresh_url: row.refresh_url });
        return;
      }
      if (frame.ok && 'srcdoc' in frame) {
        frames.push({ id, srcdoc: frame.srcdoc, sandbox: frame.sandbox, referrerPolicy: frame.referrerPolicy, refresh_url: row.refresh_url });
        return;
      }
      if (typeof row.refresh_url === 'string' && row.refresh_url) {
        frames.push({ id, sandbox: HTML_SANDBOX, referrerPolicy: 'no-referrer', refresh_url: row.refresh_url });
      }
    });
  }
  if (frames.length === 0) return null;
  return <>{frames.map((row) => (
    <div key={row.id || row.refresh_url}>
      {typeof row.refresh_url === 'string' && row.refresh_url ? (
        <button type="button" className="sm-spec-refresh" data-testid="sm-board-spec-html-refresh"
          onClick={() => onRefresh({ block_id: row.id, refresh_url: row.refresh_url })}>刷新沙箱</button>
      ) : null}
      {row.srcdoc ? (
        <iframe title="沙箱 HTML" data-testid="sm-board-spec-iframe" className="sm-spec-iframe"
          srcDoc={row.srcdoc} sandbox={row.sandbox} referrerPolicy={row.referrerPolicy} />
      ) : null}
    </div>
  ))}</>;
}

export type BoardSpecCanvasProps = {
  spec?: object;
  facts?: object | null;
  goConversation?(): void;
  askTransport?: { fetchImpl: typeof fetch; path?: string; resultsPath?: string };
};

export function BoardSpecCanvas(props: BoardSpecCanvasProps = {}) {
  const spec = props.spec ?? BOARD_SPEC_FIXTURE;
  const facts = props.facts === undefined ? BOARD_SPEC_FACTS : props.facts;
  const boot = useMemo(() => createCanvasState(spec, facts), [spec, facts]);
  const [state, setState] = useState(boot.ok ? boot.value : null);
  const [message, setMessage] = useState(boot.ok ? '' : boot.error.message);
  const [url, setUrl] = useState('');
  const [askTab, setAskTab] = useState<'talk' | 'trace'>('talk');
  const [askOpen, setAskOpen] = useState(true);
  const [sandboxDocs, setSandboxDocs] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!boot.ok) {
      setState(null);
      setMessage(boot.error.message);
      return;
    }
    setMessage('');
    setState((prev) => {
      if (!prev) return boot.value;
      if (prev.spec.board_id !== boot.value.spec.board_id) return boot.value;
      return { ...prev, facts: boot.value.facts };
    });
  }, [boot]);
  if (!state) return <p data-testid="sm-board-spec-reject">{message}</p>;

  const view = interpretBoard(state.spec, state.facts);
  const blocks = visibleBlocks(state);
  const selected = view.ok ? view.value.blocks.find((b) => b.block_id === state.selected_block_id) : null;

  const apply = (next: { ok: true; value: typeof state } | { ok: false; error: { message: string } }) => {
    if (!next.ok) { setMessage(next.error.message); return; }
    setMessage('');
    setState(next.value);
  };

  const propose = () => {
    const finish = (next: { ok: true; value: typeof state; refreshed?: boolean } | { ok: false; error: { message: string } }) => {
      apply(next);
      if (next.ok && next.refreshed) setMessage('已按绑定刷新当前块，未改 spec。');
    };
    if (!props.askTransport) {
      finish(proposeAskLocal(state));
      return;
    }
    void proposeAsk(state, props.askTransport).then(finish);
  };

  return (
    <div className="sm-spec-shell" data-testid="sm-board-spec-canvas" data-tab={state.tab} data-version={state.spec.version}>
      <style>{css}</style>
      <div className="sm-spec-center">
        <div className="sm-spec-chrome">
          <div className="sm-spec-title">
            {props.goConversation ? (
              <button type="button" className="sm-spec-back" data-testid="sm-cockpit-back" onClick={() => props.goConversation?.()}>返回对话</button>
            ) : null}
            <div className="sm-spec-titles">
              <h1>驾驶舱</h1>
              <p>这场对话的产物。单击卡片，右侧按当前表问数；不满意可回退。</p>
            </div>
            <button type="button" className="sm-spec-rollback" data-testid="sm-board-spec-rollback"
              disabled={previousHistoryVersion(state) == null}
              onClick={() => apply(rollbackPrevious(state))}>回退此看板</button>
          </div>
          <div className="sm-spec-tabs" role="tablist">
            {TABS.map((tab) => (
              <button key={tab.id} type="button" role="tab" data-on={state.tab === tab.id ? '1' : '0'}
                data-testid={`sm-board-spec-tab-${tab.id}`}
                onClick={() => apply(setTab(state, tab.id))}>
                {tab.label}
              </button>
            ))}
          </div>
          <div className="sm-spec-add">
            添加：
            {ADD_KINDS.map((kind) => (
              <button key={kind} type="button" data-kind={kind}
                onClick={() => apply(setAsk(state, `加一块 ${kindLabel(kind)}`))}>
                {kindLabel(kind)}
              </button>
            ))}
            <span data-testid="sm-board-spec-version">版本 v{state.spec.version} 当前</span>
          </div>
          <input className="sm-spec-url" data-testid="sm-board-spec-url" value={url}
            placeholder="board://零售GSV-2026-08 · 或粘贴 https://"
            onChange={(event) => setUrl(event.target.value)} />
        </div>
        {state.tab === 'browser' ? (
          <div className="sm-spec-canvas sm-spec-browser" data-testid="sm-board-spec-browser">
            <h2>浏览器</h2>
            <p className="sm-spec-empty">粘贴链接，或打开对话生成的 HTML（沙箱）。不改 DSH 壳。</p>
            <SandboxFrames spec={state.spec} url={url} overrides={sandboxDocs} onRefresh={(block) => {
              void refreshSandboxHtml(block.refresh_url || '').then((got) => {
                if (!got.ok) { setMessage(got.error.message); return; }
                if (!('srcdoc' in got) || !block.block_id) return;
                setMessage('');
                setSandboxDocs((prev) => ({ ...prev, [block.block_id as string]: got.srcdoc }));
              });
            }} />
          </div>
        ) : (
          <div className="sm-spec-canvas">
            <div className="sm-spec-grid">
              {blocks.map((block) => (
                <div key={block.block_id} role="button" tabIndex={0} className="sm-spec-card"
                  data-testid={`sm-board-spec-block-${block.block_id}`}
                  data-kind={block.kind}
                  data-on={state.selected_block_id === block.block_id ? '1' : '0'}
                  onClick={() => apply(selectBlock(state, block.block_id))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      apply(selectBlock(state, block.block_id));
                    }
                  }}>
                  {block.kind === 'LINK' ? null : (
                    <div className="sm-spec-card-h">
                      <h2>{block.title}</h2>
                      <span className="sm-spec-kind">{kindLabel(block.kind)}</span>
                    </div>
                  )}
                  {paintBody(block)}
                </div>
              ))}
            </div>
            {state.tab === 'board' ? (
              <div className="sm-spec-add-slot">＋ 添加组件（点类型，或在右侧说「加一块折线」）</div>
            ) : null}
            {message ? <p role="status" data-testid="sm-board-spec-status">{message}</p> : null}
          </div>
        )}
      </div>
      <aside className="sm-spec-ask" data-testid="sm-board-spec-ask" data-collapsed={askOpen ? '0' : '1'}>
        <div className="sm-spec-grabber" aria-hidden="true" />
        <div className="sm-spec-ask-head">
          <h2>问数</h2>
          <p>当前：{selected?.title ?? '未选中'}{selected?.metric_ref ? ` · ${selected.metric_ref}` : ' · 未绑指标'}{selected?.source_result_id ? ` · ${selected.source_result_id}` : ''}</p>
          <button type="button" className="sm-spec-booth" aria-label={askOpen ? '收起问数栏' : '展开问数栏'}
            data-testid="sm-board-spec-ask-toggle" onClick={() => setAskOpen((open) => !open)}>
            {askOpen ? '–' : '+'}
          </button>
        </div>
        <div className="sm-spec-ask-body">
          <div className="sm-spec-ask-tabs">
            <button type="button" data-on={askTab === 'talk' ? '1' : '0'} onClick={() => setAskTab('talk')}>对话</button>
            <button type="button" data-on={askTab === 'trace' ? '1' : '0'} onClick={() => setAskTab('trace')}>轨迹</button>
          </div>
          <div className="sm-spec-msgs">
            {askTab === 'trace' ? (
              <p className="sm-spec-caption">版本 v{state.spec.version} · 确认才写入</p>
            ) : (
              <>
                {state.ask ? <div className="sm-spec-bubble">{state.ask}</div> : null}
                <p className="sm-spec-hint">建议默认，确认才写入</p>
                <p>将按这块看板改标题。不满意可点「回退此看板」。</p>
              </>
            )}
          </div>
          <div className="sm-spec-composer">
            <textarea data-testid="sm-board-spec-ask-input" value={state.ask}
              placeholder="基于当前表继续问…"
              onChange={(event) => apply(setAsk(state, event.target.value))} />
            <div className="sm-spec-composer-foot">
              <span>+  @  完全权限</span>
              <button type="button" className="sm-spec-send" data-testid="sm-board-spec-propose"
                aria-label="提出 PATCH" onClick={propose}>↑</button>
            </div>
          </div>
        </div>
      </aside>
      {state.pending_patch ? (
        <div className="sm-spec-dim" data-testid="sm-board-spec-patch-modal">
          <div className="sm-spec-modal" role="dialog" aria-labelledby="sm-patch-title">
            <h2 id="sm-patch-title">PATCH_BLOCK · 确认才写入</h2>
            <pre>{JSON.stringify(state.pending_patch)}</pre>
            <p className="sm-spec-caption">只改 spec，不改 r1 里的数字。</p>
            <div className="sm-spec-modal-actions">
              <button type="button" className="sm-spec-cancel" data-testid="sm-board-spec-cancel"
                onClick={() => apply(cancelPatch(state))}>取消</button>
              <button type="button" className="sm-spec-write" data-testid="sm-board-spec-confirm"
                onClick={() => apply(confirmPatch(state))}>确认写入</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
