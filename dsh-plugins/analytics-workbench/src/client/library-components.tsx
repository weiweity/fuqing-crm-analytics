import { useEffect, useState } from 'react';
import type { ComponentSeries, ComponentTable, ComponentView, WaterfallContent, FunnelContent } from '../board-spec/component-view.mjs';
import { waterfallGeometry } from '../../../shine-waterfall/src/waterfall.mjs';
import { funnelGeometry } from '../../../shine-funnel/src/funnel.mjs';
import { ProcessDiagram, TimelineDiagram, libraryDiagramCss } from './library-diagrams.tsx';

/** Brand comes exclusively from the enclosing competition ThemeProvider. */
export const libraryComponentCss = `
${libraryDiagramCss}
.sm-library { min-width:0; display:flex; flex-direction:column; gap:var(--sm-library-gap,12px); font:14px/1.5 var(--sm-font-body); overflow-wrap:anywhere; }
.sm-library[data-density="compact"] { --sm-library-gap:8px; font-size:13px; }
.sm-library[data-tone="accent"] { border-inline-start:3px solid var(--sm-purple); padding-inline-start:12px; }
.sm-library[data-tone="muted"] { background:var(--sm-glass); }
.sm-library p,.sm-library figure { margin:0; }
.sm-library-note { color:var(--sm-muted); font-size:12px; }
.sm-library-error { color:var(--sm-danger); }
.sm-library-value { font:500 32px/1.25 var(--sm-font-display); font-variant-numeric:tabular-nums; }
.sm-library-text { white-space:pre-wrap; }
.sm-library-text[data-style="callout"] { border-inline-start:3px solid var(--sm-purple); padding:12px; background:var(--sm-nav-active); }
.sm-library-chart { display:block; width:100%; height:auto; min-width:0; color:var(--sm-purple); }
.sm-library-legend { display:flex; flex-wrap:wrap; gap:8px 16px; color:var(--sm-muted); font-size:12px; }
.sm-library-bars { display:flex; flex-direction:column; gap:12px; }
.sm-library-bar-label { display:flex; justify-content:space-between; gap:12px; }
.sm-library-track { position:relative; height:12px; background:var(--sm-nav-active); }
.sm-library-fill { position:absolute; top:0; bottom:0; background:var(--sm-purple); }
.sm-library-zero { position:absolute; height:100%; border-inline-start:1px solid var(--sm-muted); }
.sm-library-table-wrap { overflow:auto; max-width:100%; }
.sm-library table { border-collapse:collapse; width:100%; font-size:inherit; }
.sm-library th,.sm-library td { padding:8px 12px; border-bottom:1px solid var(--sm-line); text-align:start; overflow-wrap:anywhere; }
.sm-library td[data-numeric="true"] { text-align:end; font-variant-numeric:tabular-nums; }
.sm-library th { font-weight:600; }
.sm-library-pagination { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.sm-library button { font:inherit; color:var(--sm-ink); background:var(--sm-bg); border:1px solid var(--sm-line); border-radius:6px; min-height:32px; padding:4px 10px; cursor:pointer; }
.sm-library button:disabled { opacity:.5; cursor:default; }
.sm-library :focus-visible { outline:2px solid var(--sm-purple); outline-offset:3px; }
.sm-library dl { margin:0; display:grid; grid-template-columns:minmax(64px,1fr) minmax(0,2fr); gap:8px; }
.sm-library dt { color:var(--sm-muted); } .sm-library dd { margin:0; }
.sm-library-waterfall-scroll { max-width:100%; overflow-x:auto; }
.sm-library-waterfall-scroll svg { display:block; max-width:none; color:var(--sm-ink); }
.sm-library-funnel { margin:12px 0; padding:0; list-style:none; display:flex; flex-direction:column; gap:16px; }
.sm-library-funnel li { min-width:0; display:flex; flex-direction:column; gap:4px; }
.sm-library-funnel-label { display:flex; flex-wrap:wrap; justify-content:space-between; gap:4px 12px; }
.sm-library-funnel-track { display:flex; justify-content:center; height:24px; border-bottom:1px solid var(--sm-line); }
.sm-library-funnel-bar { background:var(--sm-purple); height:100%; }
`;

