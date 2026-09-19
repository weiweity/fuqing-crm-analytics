import { useEffect, useRef, useState } from 'react';
import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import type { LibraryBoardClient } from './library-board-client.mjs';
export { LibraryCockpitPanel } from './cockpit-workspace.tsx';

export function GenerateChipIcon() {
  return <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <rect x="1.75" y="2.625" width="10.5" height="8.75" rx="1.75" stroke="currentColor" strokeWidth="1.225" />
    <path d="M1.75 5.25h10.5" stroke="currentColor" strokeWidth="1.225" />
  </svg>;
}

export function LibraryGenerateDock({ sessionId, generate }: { sessionId: string; generate(sessionId: string): Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const generation = useRef(0);
  useEffect(() => {
    setBusy(false); setMessage('');
    return () => { generation.current++; };
  }, [sessionId]);
  return <div className="analytics-b0-artifacts" data-testid="library-generate-dock">
    <button type="button" className="analytics-b0-generate-dock" disabled={busy} aria-label="生成驾驶舱" onClick={() => {
      setBusy(true); setMessage('');
      const requestGeneration = ++generation.current;
      void generate(sessionId).then(() => {
        if (generation.current === requestGeneration) setMessage('已交给当前原生对话生成，结果会出现在工具卡。');
      }).catch(() => {
        if (generation.current === requestGeneration) setMessage('未能提交生成请求；请在当前原生对话输入“生成驾驶舱”。');
      }).finally(() => { if (generation.current === requestGeneration) setBusy(false); });
    }}><GenerateChipIcon />生成驾驶舱</button>
    <span role="status">{message}</span>
  </div>;
}

export function LibraryPreviewToolCard(props: ToolCallViewProps & { library?: LibraryBoardClient; openCockpit?(): boolean }) {
  const block = props.block;
  if (!('kind' in block) || block.kind !== 'tool-result') return <p role="status">正在生成驾驶舱草稿…</p>;
  const meta = block.meta as Record<string, unknown> | undefined;
  if (block.isError || meta?.schema_version !== 'board-tool-result/v1' || meta.status !== 'PREVIEW_READY'
    || typeof meta.preview_id !== 'string' || meta.published !== false) {
    return <p role="status">未生成可确认的看板草稿，请查看原生对话中的原因。</p>;
  }
  return <div data-testid="library-preview-tool-card">
    <p>{String(meta.title ?? '驾驶舱')} · {String(meta.component_count)} 个组件 · 尚未保存</p>
    <button type="button" disabled={!props.library} onClick={() => {
      void props.library?.openPreview(meta.preview_id as string, typeof meta.edit_context_id === 'string' ? meta.edit_context_id : undefined);
      props.openCockpit?.();
    }}>打开预览，检查后确认</button>
  </div>;
}
