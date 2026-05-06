<script setup lang="ts">
import { NButton, NButtonGroup } from 'naive-ui'
import { exportSheetToXlsx, type XlsxColumn } from '@/utils/exportXlsx'

const props = defineProps<{
  /** 导出文件名前缀 */
  filename: string
  /** Excel 列定义（传了才显示 Excel 按钮） */
  columns?: XlsxColumn[]
  /** Excel 数据行 */
  data?: Record<string, any>[]
  /** 工作表名 */
  sheetName?: string
  /** 图表组件 ref（传了才显示图片按钮） */
  chartRef?: { exportAsPng: (filename: string) => void } | null
}>()

function handleExportExcel() {
  if (!props.columns || !props.data) return
  exportSheetToXlsx(
    props.filename,
    props.sheetName || '数据',
    props.columns,
    props.data,
  )
}

function handleExportImage() {
  if (!props.chartRef) return
  props.chartRef.exportAsPng(props.filename)
}
</script>

<template>
  <NButtonGroup size="tiny">
    <NButton v-if="columns && data" @click="handleExportExcel">
      📊 导出Excel
    </NButton>
    <NButton v-if="chartRef" @click="handleExportImage">
      🖼️ 导出图片
    </NButton>
  </NButtonGroup>
</template>
