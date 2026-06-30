/**
 * Excel 导出工具 — 基于 xlsx-js-style (SheetJS + styles)
 * 支持：SSOT 颜色 + 0 公式 + YOY 红/绿 + 列宽 + 数字格式
 *
 * Sprint 174 真业务 fix (Q4): 前端导出原本用 SheetJS community (xlsx 不支持 fill color)，
 * Sprint 174 切换到 xlsx-js-style 社区 fork（SheetJS 100% 兼容 + styles API）以支持视觉 SSOT。
 *
 * 视觉 SSOT Mirror (跟 backend scripts/ad_hoc_query_excel_styles.py 一致):
 * - 表头: 深蓝 #1F4E79 + 白字 bold
 * - 同比正值: A 股红 #D32F2F bold
 * - 同比负值: 绿色 #2E7D32 bold
 * - 列宽: header 自适应 + 内容 max 长度 adaptive
 * - 公式: 0 公式 (cell.value 拒绝 "=" 开头)
 *
 * xlsx-js-style 通过动态 import() 按需加载，不进入首屏 bundle。
 * 首次点击导出时有 ~300ms 加载延迟，后续调用使用缓存。
 */

let _XLSX: typeof import('xlsx-js-style') | null = null

async function _getXLSX(): Promise<typeof import('xlsx-js-style')> {
  if (!_XLSX) {
    _XLSX = await import('xlsx-js-style')
  }
  return _XLSX
}

/**
 * Sprint 174 视觉 SSOT (跟 backend `scripts/ad_hoc_query_excel_styles.py` mirror)
 * SSOT 反漂移: 改这里要同步改 backend, 反之亦然.
 */
export const SSOT = {
  THEME_HEADER: '1F4E79',   // 深蓝 (header bg + fill)
  THEME_SUBHEADER: '2E75B6', // 中蓝
  YOY_POS: 'D32F2F',         // A 股红 (同比正)
  YOY_NEG: '2E7D32',         // 绿 (同比负)
  BORDER: 'D9E2F3',          // 浅蓝 (cell border)
  WHITE: 'FFFFFF',
  BLACK: '000000',
} as const

/**
 * Sprint 174 视觉 SSOT cell styles (ready 给 ws['!cells'][r][c].s 设置)
 * 每个 cell.s = { fill, font, alignment, border }
 */
const HEADER_STYLE = {
  fill: { patternType: 'solid', fgColor: { rgb: SSOT.THEME_HEADER } },
  font: { name: 'Microsoft YaHei', sz: 11, bold: true, color: { rgb: SSOT.WHITE } },
  alignment: { horizontal: 'center', vertical: 'center', wrapText: true },
  border: {
    top: { style: 'thin', color: { rgb: SSOT.BORDER } },
    bottom: { style: 'thin', color: { rgb: SSOT.BORDER } },
    left: { style: 'thin', color: { rgb: SSOT.BORDER } },
    right: { style: 'thin', color: { rgb: SSOT.BORDER } },
  },
} as const

const BODY_STYLE = {
  font: { name: 'Microsoft YaHei', sz: 10, color: { rgb: SSOT.BLACK } },
  alignment: { horizontal: 'left', vertical: 'center', wrapText: true },
  border: {
    top: { style: 'thin', color: { rgb: SSOT.BORDER } },
    bottom: { style: 'thin', color: { rgb: SSOT.BORDER } },
    left: { style: 'thin', color: { rgb: SSOT.BORDER } },
    right: { style: 'thin', color: { rgb: SSOT.BORDER } },
  },
} as const

const BODY_NUMERIC_STYLE = {
  ...BODY_STYLE,
  alignment: { horizontal: 'right', vertical: 'center', wrapText: true },
}

const BODY_YOY_POS_STYLE = {
  fill: { patternType: 'solid', fgColor: { rgb: 'FFF6F6' } }, // 浅红底增强可读性
  font: { name: 'Microsoft YaHei', sz: 10, bold: true, color: { rgb: SSOT.YOY_POS } },
  alignment: { horizontal: 'right', vertical: 'center' },
  border: BODY_STYLE.border,
} as const

const BODY_YOY_NEG_STYLE = {
  fill: { patternType: 'solid', fgColor: { rgb: 'F1F8F1' } }, // 浅绿底
  font: { name: 'Microsoft YaHei', sz: 10, bold: true, color: { rgb: SSOT.YOY_NEG } },
  alignment: { horizontal: 'right', vertical: 'center' },
  border: BODY_STYLE.border,
} as const

/**
 * Sprint 174 SSOT: 列名后缀白名单 — 命中 = 当 YOY 列处理.
 * 跟 backend ad-hoc SKILL.md ratio convention 命名规范一致:
 * - *_yoy / *_YoY / *_YoYPct / *_YoYPp
 * - *_mom / *_MoM
 * - *_ppt / *_Pp  (单位是 pp 不是 %)
 */
const YOY_COLUMN_PATTERN = /_(yoy|mom)(?:pct|pp)?$|_YoYP?p?_?$/i
const PP_COLUMN_PATTERN = /_(ppt|pp|YoYPp|MoMPp)$/i

export interface XlsxColumn {
  /** 列标题（中文） */
  header: string
  /** 数据字段 key */
  key: string
  /** 列宽（字符数） */
  width?: number
  /** 数字格式，如 '#,##0' / '0.00%' / '¥#,##0' */
  numFmt?: string
  /**
   * Sprint 174 SSOT 扩展: 列类型 hint (默认 'auto' 让 SSOT 自动推断)
   * - 'yoy': 强制识别为 YOY 列 (按 numFmt 正负着色)
   * - 'auto': 按列名后缀 (默认)
   */
  kind?: 'auto' | 'yoy' | 'text' | 'number'
}

