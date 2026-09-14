/** Serializable component contract shared by AI tools, validation and rendering. */
import definition from './component-catalog.json' with { type: 'json' };
import { validCalendarDate, structuredContentError } from './structured-content.mjs';

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

export const COMPONENT_CATALOG = deepFreeze(definition);
export const LIBRARY_KINDS = Object.freeze(definition.components.map(component => component.kind));
const components = new Map(definition.components.map(component => [component.kind, component]));
const fail = (code, message) => ({ ok: false, error: { code, message } });

export function componentDefinition(kind) {
  return components.get(kind) ?? null;
}

export function isPlainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function validValue(value, rule) {
  if (rule.type === 'boolean') return typeof value === 'boolean';
  if (rule.type === 'integer') {
    return Number.isSafeInteger(value) && value >= rule.minimum && value <= rule.maximum;
  }
  if (rule.type === 'string') {
    return typeof value === 'string'
      && Array.from(value).length >= (rule.minLength ?? 0) && Array.from(value).length <= (rule.maxLength ?? Infinity)
      && (!rule.enum || rule.enum.includes(value)) && (!rule.pattern || new RegExp(rule.pattern).test(value))
      && (rule.format !== 'date' || validCalendarDate(value));
  }
  if (rule.type === 'array') {
    return Array.isArray(value) && value.length >= (rule.minItems ?? 0) && value.length <= rule.maxItems
      && (!rule.uniqueItems || new Set(value).size === value.length)
      && Array.from(value).every(item => validValue(item, rule.items));
  }
  if (rule.type === 'object') return isPlainObject(value)
    && (rule.required ?? []).every(key => Object.hasOwn(value, key))
    && Object.keys(value).every(key => Object.hasOwn(rule.properties, key) && validValue(value[key], rule.properties[key]));
  return false;
}

/** Partial props are valid; defaults are materialized only by the renderer/tool. */
export function parseComponentProps(kind, props, { defaults = false } = {}) {
  const component = componentDefinition(kind);
  if (!component) return fail('COMPONENT_UNSUPPORTED', `组件库尚不支持 ${String(kind)}`);
  if (!isPlainObject(props)) return fail('COMPONENT_PROPS', '组件 props 必须是普通对象');
  const rules = { ...definition.common_properties, ...component.properties };
  for (const key of Object.keys(props)) {
    if (!Object.hasOwn(rules, key)) return fail('COMPONENT_PROPERTY', `${kind} 不支持属性 ${key}`);
    // Enum strings have an implicit bounded length even when no maxLength is declared.
    const rule = rules[key];
    const bounded = rule.enum ? { ...rule, maxLength: Math.max(...rule.enum.map(item => item.length)) } : rule;
    if (!validValue(props[key], bounded)) return fail('COMPONENT_VALUE', `${kind}.${key} 值不合法`);
  }
  const result = defaults
    ? Object.fromEntries(Object.entries(rules).map(([key, rule]) => [key, structuredClone(rule.default)]))
    : {};
  const value = { ...result, ...structuredClone(props) };
  const issue = structuredContentError(kind, value);
  return issue ? fail('COMPONENT_STRUCTURE', issue) : { ok: true, value };
}

/** No fact values, sources, query parameters, CSS or executable code via a display patch.
 * Plain explanatory text is untrusted copy, not verified numerical evidence.
 */
export function mergeComponentProps(kind, current, patch) {
  const old = parseComponentProps(kind, current ?? {});
  if (!old.ok) return old;
  const next = parseComponentProps(kind, patch);
  if (!next.ok) return next;
  return parseComponentProps(kind, { ...old.value, ...next.value });
}

/** Grid constraints for new library layouts; legacy documents are not rewritten. */
export function parseComponentLayout(kind, layout) {
  const component = componentDefinition(kind);
  if (!component) return fail('COMPONENT_UNSUPPORTED', `组件库尚不支持 ${String(kind)}`);
  if (!isPlainObject(layout) || Object.keys(layout).some(key => !['x', 'y', 'w', 'h'].includes(key))) {
    return fail('COMPONENT_LAYOUT', '布局必须为 x/y/w/h');
  }
  const { x, y, w, h } = layout;
  if (![x, y, w, h].every(Number.isSafeInteger) || x < 0 || y < 0
    || w < component.min_size.w || h < component.min_size.h
    || x + w > definition.grid.columns || y + h > definition.grid.max_rows) {
    return fail('COMPONENT_LAYOUT', `${kind} 布局超出画布或小于最小尺寸`);
  }
  return { ok: true, value: { x, y, w, h } };
}
