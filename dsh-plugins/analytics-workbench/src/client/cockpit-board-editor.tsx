import { COMPONENT_CATALOG, componentDefinition, parseComponentProps } from '../board-spec/component-catalog.mjs';
import type { LibraryBoardClient, LibraryState } from './library-board-client.mjs';
const labels: Record<string, string> = { content: '正文', align: '对齐方式', text_style: '文本样式', show_comparison: '显示对比',
  show_legend: '显示图例', show_points: '显示数据点', line_style: '线条样式', orientation: '方向', show_values: '显示数值',
  value_format: '数值格式', page_size: '每页条数', sort_field: '排序字段', sort_direction: '排序方向', summary: '摘要',
  expanded: '展开详情', show_owners: '显示负责人', show_details: '显示详情', show_dates: '显示日期' };
const values: Record<string, string> = { standard: '标准', compact: '紧凑', solid: '实线', dashed: '虚线', horizontal: '横向',
  vertical: '纵向', start: '左对齐', center: '居中', body: '正文', callout: '提示', asc: '升序', desc: '降序' };

export function BoardEditor({ library, state }: { library: LibraryBoardClient; state: LibraryState }) {
  const block = state.editContext?.block;
  const draft = state.fieldDraft;
  const title = draft?.title ?? block?.title ?? '';
  const kind = draft?.kind ?? block?.kind ?? '';
  const source = draft?.source_result_id ?? block?.source_result_id ?? '';
  const props = { ...block?.props, ...draft?.props } as Record<string, unknown>;
  const caps = library.describeSelectedPatch();
  const definition = componentDefinition(kind);
  const dirty = Boolean(draft);
  const change = (field: string, value: unknown) => {
    if (!block) return;
    const next = { ...draft } as Record<string, unknown>;
    const baseline = block as unknown as Record<string, unknown>;
    if (field === 'props') {
      const changed = Object.fromEntries(Object.entries(value as Record<string, unknown>).filter(([key, val]) => JSON.stringify(val) !== JSON.stringify((block.props as Record<string, unknown>)[key])));
      if (Object.keys(changed).length) next.props = changed; else delete next.props;
    } else if (value === baseline[field]) delete next[field]; else next[field] = value;
    library.setFieldDraft(Object.keys(next).length ? next : null);
  };
  const disabled = state.busy || Boolean(state.preview || state.layoutDraft) || state.confirmationUncertain;
  if (!block) return <><p className="cockpit-eyebrow">组件属性</p><div className="cockpit-selection-hint" aria-hidden="true">↖</div><h3>选择一个组件</h3>
    <p className="cockpit-muted">点选画布上的组件，在这里修改标题和展示属性。</p></>;
  const kinds = COMPONENT_CATALOG.components.filter(row => row.kind === block.kind ||
    (row.data_shape === componentDefinition(block.kind)?.data_shape && row.requires_result === Boolean(block.source_result_id)
      && row.min_size.w <= block.layout.w && row.min_size.h <= block.layout.h && parseComponentProps(row.kind, block.props).ok));
  return <form className="cockpit-board-form" onSubmit={event => {
    event.preventDefault(); if (state.fieldDraft) void library.previewBlockPatch(state.fieldDraft);
  }}>
    <p className="cockpit-eyebrow">当前组件</p><h3>{block.title}</h3>
    <label className="cockpit-field">组件标题<input data-testid="board-title-input" value={title} maxLength={160} required disabled={disabled} onChange={event => change('title', event.target.value)} /></label>
    <label className="cockpit-field">组件类型<select value={kind} disabled={disabled || kinds.length < 2} onChange={event => change('kind', event.target.value)}>{kinds.map(row => <option key={row.kind} value={row.kind}>{row.name}</option>)}</select></label>
    {Object.entries(definition?.properties ?? {}).map(([key, raw]) => {
      const rule = raw as { type: string; enum?: string[]; default?: unknown; minimum?: number; maximum?: number; maxLength?: number };
      if (!caps.props?.includes(key) || !['string','boolean','integer'].includes(rule.type)) return null;
      const value = props[key] ?? rule.default;
      const update = (next: unknown) => change('props', { ...props, [key]: next });
      return <label className="cockpit-field" key={key}>{labels[key] ?? key}
        {rule.type === 'boolean' ? <input type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={event => update(event.target.checked)} />
          : rule.enum ? <select value={String(value)} disabled={disabled} onChange={event => update(event.target.value)}>{rule.enum.map(item => <option key={item} value={item}>{values[item] ?? item}</option>)}</select>
          : rule.type === 'integer' ? <input type="number" value={Number(value)} min={rule.minimum} max={rule.maximum} disabled={disabled} onChange={event => update(Number(event.target.value))} />
          : <textarea rows={key === 'content' ? 5 : 2} value={String(value ?? '')} maxLength={rule.maxLength} disabled={disabled} onChange={event => update(event.target.value)} />}
      </label>;
    })}
    {caps.source_result_id ? <label className="cockpit-field">数据来源<select disabled={disabled || !caps.source_result_options?.length}
      value={source} onChange={event => change('source_result_id', event.target.value)}>
      <option value={block.source_result_id ?? ''}>当前已绑定结果</option>{caps.source_result_options?.filter(id => id !== block.source_result_id).map((id, i) => <option key={id} value={id}>可用结果 {i + 1} · {id}</option>)}
    </select></label> : null}
    <button type="submit" className="cockpit-primary" data-testid="board-preview-patch" disabled={disabled || !dirty || !title.trim()}>预览修改</button>
    {dirty && !state.preview ? <button type="button" disabled={state.busy} onClick={() => { library.setFieldDraft(null); }}>放弃字段修改</button> : null}
    <button type="button" disabled={disabled || dirty} onClick={() => void library.cancel()}>取消选择</button>
    <hr /><p className="cockpit-muted">需要更复杂的修改，可以将当前组件交给原生对话。</p>
    <button type="button" disabled={disabled || dirty} onClick={() => void library.resumeEdit()}>用 AI 改</button>
  </form>;
}


export function boardChangeSummary(before: { title: string; props?: Record<string, unknown> }, after?: { title: string; props?: Record<string, unknown> }) {
  if (!after) return '';
  const props = [...new Set([...Object.keys(before.props ?? {}), ...Object.keys(after.props ?? {})])].filter(key => JSON.stringify(before.props?.[key]) !== JSON.stringify(after.props?.[key]));
  const show = (value: unknown) => typeof value === 'boolean' ? (value ? '开启' : '关闭') : typeof value === 'object' ? JSON.stringify(value) : values[String(value)] ?? String(value ?? '默认');
  return ['修改前：' + before.title + ' → 修改后：' + after.title, ...props.map(key => (labels[key] ?? '结构化内容') + '：' + show(before.props?.[key]) + ' → ' + show(after.props?.[key]))].join('；');
}
