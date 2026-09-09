import { useEffect, useRef, useState } from 'react';
import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import {
  FIRST_PURCHASE_RECEIPT_SCHEMA, decodeFirstPurchaseReceipt, firstPurchaseSaveBinding,
  type FirstPurchaseNativeReceipt, type FirstPurchaseProductRow,
} from '../first-purchase-query-model.mjs';
import { formatEmptyReason, formatRatioPercent } from '../query-format.mjs';
import { QUERY_CANCEL_COPY, classifyCancelOutcome, sessionCancelEnvelope } from '../query-cancel.mjs';
import {
  addIntentKey, assetRequest, dashboardContainsAnalysis, decodeAssetError, decodeHttpDashboard, probeAssetHttp,
} from '../asset-http.mjs';

type CancelPhase = 'idle' | 'submitting' | 'accepted' | 'error';

function productLine(row: FirstPurchaseProductRow) {
  const ratio = formatRatioPercent(row.finished_conversion_ratio);
  const empty = formatEmptyReason(row.empty_reason);
  if (ratio === null || empty === null) return null;
  return {
    productId: row.product_id,
    text: `${row.product_id}（${row.role}）：入组 ${row.enrolled_count} / 成熟 ${row.mature_count} / 未成熟 ${row.immature_count} / 正装转化 ${row.finished_conversion_count} · 转化率 ${ratio}`,
    empty,
    ratio,
  };
}

function faultKind(block: ToolCallViewProps['block']): 'running' | 'in-flight' | 'tool-error' | 'cancelled' | 'unknown-version' | 'malformed' | 'ok' | 'contract-rejected' {
  if (!('kind' in block) || block.kind !== 'tool-result') return 'running';
  if (block.isError) {
    const text = Array.isArray(block.content) ? block.content.map(item => 'text' in item ? String(item.text) : '').join(' ') : '';
    return text.includes('cancelled') || text.includes('已取消') ? 'cancelled' : 'tool-error';
  }
  const receipt = decodeFirstPurchaseReceipt(block.meta);
  if (receipt?.disposition === 'IN_FLIGHT') return 'in-flight';
  if (receipt?.result?.status === 'REJECTED') return 'contract-rejected';
  if (receipt) return 'ok';
  const meta = block.meta;
  const version = meta && typeof meta === 'object' && !Array.isArray(meta) && 'schema_version' in meta
    ? (meta as { schema_version?: unknown }).schema_version : undefined;
  return typeof version === 'string' && version !== FIRST_PURCHASE_RECEIPT_SCHEMA ? 'unknown-version' : 'malformed';
}

function cardSessionId(props: ToolCallViewProps): string | null {
  const value = (props as { sessionId?: unknown }).sessionId;
  return typeof value === 'string' && value ? value : null;
}

function RunningCard({
  phase, onCancel, inFlight,
}: { phase: CancelPhase; onCancel: () => void; inFlight: boolean }) {
  const busy = phase === 'submitting' || phase === 'accepted';
  const status = phase === 'idle' ? null : QUERY_CANCEL_COPY[phase];
  return <div className="analytics-b0-card analytics-query-card" role="status"
    data-query-fault={inFlight ? 'in-flight' : 'running'} data-cancel-state={phase}>
    {inFlight ? '合成首购查询仍在途…' : '合成首购查询运行中…'}
    <button type="button" data-testid="analytics-first-purchase-cancel" disabled={busy}
      onClick={onCancel}>停止查询</button>
    {status && <small data-testid="analytics-first-purchase-cancel-status">{status}</small>}
  </div>;
}

