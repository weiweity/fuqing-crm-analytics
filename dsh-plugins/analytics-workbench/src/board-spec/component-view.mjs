/** Read-only projection. Component facts are server-owned, never AI display props.
 * Units describe the number AS SUPPLIED; this renderer never guesses a multiplier.
 */
import { componentDefinition, isPlainObject, parseComponentProps } from './component-catalog.mjs';
import { timelineGeometry } from './structured-content.mjs';
import { waterfallGeometry } from '../../../shine-waterfall/src/waterfall.mjs';
import { funnelGeometry } from '../../../shine-funnel/src/funnel.mjs';

export const COMPONENT_FACTS_VERSION = 'board-component-facts/v1';
const number = value => typeof value === 'number' && Number.isFinite(value);
const text = (value, max = 240) => typeof value === 'string' && value.length <= max;
const unit = value => value === null || text(value, 24);
const key = value => text(value, 80) && /^[a-zA-Z][a-zA-Z0-9_]*$/.test(value)
  && !['constructor', 'prototype', '__proto__'].includes(value);
const cell = value => value === null || number(value) || text(value, 2000);
const invalid = message => ({ status: 'error', code: 'COMPONENT_DATA', message });

/** Legacy GSV conversion preserves raw values and explicitly leaves the unit unknown. */
function legacyFacts(facts) {
  if (!number(facts?.current_gsv) || !number(facts?.comparison_gsv)) return null;
  const current = facts.current_gsv;
  const comparison = facts.comparison_gsv;
  return {
    schema_version: COMPONENT_FACTS_VERSION,
    scalar: { value: current, comparison, unit: null },
    series: { points: [{ label: '对比期', value: comparison }, { label: '本期', value: current }], ordered: false, unit: null },
    table: { columns: [{ key: 'label', label: '项目' }, { key: 'value', label: '数值', unit: null }],
      rows: [{ label: '本期 GSV', value: current }, { label: '对比期 GSV', value: comparison },
        { label: '差额', value: number(facts.difference) ? facts.difference : null }] },
    evidence: { source_label: '历史 GSV 结果（单位未声明）', items: [] },
  };
}

