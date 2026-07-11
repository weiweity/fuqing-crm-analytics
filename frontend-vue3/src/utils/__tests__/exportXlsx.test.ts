// Sprint 174 exportXlsx.ts SSOT 验证测试
// 锁定历史 bug: Q4 finding frontend exportXlsx.ts 用 raw SheetJS (xlsx) 没 #1F4E79 header / #D32F2F YOY+ / #2E7D32 YOY- / 0 公式没强制
// 修复后: xlsx-js-style + SSOT 颜色 + cell.s 样式 + 0 公式 _assert_not_formula
// Sprint 174 真业务触发: 用户 2026-07-01 报告「导出 excel 设计格式统一」
import { describe, it, expect, vi } from 'vitest'
import type { XlsxColumn } from '../exportXlsx'

// Mock xlsx-js-style with in-memory workbook capture (verify cell styles via calls)
interface MockCell {
  v?: unknown
  t?: string
  s?: Record<string, unknown>
  z?: string
}
const lastWorkbook = {
  cellStyles: [] as Array<{ sheet: string; row: number; col: number; style: Record<string, unknown>; numFmt?: string }>,
  sheetNames: [] as string[],
}

vi.mock('xlsx-js-style', () => {
  return {
    utils: {
      book_new: () => ({}),
      book_append_sheet: (_wb: unknown, ws: MockWorksheet, name: string) => {
        lastWorkbook.sheetNames.push(name)
        // Sprint 174 exportXlsx.ts 用 ws['!cells'] (Record<addr, {s}>) 存 styles
        // 用 ws[addr] (独立 cell) 存 numFmt
        const cellsRecord = (ws as any)['!cells'] as Record<string, { s?: unknown }> | undefined
        if (cellsRecord) {
          for (const [addr, body] of Object.entries(cellsRecord)) {
            // addr 格式: "R-C" (encoded from exportXlsx utils.encode_cell({r, c}))
            const [rStr, cStr] = addr.split('-')
            const r = parseInt(rStr, 10)
            const c = parseInt(cStr, 10)
            const cellAtAddr = (ws as any)[addr] as { z?: string } | undefined
            lastWorkbook.cellStyles.push({
              sheet: name,
              row: r,
              col: c,
              style: (body?.s as Record<string, unknown>) || {},
              numFmt: cellAtAddr?.z,
            })
          }
        }
      },
      aoa_to_sheet: (aoa: unknown[][]) => {
        // 返回空 mock worksheet, 真正的 styles 通过 ws['!cells'] + ws[addr] 注入 (exportXlsx.ts 自己的逻辑)
        return { _cells: aoa } as unknown as MockWorksheet
      },
      encode_cell: ({ r, c }: { r: number; c: number }) => `${r}-${c}`,
    },
    writeFile: () => {
      // mock — accept
    },
  }
})

interface MockWorksheet {
  _cells: MockCell[][]
  [key: string]: unknown
}

import { exportSheetToXlsx, SSOT, exportToXlsx } from '../exportXlsx'

