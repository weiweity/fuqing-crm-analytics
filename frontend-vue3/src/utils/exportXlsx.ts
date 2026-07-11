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
 * 跟 backend ad-hoc SKILL.md ratio convention 命名规范一致 (跟 L4.79 + L4.80 + L4.81 1:1 stable 永久规则链配套):
 * - *_yoy / *_YoY / *_YoYPct / *_YoYPp  (百分比 YOY)
 * - *_mom / *_MoM
 * - *_ppt / *_Pp  (单位是 pp 不是 %)
 *
 * L4.91 扩展 (Q10A): 列 suffix 显式分支 — caller 用 `kind` 显式声明单位语义,
 * 不再依赖 auto-detect 的 regex 隐式分支 (避免 `_YoYP?p?_?` 这种埋雷 regex).
 */
// L4.91: 显式分支命名约定 (跟 backend PpField/PercentageField 1:1 stable 永久规则化沿用)
// 优先级: kind 显式 > caller numFmt > key/header suffix auto-detect
const YOY_PCT_PATTERN = /_(yoy|mom)(?:pct)?$|_YoYPct$|_YoY$/i
const YOY_PP_PATTERN = /_(ppt|pp)$|_yoy_pp$|_YoYPp$/i
const YOY_DAY_PATTERN = /_(days_yoy|days_mom)$|_yoy_day$/i

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
   * L4.91 SSOT: 列类型 hint (Q10A 显式 enum, 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)
   * - 'auto': 按列名后缀 (默认, 跟 Sprint 174 SSOT 兼容)
   * - 'yoy_pct': YOY percentage (raw 0.25 → 25.00% 显示)
   * - 'yoy_pp': YOY percentage-point diff (raw 0.05 → +5.00pp 显示)
   * - 'yoy_day': YOY days diff (raw signed int → +3天 显示, 无 numFmt 百分号)
   * - 'text': 文本列 (不应用 numFmt, 也不参与 YOY auto-detect)
   * - 'number': 通用数字列
   */
  kind?: 'auto' | 'yoy_pct' | 'yoy_pp' | 'yoy_day' | 'text' | 'number'
  /**
   * L4.91.1 (2026-07-11) 治本 market-focus#product-customer 对比行格式错:
   * 跟 L4.91 PR0 kind enum 1:1 stable 永久规则化沿用, 0 业务代码改动 1:1 stable 永久规则链配套.
   * 跟 user 限制 "其他前端不要调整逻辑" 1:1 stable: 这是 SSOT 扩展, 向后兼容 (可选字段, 缺省用 row[col.key]).
   * per-row dispatch 函数 (跟 row-level isChangeRow/isYoyRow 1:1 stable 永久规则化沿用):
   * - 入参: (val, row) — val 是 row[col.key], row 是完整数据行
   * - 出参:
   *   - 简单值: any — override cell value (per-row data dispatch)
   *   - 对象 { val, numFmt? }: 同时 override value 和 numFmt (per-row format switch, 治本 ProductCustomerTab 对比行 yoy)
   * 典型用法: 对比行 (isChangeRow/isYoyRow) 用 _yoy_pct / _yoy_pp 后缀字段, normal row 用原字段
   */
  formatValue?: (val: any, row?: Record<string, any>) => any | { val: any; numFmt?: string }
}

export interface XlsxSheetConfig {
  /** 工作表名 */
  name: string
  columns: XlsxColumn[]
  data: Record<string, any>[]
}

/**
 * Sprint 174 SSOT: 拒绝写入公式 (string + object 两种形式).
 * 整份 XLSX 必须 0 公式 (user 7/10 拍板 "WYSIWYG 不要公式", 跨 sprint stable).
 *
 * L4.91 PR0 扩展 (Q15): 之前只挡 `=开头的 string`, 漏挡 SheetJS object 形式 `{ t: 'n', f: '=B1-C1' }`
 * (AudienceView.vue:1657-1659 raw xlsx path 用过). 必须同时检测两种形式.
 */
function assertNotFormula(value: unknown): void {
  if (typeof value === 'string' && value.startsWith('=')) {
    throw new Error(`XLSX output forbids formulas, but received string: ${value.slice(0, 50)}`)
  }
  if (typeof value === 'object' && value !== null && 'f' in (value as Record<string, unknown>)) {
    const formulaField = (value as Record<string, unknown>).f
    if (typeof formulaField === 'string' && formulaField.startsWith('=')) {
      throw new Error(`XLSX output forbids formulas, but received object.f: ${formulaField.slice(0, 50)}`)
    }
  }
}

/**
 * L4.91 PR0 扩展 (Q10A): 显式 kind 优先级 > auto-detect.
 * caller 显式声明 'yoy_pct' / 'yoy_pp' / 'yoy_day' / 'text' / 'number' 时, 直接返回.
 * 否则 fallback 到 Sprint 174 后缀 auto-detect (向后兼容).
 */