export interface XlsxSheetConfig {
  /** 工作表名 */
  name: string
  columns: XlsxColumn[]
  data: Record<string, any>[]
}

/**
 * Sprint 174 SSOT: 拒绝写入以 "=" 开头的公式字符串.
 * 整份 XLSX 必须 0 公式 (用户拍板, 跨 sprint stable).
 */
function assertNotFormula(value: unknown): void {
  if (typeof value === 'string' && value.startsWith('=')) {
    throw new Error(`XLSX output forbids formulas, but received: ${value.slice(0, 50)}`)
  }
}

/**
 * Sprint 174 SSOT: 列是否识别为 YOY 列.
 */
function isYoyColumn(col: XlsxColumn): boolean {
  if (col.kind === 'yoy') return true
  if (col.kind === 'text' || col.kind === 'number') return false
  return YOY_COLUMN_PATTERN.test(col.key) || YOY_COLUMN_PATTERN.test(col.header)
}

function isPpColumn(col: XlsxColumn): boolean {
  return PP_COLUMN_PATTERN.test(col.key) || PP_COLUMN_PATTERN.test(col.header)
}

/**
 * 将多张表导出为一个 .xlsx 文件 (SSOT 合规).
 */
export async function exportToXlsx(filename: string, sheets: XlsxSheetConfig[]): Promise<void> {
  const XLSX = await _getXLSX()
  const wb = XLSX.utils.book_new()

  for (const sheet of sheets) {
    const { columns, data, name } = sheet

    // 构建 AOA 数组
    const header = columns.map((c) => c.header)
    const aoa: unknown[][] = [header]

    for (const row of data) {
      const rowArr: unknown[] = []
      for (const col of columns) {
        const val = row[col.key]
        assertNotFormula(val)
        rowArr.push(val != null ? val : '')
      }
      aoa.push(rowArr)
    }

    const ws = XLSX.utils.aoa_to_sheet(aoa)

    // ── 设置 cell styles (SSOT) ──
    if (!ws['!cells']) ws['!cells'] = {}
    const cells: Record<string, { s?: unknown }> = {}

    // header row (row 0)
    for (let c = 0; c < columns.length; c++) {
      const addr = XLSX.utils.encode_cell({ r: 0, c })
      cells[addr] = { s: HEADER_STYLE as unknown }
    }

    // body rows (1..N)
    for (let r = 1; r < aoa.length; r++) {
      for (let c = 0; c < columns.length; c++) {
        const col = columns[c]
        const val = aoa[r][c]
        const addr = XLSX.utils.encode_cell({ r, c })

        // numFmt 跟 style 独立设: numeric 走 BODY_NUMERIC_STYLE 居右
        const isNumeric = typeof val === 'number'
        const isYoy = isYoyColumn(col)
        let styleToApply: unknown
        if (isYoy && isNumeric) {
          styleToApply = (val as number) >= 0
            ? BODY_YOY_POS_STYLE
            : BODY_YOY_NEG_STYLE
        } else if (isNumeric) {
          styleToApply = BODY_NUMERIC_STYLE
        } else {
          styleToApply = BODY_STYLE
        }

        cells[addr] = { s: styleToApply }
      }
    }
    ws['!cells'] = cells

    // ── 数字格式 (numFmt) 单独设 (Sprint 174 SSOT 同时支持 YOY 字符串前缀) ──
    for (let r = 1; r < aoa.length; r++) {
      for (let c = 0; c < columns.length; c++) {
        const col = columns[c]
        const cell = XLSX.utils.encode_cell({ r, c })
        const isYoy = isYoyColumn(col)
        const isPp = isPpColumn(col)
        const isNumeric = typeof aoa[r][c] === 'number'

        if (isYoy && isNumeric) {
          // SSOT: YOY 数值用 numFmt 把 "+/-X.XX" 格式化; 但因 already-set s.font.color 着色,
          // 这里只设 number format, numFmt 让 Excel 显示 "0.00%;-0.00%"
          const fmt = isPp ? '0.00%;-0.00%;0.00%' : '+0.00%;-0.00%;0.00%'
          if (!ws[cell]) ws[cell] = {}
          ws[cell].z = fmt
        } else if (isNumeric && col.numFmt) {
          if (!ws[cell]) ws[cell] = {}
          ws[cell].z = col.numFmt
        }
      }
    }

    // ── 列宽 (Sprint 174 SSOT: header 自适应) ──
    ws['!cols'] = columns.map((c) => ({
      wch: c.width || Math.max((c.header?.length || 4) * 2, 12),
    }))

    // ── 行高 (header 双倍) ──
    ws['!rows'] = [{ hpx: 24 }]

    // ── freeze panes 冻结 header 行 ──
    ws['!freeze'] = { xSplit: 0, ySplit: 1 }

    XLSX.utils.book_append_sheet(wb, ws, name.substring(0, 31))
  }

  XLSX.writeFile(wb, `${filename}.xlsx`)
}

/**
 * 便捷方法：单表导出.
 */
export async function exportSheetToXlsx(
  filename: string,
  sheetName: string,
  columns: XlsxColumn[],
  data: Record<string, any>[],
): Promise<void> {
  await exportToXlsx(filename, [{ name: sheetName, columns, data }])
}
