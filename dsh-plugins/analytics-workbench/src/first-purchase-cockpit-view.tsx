import { css } from './client/styles.ts';
import { COCKPIT_CSS, COPY, buildCockpitView } from './first-purchase-cockpit-model.mjs';

type CockpitViewProps = {
  dashboard?: unknown;
  list?: unknown[] | null;
  error?: { status: number; code: string; message: string } | null;
  sessionId?: string | null;
  modelAvailable?: boolean;
  selectedCardId?: string | null;
};

export function FirstPurchaseCockpitView(props: CockpitViewProps) {
  const view = buildCockpitView({
    dashboard: props.dashboard ?? null,
    list: props.list ?? null,
    error: props.error ?? null,
    sessionId: props.sessionId ?? null,
    modelAvailable: props.modelAvailable === true,
    selectedCardId: props.selectedCardId ?? null,
  });
  const session = view.sessionId ?? '';
  const model = view.modelAvailable ? '1' : '0';
  const keys = view.keyboard;
  return <>
    <style>{css + COCKPIT_CSS}</style>
    <div className="analytics-b0-dialog analytics-cockpit" data-testid="analytics-first-purchase-cockpit-view"
      data-kind={view.kind} data-session={session} data-model={model} data-http="NOT_CONNECTED"
      data-finite-mock="1" data-keyboard-add={keys.add.shortcut} data-keyboard-copy={keys.copy.shortcut}
      data-keyboard-remove={keys.remove.shortcut} data-preview={view.preview ? '1' : '0'}
      data-version={view.version ?? ''}>
      <h2>{view.heading}</h2>
      <p>{COPY.noSession}</p>
      {view.kind === 'error' && <p role="status">{view.message}</p>}
      {(view.kind === 'empty' || view.kind === 'empty-board') && <>
        <p data-testid="analytics-first-purchase-cockpit-empty">{view.message}</p>
        <button type="button" data-action="add" aria-keyshortcuts={keys.add.shortcut}>{COPY.add}</button>
      </>}
      {view.kind === 'list' && view.items && <ul data-testid="analytics-first-purchase-cockpit-list">
        {view.items.map(item => <li key={item.dashboard_id} data-dashboard-id={item.dashboard_id}>
          <strong>{item.title}</strong> · v{item.version}
          <br />{item.summary}
        </li>)}
      </ul>}
      {view.kind === 'board' && <>
        {view.previewHint && <p className="analytics-b0-preview" data-testid="analytics-first-purchase-cockpit-preview">{view.previewHint}</p>}
        <div className="analytics-b0-actions">
          <button type="button" data-action="add" aria-keyshortcuts={keys.add.shortcut}>{COPY.add}</button>
          <button type="button" data-action="save" disabled={!view.preview}>{COPY.save}</button>
          <button type="button" data-action="undo">{COPY.undo}</button>
        </div>
        <div className="analytics-cockpit-grid" data-testid="analytics-first-purchase-cockpit-grid">
          {view.cards.map(card => card.kind === 'error'
            ? <article key={card.card_id ?? 'broken'} className="analytics-b0-card analytics-cockpit-card"
                data-card-id={card.card_id ?? ''} data-card-error="1" role="status">{COPY.cardError}</article>
            : <article key={card.card_id} className="analytics-b0-card analytics-query-card analytics-cockpit-card"
                data-card-id={card.card_id} data-card-error="0" data-affected={card.affected ? '1' : '0'}
                data-plugin={card.plugin} data-selected={card.selected ? '1' : '0'}
                style={{
                  gridColumn: `${card.layout.x + 1} / span ${card.layout.w}`,
                  gridRow: `${card.layout.y + 1} / span ${card.layout.h}`,
                }}>
                <h3>{card.title}</h3>
                <p>{card.badge} · {card.plugin} · x{card.layout.x}/y{card.layout.y}/w{card.layout.w}/h{card.layout.h}</p>
                <p>{card.condition}</p>
                <p>{card.totals}{card.empty?.code && <>
                  {' · '}<abbr title={card.empty.code}>{card.empty.text}</abbr></>}</p>
                <small>{card.evidence}</small>
                <p>
                  <button type="button" data-action="copy" data-card-id={card.card_id}
                    aria-keyshortcuts={keys.copy.shortcut}>{COPY.copy}</button>
                  <button type="button" data-action="remove" data-card-id={card.card_id}
                    aria-keyshortcuts={keys.remove.shortcut}>{COPY.remove}</button>
                </p>
              </article>)}
        </div>
        <small>{view.synthetic} {view.http}</small>
      </>}
    </div>
  </>;
}