function format(value: number | string | null, compact = false) {
  if (value === null) return '—';
  if (typeof value === 'string') return value;
  return new Intl.NumberFormat('zh-CN', compact ? { notation: 'compact', maximumSignificantDigits: 4 } : { maximumSignificantDigits: 15 }).format(value);
}

function domain(data: ComponentSeries) {
  const values = data.points.flatMap(point => point.value === null ? [] : [point.value]);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const magnitude = Math.max(1, Math.abs(min), Math.abs(max));
  return { min, max, magnitude, range: max / magnitude - min / magnitude || 1 };
}

function SeriesChart({ kind, data, props }: { kind: string; data: ComponentSeries; props: Record<string, unknown> }) {
  const { min, max, range, magnitude } = domain(data);
  const width = 360, height = 180, pad = 20;
  const x = (index: number) => pad + index * (width - pad * 2) / Math.max(1, data.points.length - 1);
  const position = (value: number) => (value / magnitude - min / magnitude) / range;
  const y = (value: number) => height - pad - position(value) * (height - pad * 2);
  const description = data.points.map(point => `${point.label}：${format(point.value)}`).join('；');
  const zero = position(0) * 100;
  const vertical = props.orientation === 'vertical';
  // Missing points break a line instead of joining across unavailable observations.
  let previous = false;
  const line = data.points.map((point, index) => {
    if (point.value === null) { previous = false; return ''; }
    const path = `${previous ? 'L' : 'M'}${x(index)},${y(point.value)}`;
    previous = true;
    return path;
  }).join(' ');
  return <figure aria-label={`${kind === 'LINE' ? '趋势图' : '对比图'}，${description}`}>
    {kind === 'BAR' && !vertical ? <div className="sm-library-bars">
      {data.points.map(point => <div key={point.label}>
        <div className="sm-library-bar-label"><span>{point.label}</span>{props.show_values ? <span>{format(point.value)}</span> : null}</div>
        <div className="sm-library-track" aria-hidden="true"><i className="sm-library-zero" style={{ left: `${zero}%` }} />
          {point.value === null ? null : <i className="sm-library-fill" style={{ left: `${position(Math.min(0, point.value)) * 100}%`, width: `${Math.abs(point.value / magnitude) / range * 100}%` }} />}
        </div>
      </div>)}
    </div> : <svg className="sm-library-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={description}>
      <title>{kind === 'LINE' ? '趋势' : '对比'} · {data.unit ?? '单位未声明'}</title>
      <line x1={pad} x2={width - pad} y1={y(0)} y2={y(0)} stroke="var(--sm-line-strong)" />
      {kind === 'LINE' ? <>
        <path data-testid="sm-library-line-path" d={line} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray={props.line_style === 'dashed' ? '6 4' : undefined} />
        {props.show_points ? data.points.map((point, index) => point.value === null ? null : <circle key={point.label} cx={x(index)} cy={y(point.value)} r="3" fill="currentColor"><title>{point.label} {format(point.value)}</title></circle>) : null}
      </> : data.points.map((point, index) => point.value === null ? null : <rect key={point.label}
        x={pad + index * (width - pad * 2) / data.points.length + 2} width={Math.max(1, (width - pad * 2) / data.points.length - 4)}
        y={y(Math.max(0, point.value))} height={Math.abs(y(point.value) - y(0))} fill="currentColor"><title>{point.label} {format(point.value)}</title></rect>)}
      <text x={pad} y={12} fill="var(--sm-muted)" fontSize="11">{format(max)}</text>
      <text x={pad} y={height - 2} fill="var(--sm-muted)" fontSize="11">{format(min)}</text>
    </svg>}
    {(kind === 'LINE' && props.show_legend) || (kind === 'BAR' && vertical) ? <figcaption className="sm-library-legend">
      {kind === 'LINE' ? <>
        <span>{data.points[0]?.label} — {data.points.at(-1)?.label}</span>
        <span>{data.points.length} 个数据点 · {data.points.filter(point => point.value === null).length} 个缺失</span>
      </> : data.points.map(point => <span key={point.label}>{point.label}{props.show_values ? ` ${format(point.value)}` : ''}</span>)}
    </figcaption> : null}
    {kind === 'LINE' ? <details>
      <summary>查看趋势数据（{data.points.length} 条）</summary>
      <DetailTable data={{ columns: [{ key: 'label', label: '时间 / 顺序' }, { key: 'value', label: '数值', unit: data.unit }],
        rows: data.points.map(point => ({ label: point.label, value: point.value })) }} pageSize={10} />
    </details> : null}
    <p className="sm-library-note">单位：{data.unit ?? '未声明（原值展示）'}</p>
  </figure>;
}

