import { useId, useRef } from 'react';
import type { ProcessContent, TimelineContent } from '../board-spec/component-view.mjs';
import { processGeometry } from '../board-spec/structured-content.mjs';

/** Editable document content only; no tool execution, foreign HTML or remote assets. */
export const libraryDiagramCss = `
.sm-process-nodes,.sm-timeline-events { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:16px; }
.sm-process-nodes > li { border:1px solid var(--sm-line); border-inline-start:3px solid var(--sm-purple); padding:12px; border-radius:6px; }
.sm-process-heading { display:flex; align-items:baseline; gap:8px; }
.sm-process-heading strong { flex:1; font-weight:500; }
.sm-process-edges { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
.sm-process-node-number,.sm-timeline-event-number { font:500 12px var(--sm-font-display); color:var(--sm-purple); }
.sm-process-detail,.sm-timeline-detail { white-space:pre-wrap; margin-top:8px !important; }
.sm-process-map-wrap { overflow:auto; max-height:440px; margin-bottom:16px; border-bottom:1px solid var(--sm-line); }
.sm-process-map { display:block; }
.sm-process-map [role=button] { cursor:pointer; outline:none; }
.sm-process-map [role=button]:focus rect { stroke:var(--sm-purple); stroke-width:3px; }
.sm-timeline-axis-wrap { overflow:auto; }
.sm-timeline-axis { display:block; min-width:360px; width:100%; height:auto; color:var(--sm-purple); }
.sm-timeline-events > li { display:grid; grid-template-columns:104px minmax(0,1fr); gap:12px; border-top:1px solid var(--sm-line); padding-top:12px; }
.sm-timeline-events time { color:var(--sm-muted); font-variant-numeric:tabular-nums; font-size:12px; }
.sm-timeline-events ul { padding-inline-start:16px; margin:4px 0 0; }
.sm-timeline-events li li + li { margin-top:12px; }
`;

export function ProcessDiagram({ content, showOwners, showDetails }: {
  content: ProcessContent; showOwners: boolean; showDetails: boolean;
}) {
  const id = useId(), targets = useRef(new Map<string, HTMLLIElement>());
  const nodes = new Map(content.nodes.map((node, index) => [node.id, { ...node, number: index + 1 }]));
  const geometry = processGeometry(content), arrow = `process-arrow-${id.replace(/[^a-zA-Z0-9_-]/g, '_')}`;
  const focusNode = (nodeId: string) => {
    const target = targets.current.get(nodeId);
    target?.focus({ preventScroll: true }); target?.scrollIntoView({ block: 'nearest', behavior: 'auto' });
  };
  return <section aria-label="可编辑流程说明">
    <p className="sm-library-note">规划说明 · 非已核验 SOP，不执行任务。节点排列不代表执行顺序，以显式连线为准。</p>
    <div className="sm-process-map-wrap" tabIndex={0} role="region" aria-label="流程连接图，可滚动；节点可跳转到完整说明">
      <svg className="sm-process-map" width={geometry.width} height={geometry.height}
        viewBox={`0 0 ${geometry.width} ${geometry.height}`} role="group" aria-label="带方向的节点连接图">
        <defs><marker id={arrow} viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" orient="auto" markerUnits="userSpaceOnUse">
          <path d="M 0 0 L 8 4 L 0 8 Z" fill="var(--sm-purple)" />
        </marker></defs>
        {geometry.edges.map(edge => <g key={edge.number} data-process-edge={edge.number}>
          <path d={edge.path} fill="none" stroke="var(--sm-purple)" strokeWidth="1.5" markerEnd={`url(#${arrow})`} />
          <circle cx={edge.x} cy={edge.y} r="9" fill="var(--sm-bg)" stroke="var(--sm-line)" />
          <text x={edge.x} y={edge.y + 3} textAnchor="middle" fontSize="9" fill="var(--sm-ink)">{edge.number}</text>
          <title>{nodes.get(edge.from)?.label} → {nodes.get(edge.to)?.label}{edge.label ? `：${edge.label}` : ''}</title>
        </g>)}
        {geometry.nodes.map(node => <g key={node.id} role="button" tabIndex={0} aria-controls={`${id}-${node.id}`}
          aria-label={`查看节点 ${node.number}：${node.label}`} onClick={event => { event.stopPropagation(); focusNode(node.id); }}
          onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); focusNode(node.id); } }}>
          <rect x={node.x} y={node.y} width={node.w} height={node.h} rx="6" fill="var(--sm-bg)" stroke="var(--sm-line-strong)" />
          <text x={node.x + 12} y={node.y + 31} fontSize="13" fill="var(--sm-ink)">
            {node.number}. {Array.from(node.label).length > 12 ? Array.from(node.label).slice(0, 12).join('') + '…' : node.label}
          </text><title>{node.label}</title>
        </g>)}
      </svg>
    </div>
    <ol className="sm-process-nodes">{content.nodes.map((node, index) => {
      const edges = content.edges.filter(edge => edge.from === node.id);
      return <li key={node.id} id={`${id}-${node.id}`} tabIndex={-1} data-process-node={node.id}
        ref={element => { if (element) targets.current.set(node.id, element); else targets.current.delete(node.id); }}>
        <div className="sm-process-heading"><span className="sm-process-node-number">{index + 1}</span><strong>{node.label}</strong></div>
        {showOwners ? <p className="sm-library-note">参与者：{node.owner || '未指定'}</p> : null}
        {showDetails && node.detail ? <p className="sm-process-detail">{node.detail}</p> : null}
        {edges.length ? <nav className="sm-process-edges" aria-label={`${node.label}的后续连线`}>
          {edges.map((edge, edgeIndex) => <button type="button" key={edgeIndex}
            aria-controls={`${id}-${edge.to}`} onClick={event => {
              event.stopPropagation(); focusNode(edge.to);
            }}>连线 {content.edges.indexOf(edge) + 1} → {nodes.get(edge.to)?.number}. {nodes.get(edge.to)?.label}{edge.label ? `（${edge.label}）` : ''}</button>)}
        </nav> : <p className="sm-library-note">没有后续连线</p>}
      </li>;
    })}</ol>
  </section>;
}

