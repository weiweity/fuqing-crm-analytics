/**
 * XSS 回归：恶意标签字符串只能当文本，不得变成可执行 HTML。
 */
import { describe, it, expect } from 'vitest'
import {
  encodeHtml,
  sanitizeCssColor,
  _fallbackEncodeHtmlForTests,
} from '../encodeHtml'

const MALICIOUS_PAYLOADS = [
  '<img src=x onerror=alert(1)>',
  '<script>alert("xss")</script>',
  '"><img src=x onerror=alert(1)>',
  "';alert(1)//",
  '<svg onload=alert(1)>',
  '品类<script>alert(1)</script>',
  'A&B <C>',
  "name' onclick='alert(1)",
]

describe('encodeHtml', () => {
  it('escapes all common XSS payloads so tags are text-only', () => {
    for (const payload of MALICIOUS_PAYLOADS) {
      const out = encodeHtml(payload)
      expect(out).not.toMatch(/<script/i)
      expect(out).not.toMatch(/<img/i)
      expect(out).not.toMatch(/<svg/i)
      if (payload.includes('<')) expect(out).toContain('&lt;')
      if (payload.includes('>')) expect(out).toContain('&gt;')
      expect(out).not.toBe(payload)
    }
  })

  it('uses echarts.format.encodeHTML (or equivalent) for angle brackets', () => {
    const out = encodeHtml('<b>x</b>')
    expect(out).toBe('&lt;b&gt;x&lt;/b&gt;')
  })

  it('fallback matches echarts-style 5-entity encoding', () => {
    const raw = `<script>alert("x")</script>&'"`
    const out = _fallbackEncodeHtmlForTests(raw)
    expect(out).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;&amp;&#39;&quot;',
    )
  })

  it('null/undefined become empty string', () => {
    expect(encodeHtml(null)).toBe('')
    expect(encodeHtml(undefined)).toBe('')
  })

  it('numbers and safe Chinese labels stay readable after escape', () => {
    expect(encodeHtml(123)).toBe('123')
    expect(encodeHtml('敏感肌修复')).toBe('敏感肌修复')
  })

  it('malicious category name in a tooltip HTML template is inert', () => {
    const segName = '<img src=x onerror=alert(1)>'
    const html = `<div>${encodeHtml(segName)} — 点击查看</div>`
    expect(html).toContain('&lt;img')
    expect(html).not.toContain('<img src=x')
    expect(html).not.toMatch(/<img[^>]*onerror/i)
  })
})

describe('sanitizeCssColor', () => {
  it('allows hex / rgb / named colors', () => {
    expect(sanitizeCssColor('#533afd')).toBe('#533afd')
    expect(sanitizeCssColor('#fff')).toBe('#fff')
    expect(sanitizeCssColor('rgb(1, 2, 3)')).toBe('rgb(1, 2, 3)')
    expect(sanitizeCssColor('red')).toBe('red')
  })

  it('rejects CSS injection payloads', () => {
    expect(sanitizeCssColor('red; background:url(javascript:alert(1))')).toBe(
      'transparent',
    )
    expect(sanitizeCssColor('expression(alert(1))')).toBe('transparent')
    expect(sanitizeCssColor('url(https://evil)')).toBe('transparent')
  })
})
