import { useEffect, useRef, useState } from 'react';
import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import type { components } from '../query-run-contract.generated.js';
import { QUERY_RECEIPT_SCHEMA, decodeQueryReceipt } from '../query-model.mjs';
import { formatEmptyReason, formatFenYuan, formatRatioPercent } from '../query-format.mjs';
import { QUERY_CANCEL_COPY, classifyCancelOutcome, sessionCancelEnvelope } from '../query-cancel.mjs';
import {
  addIntentKey, assetRequest, dashboardContainsAnalysis, decodeAssetError, decodeHttpDashboard, probeAssetHttp,
} from '../asset-http.mjs';

type Receipt = components['schemas']['AnalyticsQueryNativeReceipt'];
type Counts = components['schemas']['ChannelFollowupCounts'];
type CancelPhase = 'idle' | 'submitting' | 'accepted' | 'error';

function countsLine(label: string, row: Counts) {
  const repeat = formatRatioPercent(row.channel_repeat_ratio);
  const cross = formatRatioPercent(row.channel_cross_channel_ratio);
  const paid = formatFenYuan(row.channel_window_net_paid_minor);
  const empty = formatEmptyReason(row.channel_empty_reason);
  if (repeat === null || cross === null || paid === null || empty === null) return null;
  return {
    text: `${label}：成熟 ${row.channel_mature_cohort_count} / 未成熟 ${row.channel_immature_count} / 二单 ${row.channel_repeat_count} / 跨渠道 ${row.channel_cross_channel_count} · 二单率 ${repeat} · 跨渠道率 ${cross} · 净支付 ${paid}`,
    empty,
  };
}

function queryFaultKind(block: ToolCallViewProps['block']): 'running' | 'tool-error' | 'unknown-version' | 'malformed' | 'ok' {
  if (!('kind' in block) || block.kind !== 'tool-result') return 'running';
  if (block.isError) return 'tool-error';
  if (decodeQueryReceipt(block.meta)) return 'ok';
  const meta = block.meta;
  const version = meta && typeof meta === 'object' && !Array.isArray(meta) && 'schema_version' in meta
    ? (meta as { schema_version?: unknown }).schema_version : undefined;
  return typeof version === 'string' && version !== QUERY_RECEIPT_SCHEMA ? 'unknown-version' : 'malformed';
}

function cardSessionId(props: ToolCallViewProps): string | null {
  const value = (props as { sessionId?: unknown }).sessionId;
  return typeof value === 'string' && value ? value : null;
}

export function QueryToolCard(props: ToolCallViewProps) {
  const { block } = props;
  const sessionId = cardSessionId(props);
  const callId = block.callId;
  const [phase, setPhase] = useState<CancelPhase>('idle');
  const phaseRef = useRef<CancelPhase>('idle');
  const generationRef = useRef(0);

  useEffect(() => {
    generationRef.current += 1;
    phaseRef.current = 'idle';
    setPhase('idle');
  }, [callId]);

  async function submitCancel() {
    if (phaseRef.current === 'submitting' || phaseRef.current === 'accepted') return;
    const targetSession = sessionId;
    const gen = generationRef.current;
    phaseRef.current = 'submitting';
    setPhase('submitting');
    let outcome: CancelPhase = 'error';
    try {
      if (targetSession) {
        const response = await fetch('/api/session/cancel', {
          method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(sessionCancelEnvelope(targetSession, `query-cancel-${Date.now()}`)),
        });
        let body: unknown = null;
        try { body = await response.json(); } catch { body = null; }
        outcome = classifyCancelOutcome({ status: response.status, body });
      }
    } catch {
      outcome = 'error';
    }
    if (generationRef.current !== gen) return;
    phaseRef.current = outcome;
    setPhase(outcome);
  }

  if (!('kind' in block) || block.kind !== 'tool-result') {
    const busy = phase === 'submitting' || phase === 'accepted';
    const status = phase === 'idle' ? null : QUERY_CANCEL_COPY[phase];
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault="running" data-cancel-state={phase}>
      合成查询运行中…
      <button type="button" data-testid="analytics-query-cancel" disabled={busy}
        onClick={() => { void submitCancel(); }}>停止查询</button>
      {status && <small data-testid="analytics-query-cancel-status">{status}</small>}
    </div>;
  }
  if (block.isError) {
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault="tool-error">查询工具失败；没有可用结果。未执行业务动作。</div>;
  }
  const receipt = decodeQueryReceipt(block.meta) as Receipt | null;
  if (!receipt) {
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault={queryFaultKind(block)}>查询结果格式无法识别或版本不支持；不推断分析成功。</div>;
  }
  const facts = receipt.result.facts;
  const filters = receipt.result.resolved_filters;
  const rows = [
    countsLine('全体', facts.totals),
    ...facts.channels.map(row => countsLine(`渠道 ${row.channel_id}`, row)),
  ];
  if (rows.some(row => row === null)) {
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault="malformed">查询结果格式无法识别或版本不支持；不推断分析成功。</div>;
  }
  const lines = rows.filter(row => row !== null);
  return <div className="analytics-b0-card analytics-query-card" data-testid="analytics-query-tool-result"
    data-query-fault="ok" data-observation-days={facts.observation_days} data-run-id={receipt.run_id} data-step-id={receipt.step_id}>
    <strong>SYNTHETIC · 合成渠道后续购买</strong>
    <p>FIXED 首单区间 {filters.resolved_cohort_start} → {filters.resolved_cohort_end} · N={facts.observation_days} · as_of {receipt.result.as_of}</p>
    {lines.map(row => <p key={row.text}>{row.text}{row.empty.code && <>
      {' · '}<abbr title={row.empty.code}>{row.empty.text}</abbr></>}</p>)}
    <small>result_ref {receipt.run_id}/{receipt.step_id} · {receipt.result.data_source} · 不是真实业务数据。</small>
    <QuerySaveActions runId={receipt.run_id} days={facts.observation_days} />
  </div>;
}

