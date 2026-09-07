import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import type { components } from '../query-run-contract.generated.js';
import { QUERY_RECEIPT_SCHEMA, decodeQueryReceipt } from '../query-model.mjs';
import { formatEmptyReason, formatFenYuan, formatRatioPercent } from '../query-format.mjs';

type Receipt = components['schemas']['AnalyticsQueryNativeReceipt'];
type Counts = components['schemas']['ChannelFollowupCounts'];

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

export function QueryToolCard({ block }: ToolCallViewProps) {
  if (!('kind' in block) || block.kind !== 'tool-result') {
    return <div className="analytics-b0-card analytics-query-card" role="status" data-query-fault="running">合成查询运行中…</div>;
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
  </div>;
}