function FunnelChart({ data, props }: { data: FunnelContent; props: Record<string, unknown> }) {
  const geometry = funnelGeometry(data);
  if (!geometry) return <p role="status">人群计数不符合嵌套关系，不能绘制漏斗</p>;
  const previous = props.rate_basis !== 'first';
  const basis = previous ? '占上一阶段' : '占首阶段';
  const percent = (ratio: number | null) => ratio === null ? '—（无可用分母）'
    : new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 1 }).format(ratio);
  return <figure aria-label="同一人群漏斗">
    <p>{data.cohort_label}</p>
    <p className="sm-library-note">{data.counting_rule}</p>
    <p className="sm-library-note">单位：人 · 条宽按首阶段人数比例；零人数不画假宽度。比例口径：{basis}。</p>
    {geometry.empty ? <p role="status">首阶段人群为空；人数为零，比例不可计算，不显示虚构的 0%。</p> : null}
    <ol className="sm-library-funnel">
      {geometry.stages.map((stage, index) => <li key={stage.label}>
        <div className="sm-library-funnel-label"><span>{index + 1}. {stage.label}</span>
          {props.show_values !== false ? <span data-funnel-count={stage.count}>{format(stage.count)} 人</span> : null}</div>
        <div className="sm-library-funnel-track" aria-hidden="true"><div className="sm-library-funnel-bar" data-funnel-width={stage.width} style={{ width: `${stage.width}%` }} /></div>
        {props.show_rates !== false ? <p className="sm-library-note" data-funnel-rate="true">{basis}：{index === 0 && previous ? '—（首阶段无上一阶段）' : percent(previous ? stage.previous_ratio : stage.first_ratio)}</p> : null}
      </li>)}
    </ol>
    <details><summary>查看人数与比例明细（{geometry.stages.length} 阶段）</summary>
      <DetailTable pageSize={12} data={{ columns: [{ key: 'label', label: '阶段' }, { key: 'count', label: '人数', unit: '人' },
        { key: 'ratio', label: basis }], rows: geometry.stages.map((stage, index) => ({ label: stage.label,
          count: stage.count, ratio: index === 0 && previous ? '—（首阶段无上一阶段）' : percent(previous ? stage.previous_ratio : stage.first_ratio) })) }} />
    </details>
  </figure>;
}

