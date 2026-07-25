/**
 * 唯一公共 HTML 转义 — ECharts tooltip / label 等 HTML formatter 必须经此转义。
 *
 * 优先使用 echarts.format.encodeHTML（与图表库同源、行为一致）；
 * 若不可用则回退到等价的 5 字符实体转义。
 *
 * 注意：升级 ECharts 版本 ≠ 自动修自定义 formatter；所有注入 API/DB/轴/系列名的
 * HTML 字符串仍须显式调用本函数。
 */
import { format as echartsFormat } from 'echarts'

/** 与 echarts.format.encodeHTML 等价的 5 字符实体转义 */
function fallbackEncodeHtml(source: string): string {
  return source
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * 将任意值安全编码为可嵌入 HTML 的纯文本。
 * null/undefined → 空串；数字等先 String() 再转义。
 */
export function encodeHtml(value: unknown): string {
  if (value == null) return ''
  const text = String(value)
  if (typeof echartsFormat?.encodeHTML === 'function') {
    return echartsFormat.encodeHTML(text)
  }
  return fallbackEncodeHtml(text)
}

/**
 * 仅允许安全 CSS 颜色（hex / rgb(a) / named 常见色），防止 style 注入。
 * 非法值回退为 transparent。
 */
export function sanitizeCssColor(value: unknown, fallback = 'transparent'): string {
  if (value == null) return fallback
  const s = String(value).trim()
  if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(s)) return s
  if (/^rgba?\(\s*[\d.]+(?:\s*,\s*[\d.]+){2,3}\s*\)$/.test(s)) return s
  if (/^[a-zA-Z]{1,20}$/.test(s)) return s
  return fallback
}

/** 测试用：直接走 fallback 路径 */
export function _fallbackEncodeHtmlForTests(source: string): string {
  return fallbackEncodeHtml(source)
}
