import { css } from './client/styles.ts';
import { COPY, buildSavedAnalysisView } from './saved-analysis-model.mjs';

type SavedAnalysisViewProps = {
  analysis?: unknown;
  list?: unknown[] | null;
  error?: { status: number; code: string; message: string } | null;
  runStatus?: string | null;
  saveState?: 'idle' | 'saved' | 'disabled';
  sessionId?: string | null;
  modelAvailable?: boolean;
};

export function SavedAnalysisView(props: SavedAnalysisViewProps) {
  const view = buildSavedAnalysisView({
    analysis: props.analysis ?? null,
    list: props.list ?? null,
    error: props.error ?? null,
    runStatus: props.runStatus ?? null,
    saveState: props.saveState ?? 'idle',
    sessionId: props.sessionId ?? null,
    modelAvailable: props.modelAvailable === true,
  });
  const session = view.sessionId ?? '';
  const model = view.modelAvailable ? '1' : '0';
  return <>
    <style>{css}</style>
    <div className="analytics-b0-dialog analytics-saved-analysis" data-testid="analytics-saved-analysis-view"
      data-kind={view.kind} data-session={session} data-model={model} data-http="NOT_CONNECTED">
      <h2>{view.heading}</h2>
      <p>{COPY.noSession}</p>
      {view.kind === 'error' && <p role="status">{view.message}</p>}
      {view.kind === 'empty' && <p data-testid="analytics-saved-analysis-empty">{view.message}</p>}
      {view.kind === 'list' && view.items && <ul data-testid="analytics-saved-analysis-list">
        {view.items.map(item => <li key={item.analysis_id} data-analysis-id={item.analysis_id}>
          <strong>{item.title}</strong> · v{item.version} · {item.badge}
          <br />{item.summary}
        </li>)}
      </ul>}
      {view.kind === 'detail' && <>
        <h3>{view.title}</h3>
        <p>{view.badge} · v{view.version}</p>
        <p>{view.condition}</p>
        <p className="analytics-query-card">{view.totals}{view.empty?.code && <>
          {' · '}<abbr title={view.empty.code}>{view.empty.text}</abbr></>}</p>
        <small>{view.evidence}</small>
        {view.refreshCandidate && <p>刷新候选 {view.refreshCandidate.run_id}；当前仍固定 {view.snapshotRunId}</p>}
        {view.saveState === 'saved' && <p>{COPY.saved}</p>}
        <p><button type="button" disabled>{COPY.join}</button> {view.joinHint}</p>
        <small>{view.synthetic} {view.http}</small>
      </>}
      {view.kind === 'save-panel' && <>
        <label>标题<input maxLength={120} aria-label="分析标题" /></label>
        <p>{view.saveState === 'saved' ? COPY.saved : view.saveHint}；{COPY.noApproval}</p>
        <button type="button" disabled={!view.canSave}>{COPY.saveHint}</button>
        <button type="button" disabled>{COPY.join}</button>
        <small>{view.http}</small>
      </>}
    </div>
  </>;
}