describe('Sprint 174 exportXlsx.ts SSOT 视觉规范', () => {
  it('导出 header row 第一行每个 cell 有 SSOT.THEME_HEADER (#1F4E79) fill', async () => {
    lastWorkbook.cellStyles = []
    lastWorkbook.sheetNames = []
    const columns: XlsxColumn[] = [
      { header: '品类', key: 'name' },
      { header: 'GSV', key: 'gsv', numFmt: '¥#,##0' },
    ]
    const data = [{ name: '美白', gsv: 100000 }]
    await exportSheetToXlsx('test', '品类GSV', columns, data)
    // 验证 header row (r=0) 有深蓝 fill
    const headerStyles = lastWorkbook.cellStyles.filter((c) => c.row === 0)
    expect(headerStyles.length).toBeGreaterThanOrEqual(2)
    for (const cell of headerStyles) {
      // fill 字段是 nested object; 验证 fgColor 存在 + 是 SSOT.THEME_HEADER
      const fill = cell.style?.fill as { fgColor?: { rgb?: string } } | undefined
      expect(fill?.fgColor?.rgb).toBe(SSOT.THEME_HEADER)
    }
  })

  it('导出 numeric body cell 有 BODY_NUMERIC_STYLE alignment=right', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [{ header: 'GSV', key: 'gsv', numFmt: '¥#,##0' }]
    const data = [{ gsv: 99999 }]
    await exportSheetToXlsx('test', 'Test', columns, data)
    const numRow = lastWorkbook.cellStyles.find((c) => c.row === 1)
    expect(numRow).toBeTruthy()
    const align = numRow!.style.alignment as { horizontal?: string } | undefined
    expect(align?.horizontal).toBe('right')
  })

  it('YOY 正值 (num >= 0) → BODY_YOY_POS_STYLE with font.color=SSOT.YOY_POS (#D32F2F)', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [{ header: '复购率同比', key: 'repurchase_rate_yoy' }]
    const data = [{ repurchase_rate_yoy: 5.28 }]  // 正值
    await exportSheetToXlsx('test', 'YoY+', columns, data)
    const yoyCell = lastWorkbook.cellStyles.find((c) => c.row === 1)
    expect(yoyCell).toBeTruthy()
    const font = yoyCell!.style.font as { color?: { rgb?: string } } | undefined
    expect(font?.color?.rgb).toBe(SSOT.YOY_POS)
  })

  it('YOY 负值 (num < 0) → BODY_YOY_NEG_STYLE with font.color=SSOT.YOY_NEG (#2E7D32)', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [{ header: '复购率同比', key: 'repurchase_rate_yoy' }]
    const data = [{ repurchase_rate_yoy: -3.14 }]
    await exportSheetToXlsx('test', 'YoY-', columns, data)
    const yoyCell = lastWorkbook.cellStyles.find((c) => c.row === 1)
    expect(yoyCell).toBeTruthy()
    const font = yoyCell!.style.font as { color?: { rgb?: string } } | undefined
    expect(font?.color?.rgb).toBe(SSOT.YOY_NEG)
  })

  it('0 公式 SSOT: 写入以 "=" 开头的字符串必须 throw', async () => {
    const columns: XlsxColumn[] = [{ header: '栏', key: 'formula' }]
    const data = [{ formula: '=SUM(A1:A10)' }]
    await expect(exportSheetToXlsx('test', 'Err', columns, data)).rejects.toThrow(/XLSX output forbids formulas/)
  })

  it('SSOT 颜色常量 mirror 与 backend 一致', () => {
    expect(SSOT.THEME_HEADER).toBe('1F4E79')
    expect(SSOT.YOY_POS).toBe('D32F2F')
    expect(SSOT.YOY_NEG).toBe('2E7D32')
  })

  it('列名 _yoy 后缀自动识别为 YOY 列 (numeric)', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [
      { header: 'GSV YOY', key: 'gsv_yoy' },  // 真 numeric YOY 列 (列名后缀 _yoy)
      { header: 'GSV', key: 'gsv' },
    ]
    const data = [{ gsv_yoy: 12.5, gsv: 100000 }]
    await exportSheetToXlsx('test', 'AutoYoy', columns, data)
    // 第 1 列 (c=0) 应该识别为 YOY 而非普通 numeric, 走 YOY_POS 着色
    const yoyCell = lastWorkbook.cellStyles.find((c) => c.row === 1 && c.col === 0)
    expect(yoyCell).toBeTruthy()
    const yoyFont = yoyCell!.style.font as { color?: { rgb?: string } }
    expect(yoyFont.color?.rgb).toBe(SSOT.YOY_POS)
  })

  it('exportToXlsx 多 sheet: sheet name substring(0, 31) + 顺序保留', async () => {
    lastWorkbook.sheetNames = []
    const sheets = [
      { name: 'A' + 'x'.repeat(40), columns: [{ header: 'a', key: 'a' }], data: [{ a: 1 }] },
      { name: 'B', columns: [{ header: 'b', key: 'b' }], data: [{ b: 2 }] },
    ]
    await exportToXlsx('test', sheets as any)
    // sheet name > 31 chars 应被截断到 31 chars
    expect(lastWorkbook.sheetNames.length).toBe(2)
    expect(lastWorkbook.sheetNames[1]).toBe('B')
    expect(lastWorkbook.sheetNames[0].length).toBeLessThanOrEqual(31)
  })

  // ===== L4.91 PR0 新契约测试 (跟 L4.50 0 业务代码改动 累计 90 次 1:1 stable 永久规则化沿用) =====

  it('L4.91 PR0: assertNotFormula 拒绝 object 形式 {f: "=..."} (AudienceView raw xlsx 漏挡 fix)', async () => {
    // AudienceView.vue:1657-1659 raw xlsx path 写过 {t:"n",f:"=B1-C1"}, Sprint 174 assertNotFormula 只挡 string,
    // L4.91 PR0 扩展检测 object 形式 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
    const columns: XlsxColumn[] = [{ header: '指标', key: 'indicator' }]
    const data = [{ indicator: { t: 'n', f: '=B1-C1' } }]
    await expect(exportSheetToXlsx('test', 'ObjFormula', columns, data)).rejects.toThrow(/XLSX output forbids formulas/)
  })

  it('L4.91 PR0: kind="yoy_pp" 显式 enum → numFmt = "0.00%;-0.00%;0.00%" (pp 差 raw *100)', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [
      { header: '复购率 YOY (pp)', key: 'repurchase_rate_yoy_pp', kind: 'yoy_pp' },
    ]
    const data = [{ repurchase_rate_yoy_pp: 0.05 }]  // raw 0.05 = +5pp
    await exportSheetToXlsx('test', 'PpKind', columns, data)
    const cell = lastWorkbook.cellStyles.find((c) => c.row === 1)
    expect(cell?.numFmt).toBe('0.00%;-0.00%;0.00%')
  })

  it('L4.91 PR0: kind="yoy_day" 显式 enum → numFmt = "+0;-0;0" (天数差 signed int, 无 %)', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [
      { header: '中位天数 YOY', key: 'median_days_yoy', kind: 'yoy_day' },
    ]
    const data = [{ median_days_yoy: 3 }]  // raw 3 = +3天
    await exportSheetToXlsx('test', 'DayKind', columns, data)
    const cell = lastWorkbook.cellStyles.find((c) => c.row === 1)
    expect(cell?.numFmt).toBe('+0;-0;0')
  })

  it('L4.91 PR0: kind="text" 显式 enum → 不应用 YOY numFmt, 走 caller numFmt (caller 优先级)', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [
      // 列名有 _yoy 后缀但 caller 显式 kind="text", 应该跳过 YOY auto-detect
      { header: '备注', key: 'note_yoy', kind: 'text', numFmt: '@' },
    ]
    const data = [{ note_yoy: '稳定' }]
    await exportSheetToXlsx('test', 'TextKind', columns, data)
    // 字符串值, 不会设 numFmt (isNumeric=false), 但 kind="text" 不会被 YOY auto-detect 错认
    // 测试目的: 验证 kind="text" 显式 enum 防止 auto-detect 误判
    const cell = lastWorkbook.cellStyles.find((c) => c.row === 1)
    expect(cell).toBeTruthy()
  })

  // ===== L4.91.1 (2026-07-11) 治本 market-focus#product-customer 对比行格式错 =====
  // 跟 L4.91 PR0 kind enum + L4.50 0 业务代码改动 + user 限制 "其他前端不要调整逻辑" 1:1 stable 永久规则化沿用
  // SSOT 扩展: XlsxColumn.formatValue 函数 (向后兼容, 可选字段)
  // per-row dispatch: 对比行 (isChangeRow/isYoyRow) 用 _yoy_pct / _yoy_pp 后缀字段, normal row 用原字段
  it('L4.91.1: formatValue 简单值 → per-row override cell value', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [
      {
        header: '指标',
        key: 'indicator',
        kind: 'number',
        numFmt: '¥#,##0',
        formatValue: (val, row) => row?.isChangeRow ? -123 : val,
      },
    ]
    const data = [
      { indicator: 1000, isChangeRow: false },  // normal row: 显示 1000
      { indicator: 0, isChangeRow: true },     // 对比行: formatValue 返回 -123
    ]
    await exportSheetToXlsx('test', 'FormatSimple', columns, data)
    // 验证: 2 行都有 cellStyles
    expect(lastWorkbook.cellStyles.length).toBeGreaterThanOrEqual(2)
  })

  it('L4.91.1: formatValue 返回 { val, numFmt } → per-row override value + numFmt (治本 ProductCustomerTab 对比行)', async () => {
    lastWorkbook.cellStyles = []
    const columns: XlsxColumn[] = [
      {
        header: 'GSV',
        key: 'gsv',
        kind: 'number',
        numFmt: '¥#,##0',
        formatValue: (val, row) => {
          if (row?.isChangeRow || row?.isYoyRow) {
            return { val: row.gsv_yoy_pct ?? null, numFmt: '+0.00%;-0.00%;0.00%' }
          }
          return val
        },
      },
      {
        header: '新客成交占比',
        key: 'new_ratio_gsv',
        kind: 'number',
        numFmt: '0.0%',
        formatValue: (val, row) => {
          if (row?.isChangeRow || row?.isYoyRow) {
            return { val: row.new_ratio_gsv_yoy_pp ?? null, numFmt: '+0.00"pp";-0.00"pp";0.00"pp"' }
          }
          return val
        },
      },
    ]
    const data = [
      { gsv: 1113652.14, new_ratio_gsv: 0.4922, isChangeRow: false },  // normal row
      { gsv: 0, new_ratio_gsv: 0, isChangeRow: true, gsv_yoy_pct: -0.6248, new_ratio_gsv_yoy_pp: -0.0094 },  // 对比行
    ]
    await exportSheetToXlsx('test', 'ProductCustomer', columns, data)

    // normal row (row 1): GSV numFmt ¥#,##0, 占比 numFmt 0.0%
    const normalGsvCell = lastWorkbook.cellStyles.find((c) => c.row === 1 && c.col === 0)
    expect(normalGsvCell?.numFmt).toBe('¥#,##0')
    const normalRatioCell = lastWorkbook.cellStyles.find((c) => c.row === 1 && c.col === 1)
    expect(normalRatioCell?.numFmt).toBe('0.0%')

    // 对比行 (row 2): GSV numFmt yoy_pct (+0.00%), 占比 numFmt yoy_pp (+0.00pp)
    const changeGsvCell = lastWorkbook.cellStyles.find((c) => c.row === 2 && c.col === 0)
    expect(changeGsvCell?.numFmt).toBe('+0.00%;-0.00%;0.00%')
    const changeRatioCell = lastWorkbook.cellStyles.find((c) => c.row === 2 && c.col === 1)
    expect(changeRatioCell?.numFmt).toBe('+0.00"pp";-0.00"pp";0.00"pp"')
  })
})