function WaterfallChart({ data, props }: { data: WaterfallContent; props: Record<string, unknown> }) {
  const geometry = waterfallGeometry(data);
  if (!geometry) return <p role="status">贡献未对账，不能绘制瀑布</p>;
  const signed = (amount: number, compact = false) => `${amount > 0 ? '+' : ''}${format(amount, compact)}`;
  const display = (bar: { role: string; value: number }, compact = false) => bar.role === 'total' ? format(bar.value, compact) : signed(bar.value, compact);
  const description = `贡献瀑布，单位${data.unit}。${geometry.bars.map((bar, index) => `${index + 1} ${bar.label}：${display(bar)}`).join('；')}`;
  return <figure aria-label="已对账贡献瀑布">
    <p className="sm-library-note">起止总量与带符号贡献同单位对账；不是因果归因。横向滚动查看全部步骤，序号对应下方明细。</p>
    <div className="sm-library-waterfall-scroll" role="region" aria-label="瀑布图，可用左右方向键横向滚动" tabIndex={0}>
      <svg width={geometry.width} height={geometry.height} viewBox={`0 0 ${geometry.width} ${geometry.height}`} role="img" aria-label={description}>
        <title>{description}</title>
        <line x1={48} x2={geometry.width - 16} y1={geometry.zero} y2={geometry.zero} stroke="var(--sm-line-strong)" />
        <text x={8} y={32} fill="var(--sm-muted)" fontSize={12}>{format(geometry.max, true)}</text>
        <text x={8} y={256} fill="var(--sm-muted)" fontSize={12}>{format(geometry.min, true)}</text>
        {geometry.bars.map((bar, index) => <g key={index} data-role={bar.role} data-value={bar.value} data-from={bar.from} data-to={bar.to}>
          <title>{index + 1} {bar.label}：{display(bar)}；累计 {format(bar.to)}</title>
          {bar.bottom === bar.top ? <line data-zero="true" x1={bar.x} x2={bar.x + bar.width} y1={bar.top} y2={bar.top} stroke="var(--sm-copy)" strokeWidth={2} />
            : <rect x={bar.x} y={bar.top} width={bar.width} height={bar.bottom - bar.top}
                fill={bar.role === 'total' ? 'var(--sm-purple)' : bar.value < 0 ? 'var(--sm-bg)' : 'var(--sm-nav-active)'}
                stroke={bar.role === 'total' ? 'var(--sm-purple)' : 'var(--sm-copy)'} />}
          {index + 1 < geometry.bars.length ? <line data-carry={bar.to} x1={bar.x + bar.width} x2={geometry.bars[index + 1].x}
            y1={bar.carry} y2={bar.carry} stroke="var(--sm-copy)" strokeDasharray="3 3" /> : null}
          {props.show_values ? <text data-value-label="true" x={bar.x + bar.width / 2} y={bar.top - 8} textAnchor="middle" fill="var(--sm-ink)" fontSize={12}>
            {display(bar, String(Math.abs(bar.value)).length > 10)}</text> : null}
          <text x={bar.x + bar.width / 2} y={280} textAnchor="middle" fill="var(--sm-copy)" fontSize={12}>{index + 1}</text>
        </g>)}
      </svg>
    </div>
    <p className="sm-library-note">单位：{data.unit} · 实心为总量、浅填为增加、空心为减少，横线为零；零项不删除。</p>
    <details open={props.show_table !== false}>
      <summary>查看贡献明细（{geometry.bars.length} 步，含起止）</summary>
      <DetailTable pageSize={10} data={{ columns: [{ key: 'step', label: '序号' }, { key: 'label', label: '项目' },
        { key: 'role', label: '类型' }, { key: 'value', label: '总量 / 带符号贡献', unit: data.unit },
        { key: 'to', label: '累计', unit: data.unit }], rows: geometry.bars.map((bar, index) => ({
          step: index + 1, label: bar.label, role: bar.role === 'total' ? '总量' : '贡献', value: display(bar), to: bar.to })) }} />
    </details>
  </figure>;
}

