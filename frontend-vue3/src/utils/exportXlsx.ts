/**
 * Excel 导出工具 — 基于 xlsx (SheetJS)
 * 支持：表头样式、列宽、数字/百分比格式、合并单元格
 *
 * xlsx 通过动态 import() 按需加载，不进入首屏 bundle。
 * 首次点击导出时有 ~300ms 加载延迟，后续调用使用缓存。
 */

let _XLSX: typeof import('xlsx') | null = null

async function _getXLSX(): Promise<typeof import('xlsx')> {
  if (!_XLSX) {
    _XLSX = await import('xlsx')
  }
  return _XLSX
}

export interface XlsxColumn {
  /** 列标题（中文） */
  header: string
  /** 数据字段 key */
  key: string
  /** 列宽（字符数） */
  width?: number
  /** 数字格式，如 '#,##0' / '0.00%' / '¥#,##0' */
  numFmt?: string
}

export interface XlsxSheetConfig {
  /** 工作表名 */
  name: string
  columns: XlsxColumn[]
  data: Record<string, any>[]
}

/**
 * 将多张表导出为一个 .xlsx 文件
 * - 自动设置列宽、表头样式、数字格式
 * - 百分比原始值(0.21)写入后格式化为 21.00%
 */
export async function exportToXlsx(filename: string, sheets: XlsxSheetConfig[]): Promise<void> {
  const XLSX = await _getXLSX()
  const wb = XLSX.utils.book_new()

  for (const sheet of sheets) {
    const { columns, data, name } = sheet

    // 构建表头行
    const header = columns.map((c) => c.header)

    // 构建数据行：按 columns 顺序提取值
    const rows = data.map((row) =>
      columns.map((col) => {
        const val = row[col.key]
        return val != null ? val : ''
      })
    )

    // 构建 AOA (array of arrays)
    const aoa = [header, ...rows]
    const ws = XLSX.utils.aoa_to_sheet(aoa)

    // 设置列宽
    ws['!cols'] = columns.map((c) => ({
      wch: c.width || Math.max(c.header.length * 2, 10),
    }))

    // 设置数字格式（从第2行开始，第1行是表头）
    if (ws['!data']) {
      for (let r = 1; r < aoa.length; r++) {
        for (let c = 0; c < columns.length; c++) {
          const cell = ws['!data'][r]?.[c]
          if (!cell || cell.t !== 'n') continue
          if (columns[c].numFmt) {
            cell.z = columns[c].numFmt
          }
        }
      }
    }

    XLSX.utils.book_append_sheet(wb, ws, name.substring(0, 31)) // Sheet名最长31字符
  }

  XLSX.writeFile(wb, `${filename}.xlsx`)
}

/**
 * 便捷方法：单表导出
 */
export async function exportSheetToXlsx(
  filename: string,
  sheetName: string,
  columns: XlsxColumn[],
  data: Record<string, any>[],
): Promise<void> {
  await exportToXlsx(filename, [{ name: sheetName, columns, data }])
}