export function FirstPurchaseQueryCard(props: ToolCallViewProps) {
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
          body: JSON.stringify(sessionCancelEnvelope(targetSession, `fp-query-cancel-${Date.now()}`)),
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
    return <RunningCard phase={phase} inFlight={false} onCancel={() => { void submitCancel(); }} />;
  }
  if (block.isError) {
    const kind = faultKind(block);
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault={kind}>
      {kind === 'cancelled' ? '首购查询已取消；没有可用结果。未执行业务动作。' : '首购查询失败；没有可用结果。未执行业务动作。'}
    </div>;
  }
  const receipt = decodeFirstPurchaseReceipt(block.meta) as FirstPurchaseNativeReceipt | null;
  if (receipt?.disposition === 'IN_FLIGHT') {
    return <RunningCard phase={phase} inFlight onCancel={() => { void submitCancel(); }} />;
  }
  if (!receipt) {
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault={faultKind(block)}>查询结果格式无法识别或版本不支持；不推断分析成功。</div>;
  }
  if (receipt.result?.status === 'REJECTED') {
    const missing = receipt.result.missing_product_ids.join(', ');
    return <div className="analytics-b0-card analytics-query-card" role="status"
      data-query-fault="contract-rejected" data-reason-code="MISSING_PRODUCT_ROLE"
      data-run-id={receipt.run_id} data-conversion-metric="0">
      <strong>SYNTHETIC · 首购商品路径合同拒绝</strong>
      <p>商品角色映射缺失（{missing}）。整单拒绝，不展示转化率或 0%。</p>
      <small>result_ref {receipt.run_id} · 不是真实业务数据。保存分析只能引用该 run，不能引用卡片数字。</small>
    </div>;
  }
  const facts = receipt.result?.facts;
  if (!facts || receipt.result?.status !== 'OK') {
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault="malformed">查询结果格式无法识别或版本不支持；不推断分析成功。</div>;
  }
  const rows = facts.products.map(productLine);
  if (rows.some(row => row === null)) {
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault="malformed">查询结果格式无法识别或版本不支持；不推断分析成功。</div>;
  }
  const binding = firstPurchaseSaveBinding(receipt.run_id);
  return <div className="analytics-b0-card analytics-query-card" data-testid="analytics-first-purchase-tool-result"
    data-query-fault="ok" data-observation-days={facts.observation_days} data-run-id={receipt.run_id}
    data-save-run-id={binding?.created_from_run_id} data-save-source="first-purchase-run">
    <strong>SYNTHETIC · 首购商品路径 / N日正装转化</strong>
    <p>FIXED 入组窗 · N={facts.observation_days} · as_of {receipt.result.as_of} · 入组 {facts.cohort_enrolled_count} / 成熟 {facts.cohort_mature_count}</p>
    {rows.filter(row => row !== null).map(row => <p key={row.productId} data-conversion-metric="1">{row.text}{row.empty.code && <>
      {' · '}<abbr title={row.empty.code}>{row.empty.text}</abbr></>}</p>)}
    <small>result_ref {receipt.run_id} · {receipt.result.data_source} · 保存分析仅传递 created_from_run_id，不把卡片 facts 当作可信来源。</small>
    <FirstPurchaseSaveActions runId={receipt.run_id} days={facts.observation_days} />
  </div>;
}

type SavePhase = 'idle' | 'saving' | 'saved' | 'joining' | 'joined' | 'join-error';

