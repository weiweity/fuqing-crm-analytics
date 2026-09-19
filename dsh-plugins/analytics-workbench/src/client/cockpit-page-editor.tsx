import { useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import type { FreeHtmlLibraryStore } from './free-html-library/store.mjs';
import { acceptSelection, editableTextNodes, selectionSrcdoc, type TextNode } from './html-selection-bridge.mjs';
import { FREE_PAGE_REFERRER_POLICY, FREE_PAGE_SANDBOX } from '../free-page/runtime/isolation-policy.mjs';
import { CockpitSidebar } from './CockpitSidebar.tsx';
const NO_NODES: TextNode[] = [];

export function HtmlPreview({ pkg, pageId = 'workspace', version = 0, editing = false, nodes = NO_NODES, selected, onSelect, title }: {
  pkg: { html: string; css?: string; js?: string; resources?: unknown[] }; pageId?: string; version?: number;
  editing?: boolean; nodes?: TextNode[]; selected?: string; onSelect?(node: TextNode | null): void; title: string;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const callback = useRef(onSelect); callback.current = onSelect;
  const channel = useMemo(() => crypto.randomUUID(), [pkg, pageId, version, editing]);
  const srcdoc = useMemo(() => selectionSrcdoc(pkg, { channel, pageId, version, nodes, editing }), [pkg, channel, pageId, version, editing, nodes]);
  useEffect(() => {
    if (!editing) return;
    const receive = (event: MessageEvent) => {
      const node = acceptSelection(event, { source: frame.current?.contentWindow ?? null, channel, pageId, version, nodes });
      if (node !== undefined) callback.current?.(node);
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [channel, pageId, version, editing, nodes]);
  useEffect(() => {
    const send = () => frame.current?.contentWindow?.postMessage({ type: 'cockpit.highlight', channel, pageId, version, nodeId: selected ?? null }, '*');
    send(); const node = frame.current; node?.addEventListener('load', send);
    return () => node?.removeEventListener('load', send);
  }, [selected, channel, pageId, version]);
  return <iframe ref={frame} title={title} data-testid="library-html-preview" className="cockpit-html-frame"
    srcDoc={srcdoc} sandbox={FREE_PAGE_SANDBOX} referrerPolicy={FREE_PAGE_REFERRER_POLICY} />;
}
function decodeText(text: string) {
  const node = document.createElement('textarea'); node.innerHTML = text; return node.value;
}
const bindingCopy: Record<string, string> = { UNBOUND_SAMPLE: '未绑定数据', BOUND_VERIFIED: '已核验数据来源', BOUND_STALE: '数据绑定待更新' };
export function CockpitPageEditor({ store, onInspect }: { store: FreeHtmlLibraryStore; onInspect?(): void }) {
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot);
  const current = state.current!;
  const pkg = state.preview?.snapshot ?? current.package;
  const nodes = useMemo(() => editableTextNodes(current.package, current.binding_manifest), [current.package, current.binding_manifest]);
  const selected = nodes.find(row => row.node_id === state.selection?.node_id);
  const original = selected ? decodeText(selected.text) : '';
  const value = state.textDraft?.value ?? original;
  const locked = state.busy || Boolean(state.preview) || state.confirmationUncertain;
  const choose = (node: TextNode | null) => {
    if (!node) { if (!state.textDraft?.changed) store.clearSelection(); return; }
    store.selectLocatable(node); onInspect?.();
  };
  return <div className="cockpit-editor-layout">
    <div className="cockpit-editor-canvas">
      <div className="cockpit-document-tools">
        <span className="cockpit-badge">{bindingCopy[current.binding_state] ?? current.binding_state}</span>
        <span className="cockpit-muted">{state.mode === 'edit' ? '点选画布中的文字，在右侧修改' : '页面预览'}</span>
        <div className="cockpit-tool-actions">
          <button onClick={() => { store.openContext('source'); onInspect?.(); }}>来源与源码</button>
          <button disabled={state.busy} onClick={() => { void store.loadHistory(); onInspect?.(); }}>版本历史</button>
          <button onClick={() => state.previewAlive ? store.stopPreview() : store.restartPreview()}>{state.previewAlive ? '暂停预览' : '恢复预览'}</button>
        </div>
      </div>
      {state.preview ? <div className="cockpit-notice" data-testid="html-patch-preview">
        <div><strong>{state.preview.operation === 'ROLLBACK' ? '回退预览' : '修改预览'}</strong><p>{state.confirmationUncertain ? '保存结果待核对，请重试本次确认。' : '检查画布变化，确认后才会保存新版本。'}</p>
          {state.textDraft ? <p className="cockpit-change"><del>{state.textDraft.original}</del> → <strong>{state.textDraft.value || '（空文本）'}</strong></p> : null}</div>
        <button disabled={state.busy || state.confirmationUncertain} onClick={() => void store.cancelPreview()}>取消预览</button>
        <button className="cockpit-primary" data-testid="html-confirm" disabled={state.busy} onClick={() => void store.confirmPatch()}>{state.confirmationUncertain ? '重试确认' : '确认保存'}</button>
      </div> : null}
      <div className="cockpit-frame-wrap">{state.previewAlive
        ? <HtmlPreview pkg={pkg} pageId={current.page_id} version={current.version} title={current.title}
          editing={state.mode === 'edit' && !locked} nodes={nodes} selected={state.selection?.node_id} onSelect={choose} />
        : <div className="cockpit-empty"><h2>预览已暂停</h2><p>已保存的页面和当前修改均保留。</p><button onClick={() => store.restartPreview()}>恢复预览</button></div>}
      </div>
    </div>
    <CockpitSidebar visible={state.mode === 'edit' || Boolean(state.contextPanel)}
      title={state.contextPanel === 'source' ? '来源与源码' : state.contextPanel === 'history' ? '版本历史' : '编辑文字'}
      onClose={() => state.contextPanel ? store.closeContext() : store.exitEdit()}>
      {state.contextPanel === 'source' ? <>
        <p className="cockpit-muted">{current.origin_path ? '来自工作区副本：' + current.origin_path : '已保存页面'}</p>
        <p>{bindingCopy[current.binding_state] ?? current.binding_state}</p>
        <pre className="cockpit-source">{current.package.html}</pre>
      </> : state.contextPanel === 'history' ? <>
        <p className="cockpit-muted">回退先预览，确认后保存为新版本。</p>
        {state.historyItems.map(row => <div className="cockpit-history-row" key={row.version}><span>版本 {row.version}{row.version === current.version ? ' · 当前' : ''}</span>
          <button disabled={locked || store.hasUnsavedChanges() || row.version === current.version} onClick={() => void store.previewRollback(row.version)}>预览回退</button></div>)}
        {!state.historyItems.length ? <p>暂无可读取的版本记录。</p> : null}
      </> : <>
        <p className="cockpit-eyebrow">当前选区</p>
        {selected ? <>
          <h3>{original.slice(0, 60) || '空文本'}</h3>
          <label className="cockpit-field">替换文本<textarea data-testid="html-replacement" disabled={locked} value={value}
            rows={6} onChange={event => store.setReplacementText(event.target.value, original)} /></label>
          <p className="cockpit-muted">只替换这段文字。确认前可检查修改效果。</p>
          <button className="cockpit-primary" data-testid="html-preview-patch" disabled={locked || value === original}
            onClick={() => void store.previewPatch(value)}>预览修改</button>
          {state.textDraft?.changed && !state.preview ? <button disabled={state.busy} onClick={() => store.discardTextDraft()}>放弃文本修改</button> : null}
        </> : <>
          <div className="cockpit-selection-hint" aria-hidden="true">↖</div>
          <h3>{nodes.length ? '选择一段文字' : '此页暂无可直接修改的文字'}</h3>
          <p className="cockpit-muted">{nodes.length ? '悬停查看可编辑范围，点击后在这里修改。也可以从下方选择。' : '页面缺少可靠的文字映射，或内容由脚本生成。仍可查看来源与历史版本。'}</p>
        </>}
        {nodes.length ? <label className="cockpit-field">选择文字<select disabled={locked || Boolean(state.textDraft?.changed)}
          value={selected?.node_id ?? ''} onChange={event => choose(nodes.find(row => row.node_id === event.target.value) ?? null)}>
          <option value="">请选择</option>{nodes.map(node => <option key={node.node_id} value={node.node_id}>{decodeText(node.text).slice(0, 60) || node.tag}</option>)}
        </select></label> : null}
        <p className="cockpit-muted">绑定数字与动态区域保持只读。</p>
      </>}
    </CockpitSidebar>
  </div>;
}