export function TimelineDiagram({ content, timezone, showDetails }: {
  content: TimelineContent; timezone: string; showDetails: boolean;
}) {
  const axis = 28 + content.lanes * 28;
  const first = content.groups[0]?.date, last = content.groups.at(-1)?.date;
  return <section aria-label="可编辑日期时间线">
    <p className="sm-library-note">日期规划说明 · 非核验经营事实；{timezone} 日历日，不推测具体时刻。</p>
    <div className="sm-timeline-axis-wrap" tabIndex={0} role="region" aria-label="按真实日期间隔绘制的时间轴">
      <svg className="sm-timeline-axis" viewBox={`0 0 400 ${axis + 28}`} role="img" aria-label={`${first} 至 ${last}，同日事件合并标记，编号对应下方完整内容`}>
        <line x1="24" x2="376" y1={axis} y2={axis} stroke="var(--sm-line-strong)" />
        {content.groups.map(group => {
          const x = 24 + group.position * 352, y = axis - 20 - group.lane * 28;
          return <g key={group.date} data-timeline-date={group.date} data-position={group.position}>
            <line x1={x} x2={x} y1={y + 10} y2={axis} stroke="var(--sm-line-strong)" />
            <circle cx={x} cy={y} r="11" fill="var(--sm-purple)" />
            <text x={x} y={y + 4} textAnchor="middle" fontSize="11" fill="var(--sm-bg)">{group.number}</text>
            <title>{group.date} · {group.events.length} 项</title>
          </g>;
        })}
        <text x="24" y={axis + 20} fontSize="11" fill="var(--sm-muted)">{first}</text>
        {last !== first ? <text x="376" y={axis + 20} textAnchor="end" fontSize="11" fill="var(--sm-muted)">{last}</text> : null}
      </svg>
    </div>
    <ol className="sm-timeline-events">{content.groups.map(group => <li key={group.date}>
      <div><span className="sm-timeline-event-number">{group.number}　</span><time dateTime={group.date}>{group.date}</time></div>
      <ul>{group.events.map(event => <li key={event.id} data-timeline-event={event.id}>
        <strong>{event.label}</strong>{showDetails && event.detail ? <p className="sm-timeline-detail">{event.detail}</p> : null}
      </li>)}</ul>
    </li>)}</ol>
  </section>;
}