function FirstPurchaseSaveActions({ runId, days }: { runId: string; days: number }) {
  const [available, setAvailable] = useState(false);
  const [phase, setPhase] = useState<SavePhase>('idle');
  const [analysis, setAnalysis] = useState<{ analysis_id: string; version: number } | null>(null);
  const [status, setStatus] = useState('');
  const joinAttempt = useRef<{ dashboardId: string; key: string; etag: number } | null>(null);
  const phaseRef = useRef<SavePhase>('idle');
  const analysisRef = useRef<{ analysis_id: string; version: number } | null>(null);
  useEffect(() => { void probeAssetHttp().then(setAvailable); }, [runId]);
  if (!available) return null;

  function go(next: SavePhase) {
    phaseRef.current = next;
    setPhase(next);
  }

  const saveLocked = analysis !== null || phase === 'saving' || phase === 'joining'
    || phase === 'saved' || phase === 'join-error' || phase === 'joined';

  async function save() {
    if (analysisRef.current || phaseRef.current === 'saving' || phaseRef.current === 'joining'
      || phaseRef.current === 'saved' || phaseRef.current === 'join-error' || phaseRef.current === 'joined') {
      return;
    }
    go('saving');
    try {
      const title = `首购商品路径 N=${days}`;
      const row = await assetRequest('/b0/analyses', {
        method: 'POST', body: { created_from_run_id: runId, title }, key: `save-${runId}`,
      });
      if (row.status !== 201 && row.status !== 200) {
        go('idle');
        setStatus(decodeAssetError(row.payload).message);
        return;
      }
      if (typeof row.payload?.analysis_id !== 'string' || typeof row.payload?.version !== 'number') {
        go('idle');
        setStatus('资产请求失败。');
        return;
      }
      const saved = { analysis_id: row.payload.analysis_id, version: row.payload.version };
      analysisRef.current = saved;
      setAnalysis(saved);
      go('saved');
      setStatus('已保存当前口径和本次快照。不附带营销批准。');
      window.dispatchEvent(new CustomEvent('analytics-asset-changed'));
    } catch {
      go('idle');
      setStatus('资产请求失败。');
    }
  }

  async function join() {
    const saved = analysisRef.current;
    if (!saved || phaseRef.current === 'joining' || phaseRef.current === 'joined') return;
    go('joining');
    try {
      let attempt = joinAttempt.current;
      if (!attempt) {
        const listed = await assetRequest('/b0/dashboards');
        if (listed.status !== 200) {
          go('join-error');
          setStatus(`分析已保存；加入驾驶舱失败。${decodeAssetError(listed.payload).message}`);
          return;
        }
        let dashboard = Array.isArray(listed.payload?.items) ? listed.payload.items[0] : undefined;
        if (!dashboard) {
          const created = await assetRequest('/b0/dashboards', {
            method: 'POST', body: { title: '我的首购驾驶舱' }, key: 'board-owner',
          });
          if (created.status !== 200 && created.status !== 201) {
            go('join-error');
            setStatus(decodeAssetError(created.payload).message);
            return;
          }
          dashboard = decodeHttpDashboard(created.payload);
        }
        const dashboardId = dashboard?.dashboard_id;
        const version = dashboard?.version;
        const key = typeof dashboardId === 'string' && typeof version === 'number'
          ? addIntentKey(saved.analysis_id, saved.version, version) : null;
        if (typeof dashboardId !== 'string' || typeof version !== 'number' || !key) {
          go('join-error');
          setStatus('分析已保存；加入驾驶舱失败。资产请求失败。');
          return;
        }
        attempt = { dashboardId, key, etag: version };
        joinAttempt.current = attempt;
      }
      const added = await assetRequest(`/b0/dashboards/${attempt.dashboardId}/versions`, {
        method: 'POST',
        body: { op: 'add', analysis_ref: { analysis_id: saved.analysis_id, version: saved.version } },
        key: attempt.key,
        etag: attempt.etag,
      });
      if (added.status === 409) {
        const current = await assetRequest(`/b0/dashboards/${attempt.dashboardId}`);
        if (dashboardContainsAnalysis(current.payload, saved.analysis_id, saved.version)) {
          go('joined');
          setStatus('已加入我的驾驶舱。');
          window.dispatchEvent(new CustomEvent('analytics-asset-changed'));
          return;
        }
        const decoded = decodeHttpDashboard(current.payload);
        if (decoded) {
          const nextKey = addIntentKey(saved.analysis_id, saved.version, decoded.version);
          if (nextKey) {
            joinAttempt.current = { dashboardId: decoded.dashboard_id, key: nextKey, etag: decoded.version };
          }
        }
        go('join-error');
        setStatus(`分析已保存；加入驾驶舱失败。${decodeAssetError(added.payload).message}`);
        return;
      }
      if (added.status !== 200 && added.status !== 201) {
        go('join-error');
        setStatus(`分析已保存；加入驾驶舱失败。${decodeAssetError(added.payload).message}`);
        return;
      }
      go('joined');
      setStatus('已加入我的驾驶舱。');
      window.dispatchEvent(new CustomEvent('analytics-asset-changed'));
    } catch {
      go('join-error');
      setStatus('分析已保存；加入驾驶舱失败。资产请求失败。');
    }
  }

  return <div data-testid="analytics-first-purchase-save">
    <button type="button" data-testid="analytics-first-purchase-save-button" disabled={saveLocked}
      onClick={() => { void save(); }}>保存分析</button>
    <button type="button" data-testid="analytics-first-purchase-join-button"
      disabled={!analysis || phase === 'joining' || phase === 'joined'} onClick={() => { void join(); }}>加入我的驾驶舱</button>
    {status && <small data-testid="analytics-first-purchase-save-status">{status}</small>}
  </div>;
}
