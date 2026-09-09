import type { ReactNode } from 'react';

export type StatusKind = 'stub' | 'deterministic' | 'agent' | 'synthetic' | 'model_unavailable' | 'ready';

const STATUS_LABEL: Record<StatusKind, string> = {
  stub: 'STUB',
  deterministic: 'DETERMINISTIC_TOOL',
  agent: 'AGENT_TOOL',
  synthetic: 'SYNTHETIC',
  model_unavailable: '模型不可用',
  ready: '就绪',
};

export function StatusBanner({ kind, message }: { kind: StatusKind; message: string }) {
  return (
    <div className="sm-status-banner" data-kind={kind} data-testid="sm-status-banner" role="status" aria-live="polite">
      <p><strong>{STATUS_LABEL[kind]}</strong> · {message}</p>
    </div>
  );
}

export type EvidenceFields = {
  asOf?: string;
  metricVersion?: string;
  dataVersion?: string;
  digest?: string;
  source?: string;
  limitations?: string[];
  unknowns?: string[];
};

export function EvidenceBlock({ asOf, metricVersion, dataVersion, digest, source, limitations = [], unknowns = [], children }: EvidenceFields & { children?: ReactNode }) {
  const shortDigest = digest && digest.length > 16 ? `${digest.slice(0, 8)}…${digest.slice(-8)}` : digest;
  return (
    <section className="sm-evidence" data-testid="sm-evidence" aria-label="证据">
      <h3>证据与局限</h3>
      <p>截数 {asOf ?? '—'} · 指标 {metricVersion ?? '—'} · 数据 {dataVersion ?? '—'}</p>
      <p>来源 {source ?? '—'} · digest {shortDigest ?? '—'}</p>
      {limitations.length > 0 ? <p>局限：{limitations.join('；')}</p> : <p>局限未提供。</p>}
      {unknowns.length > 0 ? <p>未知项：{unknowns.join('；')}</p> : null}
      {children}
    </section>
  );
}

export type ConditionChip = { id: string; label: string; value: string };

export function ConditionChips({ items }: { items: readonly ConditionChip[] }) {
  return (
    <div className="sm-condition-chips" data-testid="sm-condition-chips" aria-label="条件摘要">
      {items.map(item => (
        <span key={item.id} data-chip={item.id}>{item.label} {item.value}</span>
      ))}
    </div>
  );
}