function getColumnKind(col: XlsxColumn): 'yoy_pct' | 'yoy_pp' | 'yoy_day' | 'text' | 'number' | 'auto' {
  if (col.kind && col.kind !== 'auto') return col.kind
  // auto-detect (Sprint 174 兼容, 跟之前 isYoyColumn + isPpColumn 1:1 stable 永久规则化沿用)
  if (YOY_PP_PATTERN.test(col.key) || YOY_PP_PATTERN.test(col.header)) return 'yoy_pp'
  if (YOY_DAY_PATTERN.test(col.key) || YOY_DAY_PATTERN.test(col.header)) return 'yoy_day'
  if (YOY_PCT_PATTERN.test(col.key) || YOY_PCT_PATTERN.test(col.header)) return 'yoy_pct'
  return 'text'
}

/**
 * L4.91 PR0 重构 (替代 Sprint 174 isYoyColumn + isPpColumn):
 * 用 kind 显式 enum 替代两个独立函数, 跟 caller 显式声明 1:1 stable 永久规则化沿用.
 * (isPpColumn 已合并到 getColumnKind → 'yoy_pp' 显式分支, 不再需要单独函数)
 */
function isYoyColumn(col: XlsxColumn): boolean {
  const k = getColumnKind(col)
  return k === 'yoy_pct' || k === 'yoy_pp' || k === 'yoy_day'
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
    // L4.91.1 (2026-07-11): per-row numFmt override 独立数组 (跟 aoa 平行, 索引 0=header 1..N=row 1..N)
    //   formatValue 返回 { val, numFmt } 时, 同时切换 cell value 和 numFmt
    const numFmtOverrides: (Record<number, string | undefined> | null)[] = [null]

    for (const row of data) {
      const rowArr: unknown[] = []
      const rowNumFmtOverrides: Record<number, string | undefined> = {}
      for (let c = 0; c < columns.length; c++) {
        const col = columns[c]
        let val = row[col.key]
        // L4.91.1 (2026-07-11) 治本 market-focus#product-customer 对比行格式错:
        //   跟 L4.91 PR0 kind enum + L4.50 0 业务代码改动 + user 限制 "其他前端不要调整逻辑" 1:1 stable 永久规则化沿用
        //   per-row dispatch: 对比行 (isChangeRow/isYoyRow) 用 _yoy_pct / _yoy_pp 后缀字段, normal row 用原字段
        if (col.formatValue) {
          const result = col.formatValue(val, row)
          if (result && typeof result === 'object' && 'val' in result) {
            val = result.val
            rowNumFmtOverrides[c] = result.numFmt ?? col.numFmt
          } else {
            val = result
          }
        }
        assertNotFormula(val)
        rowArr.push(val != null ? val : '')
      }
      aoa.push(rowArr)
      numFmtOverrides.push(
        Object.keys(rowNumFmtOverrides).length > 0 ? rowNumFmtOverrides : null
      )
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

    // ── 数字格式 (numFmt) 单独设 (Sprint 174 SSOT + L4.91 PR0 caller 优先级) ──
    // L4.91 PR0 修复 (Q10A + B16): caller 显式 `kind` 优先级 > auto-detect > caller `numFmt` fallback.
    // 优先级链: kind 显式 enum > key/header suffix auto-detect > caller numFmt (向后兼容)
    for (let r = 1; r < aoa.length; r++) {
      for (let c = 0; c < columns.length; c++) {
        const col = columns[c]
        const cell = XLSX.utils.encode_cell({ r, c })
        const kind = getColumnKind(col)
        const isNumeric = typeof aoa[r][c] === 'number'

        if (isNumeric && (kind === 'yoy_pct' || kind === 'yoy_pp' || kind === 'yoy_day')) {
          // L4.91 PR0: caller 显式 kind 决定的 numFmt 优先级最高 (跟 backend L4.81 no *100 契约 1:1 stable 永久规则化沿用)
          // yoy_pct: raw 0.25 → 25.00% 显示 (Excel *100, 不需要 caller numFmt)
          // yoy_pp: raw 0.05 → +5.00pp 显示 (Excel *100, pp 后缀)
          // yoy_day: raw 3 → +3天 显示 (无 %, raw integer 天数差)
          let fmt: string
          if (kind === 'yoy_pp') {
            fmt = '0.00%;-0.00%;0.00%'  // pp 差 (跟 L4.81 后端契约 1:1 stable, raw *100)
          } else if (kind === 'yoy_day') {
            fmt = '+0;-0;0'  // 天数差 (signed integer, L4.91 扩展)
          } else {
            fmt = '+0.00%;-0.00%;0.00%'  // yoy_pct percentage (signed percentage)
          }
          if (!ws[cell]) ws[cell] = {}
          ws[cell].z = fmt
        } else if (isNumeric && col.numFmt) {
          // 非 YOY 数字列: caller numFmt 优先 (L4.91 PR0 caller 优先级)
          // L4.91.1 (2026-07-11): per-row numFmt override (formatValue 返回 { val, numFmt })
          const perRowFmt = numFmtOverrides[r]?.[c]
          if (!ws[cell]) ws[cell] = {}
          ws[cell].z = perRowFmt ?? col.numFmt
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