function QuerySaveActions({ runId, days }: { runId: string; days: number }) {
  const [available, setAvailable] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'saving' | 'saved' | 'joining' | 'joined' | 'join-error'>('idle');
  const [analysis, setAnalysis] = useState<{ analysis_id: string; version: number } | null>(null);
  const [status, setStatus] = useState('');
  const joinAttempt = useRef<{ dashboardId: string; key: string; etag: number } | null>(null);
  useEffect(() => { void probeAssetHttp().then(setAvailable); }, [runId]);
  if (!available) return null;

  async function save() {
    if (phase === 'saving' || phase === 'joining') return;
    setPhase('saving');
    try {
      const title = `渠道后续购买 N=${days}`;
      const row = await assetRequest('/b0/analyses', {
        method: 'POST', body: { created_from_run_id: runId, title }, key: `save-${runId}`,
      });
      if (row.status !== 201 && row.status !== 200) {
        setPhase('idle');
        setStatus(decodeAssetError(row.payload).message);
        return;
      }
      if (typeof row.payload?.analysis_id !== 'string' || typeof row.payload?.version !== 'number') {
        setPhase('idle');
        setStatus('资产请求失败。');
        return;
      }
      const saved = { analysis_id: row.payload.analysis_id, version: row.payload.version };
      setAnalysis(saved);
      setPhase('saved');
      setStatus('已保存当前口径和本次快照。不附带营销批准。');
      window.dispatchEvent(new CustomEvent('analytics-asset-changed'));
    } catch {
      setPhase('idle');
      setStatus('资产请求失败。');
    }
  }

  async function join() {
    if (!analysis || phase === 'joining' || phase === 'joined') return;
    setPhase('joining');
    try {
      let attempt = phase === 'join-error' ? joinAttempt.current : null;
      if (!attempt) {
        const listed = await assetRequest('/b0/dashboards');
        if (listed.status !== 200) {
          setPhase('join-error');
          setStatus(`分析已保存；加入驾驶舱失败。${decodeAssetError(listed.payload).message}`);
          return;
        }
        let dashboard = Array.isArray(listed.payload?.items) ? listed.payload.items[0] : undefined;
        if (!dashboard) {
          const created = await assetRequest('/b0/dashboards', {
            method: 'POST', body: { title: '我的驾驶舱' }, key: 'board-owner',
          });
          if (created.status !== 200 && created.status !== 201) {
            setPhase('join-error');
            setStatus(decodeAssetError(created.payload).message);
            return;
          }
          dashboard = decodeHttpDashboard(created.payload);
        }
        const dashboardId = dashboard?.dashboard_id;
        const version = dashboard?.version;
        const key = typeof dashboardId === 'string' && typeof version === 'number'
          ? addIntentKey(analysis.analysis_id, analysis.version, version) : null;
        if (typeof dashboardId !== 'string' || typeof version !== 'number' || !key) {
          setPhase('join-error');
          setStatus('分析已保存；加入驾驶舱失败。资产请求失败。');
          return;
        }
        attempt = { dashboardId, key, etag: version };
        joinAttempt.current = attempt;
      }
      const added = await assetRequest(`/b0/dashboards/${attempt.dashboardId}/versions`, {
        method: 'POST',
        body: { op: 'add', analysis_ref: { analysis_id: analysis.analysis_id, version: analysis.version } },
        key: attempt.key,
        etag: attempt.etag,
      });
      if (added.status === 409) {
        const current = await assetRequest(`/b0/dashboards/${attempt.dashboardId}`);
        if (dashboardContainsAnalysis(current.payload, analysis.analysis_id, analysis.version)) {
          setPhase('joined');
          setStatus('已加入我的驾驶舱。');
          window.dispatchEvent(new CustomEvent('analytics-asset-changed'));
          return;
        }
        joinAttempt.current = null;
        setPhase('join-error');
        setStatus(`分析已保存；加入驾驶舱失败。${decodeAssetError(added.payload).message}`);
        return;
      }
      if (added.status !== 200 && added.status !== 201) {
        setPhase('join-error');
        setStatus(`分析已保存；加入驾驶舱失败。${decodeAssetError(added.payload).message}`);
        return;
      }
      setPhase('joined');
      setStatus('已加入我的驾驶舱。');
      window.dispatchEvent(new CustomEvent('analytics-asset-changed'));
    } catch {
      setPhase('join-error');
      setStatus('分析已保存；加入驾驶舱失败。资产请求失败。');
    }
  }

  return <div data-testid="analytics-query-save">
    <button type="button" data-testid="analytics-query-save-button" disabled={phase === 'saving' || phase === 'joining'}
      onClick={() => { void save(); }}>保存分析</button>
    <button type="button" data-testid="analytics-query-join-button"
      disabled={!analysis || phase === 'joining' || phase === 'joined'} onClick={() => { void join(); }}>加入我的驾驶舱</button>
    {status && <small data-testid="analytics-query-save-status">{status}</small>}
  </div>;
}