function DetailTable({ data, pageSize }: { data: ComponentTable; pageSize: number }) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [data, pageSize]);
  const pages = Math.max(1, Math.ceil(data.rows.length / pageSize));
  const current = Math.min(page, pages - 1);
  return <>
    <div className="sm-library-table-wrap" tabIndex={0} role="region" aria-label="明细表，可横向滚动">
      <table><caption className="sm-library-note">共 {data.rows.length} 条</caption>
        <thead><tr>{data.columns.map(column => <th key={column.key} scope="col">{column.label}{column.unit ? `（${column.unit}）` : ''}</th>)}</tr></thead>
        <tbody>{data.rows.slice(current * pageSize, (current + 1) * pageSize).map((row, index) => <tr key={index}>
          {data.columns.map(column => <td key={column.key} data-numeric={typeof row[column.key] === 'number'}>{format(row[column.key])}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
    <nav className="sm-library-pagination" aria-label="明细分页">
      <button type="button" disabled={current === 0} onClick={event => { event.stopPropagation(); setPage(current - 1); }}>上一页</button>
      <span aria-live="polite">{current + 1} / {pages}</span>
      <button type="button" disabled={current + 1 >= pages} onClick={event => { event.stopPropagation(); setPage(current + 1); }}>下一页</button>
    </nav>
  </>;
}

export function LibraryComponentBody({ view }: { view: ComponentView }) {
  const props = view.props ?? {};
  let content;
  if (view.status !== 'ready') content = <p role="status" className={view.status === 'error' ? 'sm-library-error' : 'sm-library-note'}>{view.message ?? '内容暂不可用'}</p>;
  else if (view.kind === 'METRIC' && view.scalar) content = <>
    <p className="sm-library-value" data-testid="sm-library-metric-value">{format(view.scalar.value, props.value_format === 'compact')}</p>
    <p className="sm-library-note">单位：{view.scalar.unit ?? '未声明（原值展示）'}</p>
    {props.show_comparison ? <p className="sm-library-note">对比期：{format(view.scalar.comparison ?? null)}</p> : null}
  </>;
  else if ((view.kind === 'LINE' || view.kind === 'BAR') && view.series) content = <SeriesChart kind={view.kind} data={view.series} props={props} />;
  else if (view.kind === 'TABLE' && view.table) content = <DetailTable data={view.table} pageSize={typeof props.page_size === 'number' ? props.page_size : 10} />;
  else if (view.kind === 'PROCESS' && view.process) content = <ProcessDiagram content={view.process} showOwners={props.show_owners !== false} showDetails={props.show_details !== false} />;
  else if (view.kind === 'TIMELINE' && view.timeline) content = <TimelineDiagram content={view.timeline} timezone={String(props.timezone)} showDetails={props.show_details !== false} />;
  else if (view.kind === 'WATERFALL' && view.waterfall) content = <WaterfallChart data={view.waterfall} props={props} />;
  else if (view.kind === 'FUNNEL' && view.funnel) content = <FunnelChart data={view.funnel} props={props} />;
  else if (view.kind === 'TEXT') content = <div className="sm-library-text" data-style={String(props.text_style)} style={{ textAlign: props.align === 'center' ? 'center' : 'start' }}>
    {String(props.content ?? '')}<p className="sm-library-note">说明文本 · 非核验经营数字</p>
  </div>;
  else if (view.kind === 'EVIDENCE' && view.evidence) content = <>
    {props.summary ? <p>{String(props.summary)}<span className="sm-library-note">（说明，非来源原文）</span></p> : null}
    <p>{view.evidence.source_label}</p>
    {props.expanded ? <dl>{view.evidence.items.map((item, index) => <div key={index} style={{ display: 'contents' }}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl> : null}
  </>;
  else content = <p role="status">组件内容尚未支持</p>;
  return <div className="sm-library" data-testid={`sm-library-${view.kind?.toLowerCase()}`} data-state={view.status} data-density={String(props.density ?? 'comfortable')} data-tone={String(props.tone ?? 'neutral')}>
    {props.subtitle ? <p className="sm-library-note">{String(props.subtitle)}</p> : null}
    {content}
    {view.source_result_id && view.kind !== 'TEXT' ? <p className="sm-library-note">结果：{view.source_result_id}</p> : null}
  </div>;
}