function project(kind, source, props) {
  if (kind === 'FUNNEL') {
    if (!funnelGeometry(source.funnel)) return invalid('缺少同一人群的嵌套客户计数，不能用金额或无关阶段生成漏斗');
    return { status: 'ready', funnel: structuredClone(source.funnel) };
  }
  if (kind === 'WATERFALL') {
    if (!waterfallGeometry(source.waterfall)) return invalid('缺少已对账的同单位贡献，不能把两期差额编成瀑布');
    return { status: 'ready', waterfall: structuredClone(source.waterfall) };
  }
  if (kind === 'METRIC') {
    const data = source.scalar;
    if (!isPlainObject(data) || !unit(data.unit) || (data.value !== null && !number(data.value))
      || (data.comparison != null && !number(data.comparison))) return invalid('指标结果格式不合法');
    if (data.value === null) return { status: 'empty', message: '该指标暂无数据' };
    return { status: 'ready', scalar: structuredClone(data) };
  }
  if (kind === 'LINE' || kind === 'BAR') {
    const data = kind === 'LINE' && Object.hasOwn(source, 'time_series') ? source.time_series : source.series;
    const limit = kind === 'LINE' ? 366 : 200;
    if (!isPlainObject(data) || !unit(data.unit) || !Array.isArray(data.points) || data.points.length > limit
      || typeof data.ordered !== 'boolean'
      || data.points.some(point => !isPlainObject(point) || !text(point.label, 160) || !point.label
        || (point.value !== null && !number(point.value)))
      || new Set(data.points.map(point => point.label)).size !== data.points.length) return invalid('序列缺少有效标签、数值或单位说明');
    if (kind === 'LINE' && !data.ordered) return invalid('无序分类不能作为趋势，请改用对比图');
    if (!data.points.some(point => point.value !== null)) return { status: 'empty', message: '暂无可绘制的数据点' };
    return { status: 'ready', series: structuredClone(data) };
  }
  if (kind === 'TABLE') {
    const data = source.table;
    if (!isPlainObject(data) || !Array.isArray(data.columns) || data.columns.length < 1 || data.columns.length > 12
      || data.columns.some(column => !isPlainObject(column) || !key(column.key) || !text(column.label, 160)
        || (column.unit !== undefined && !unit(column.unit)))
      || new Set(data.columns.map(column => column.key)).size !== data.columns.length
      || !Array.isArray(data.rows) || data.rows.length > 10000) return invalid('明细表结构或数据量不符合合同');
    const fields = new Set(data.columns.map(column => column.key));
    if (data.rows.some(row => !isPlainObject(row) || Object.keys(row).some(field => !fields.has(field))
      || data.columns.some(column => !Object.hasOwn(row, column.key) || !cell(row[column.key])))) return invalid('明细表含未知字段、缺失字段或非法单元格');
    if (props.columns.some(field => !fields.has(field)) || (props.sort_field && !fields.has(props.sort_field))) {
      return invalid('所选列或排序字段不存在于绑定结果，需重新选择或问数');
    }
    const columns = props.columns.length ? props.columns.map(field => data.columns.find(column => column.key === field)) : data.columns;
    const rows = structuredClone(data.rows);
    if (props.sort_field) {
      const direction = props.sort_direction === 'desc' ? -1 : 1;
      rows.sort((a, b) => {
        const left = a[props.sort_field], right = b[props.sort_field];
        // Missing values stay last for either direction; no type coercion or numeric invention.
        if (left === right) return 0;
        if (left === null) return 1;
        if (right === null) return -1;
        return direction * (typeof left === 'number' && typeof right === 'number'
          ? left - right : String(left).localeCompare(String(right), 'zh-CN'));
      });
    }
    return { status: rows.length ? 'ready' : 'empty', message: rows.length ? '' : '暂无明细记录', table: { columns: structuredClone(columns), rows } };
  }
  if (kind === 'EVIDENCE') {
    const data = source.evidence;
    if (!isPlainObject(data) || !text(data.source_label) || !data.source_label || !Array.isArray(data.items)
      || data.items.length > 40 || data.items.some(item => !isPlainObject(item) || !text(item.label)
        || !text(item.value, 2000))) return invalid('证据信息不符合合同');
    return { status: 'ready', evidence: structuredClone(data) };
  }
  return invalid('组件没有登记数据投影');
}

export function projectComponent(block, facts) {
  const definition = componentDefinition(block.kind);
  if (!definition) return { status: 'error', code: 'COMPONENT_UNSUPPORTED', message: '尚未支持此组件' };
  const parsed = parseComponentProps(block.kind, block.props ?? {}, { defaults: true });
  if (!parsed.ok) return { status: 'error', ...parsed.error };
  const common = { kind: block.kind, props: parsed.value, source_result_id: block.source_result_id ?? null };
  if (definition.allows_result === false && block.source_result_id != null) return { ...common, ...invalid('规划说明不能冒充核验结果') };
  if (block.kind === 'PROCESS') return { ...common, status: parsed.value.nodes.length ? 'ready' : 'empty',
    message: '暂无流程节点；可让 AI 根据你的要求补充规划', process: { nodes: parsed.value.nodes, edges: parsed.value.edges } };
  if (block.kind === 'TIMELINE') return { ...common, status: parsed.value.events.length ? 'ready' : 'empty',
    message: '暂无日期事件；请提供明确日期，不推测时间', timeline: timelineGeometry(parsed.value.events) };
  if (block.kind === 'TEXT') return { ...common, status: parsed.value.content ? 'ready' : 'empty', message: '暂无说明文本' };
  if (!block.source_result_id || !facts) return { ...common, status: 'empty', code: 'RESULT_MISSING', message: '没有可用的绑定结果，不编造数字' };
  // An unknown explicit version must never fall back to the legacy shape.
  const source = facts.schema_version === COMPONENT_FACTS_VERSION ? facts : facts.schema_version ? null : legacyFacts(facts);
  if (!source) return { ...common, ...invalid('绑定结果版本或结构不受支持') };
  return { ...common, ...project(block.kind, source, parsed.value) };
}
