<script setup lang="ts">
import { exportSheetToXlsx, type XlsxColumn } from '@/utils/exportXlsx'
import BaseStyleButton from './BaseStyleButton.vue'

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

async function handleExportExcel() {
  if (!props.columns || !props.data) return
  try {
    await exportSheetToXlsx(
      props.filename,
      props.sheetName || '数据',
      props.columns,
      props.data,
    )
  } catch (err) {
    console.error('Excel 导出失败:', err)
  }
}

function handleExportImage() {
  if (!props.chartRef) return
  props.chartRef.exportAsPng(props.filename)
}
</script>

<template>
  <div class="export-toolbar">
    <BaseStyleButton
      v-if="columns && data"
      mode="neutral"
      custom-class="export-toolbar__btn"
      @click="handleExportExcel"
    >
      导出Excel
    </BaseStyleButton>
    <BaseStyleButton
      v-if="chartRef"
      mode="neutral"
      custom-class="export-toolbar__btn"
      @click="handleExportImage"
    >
      导出图片
    </BaseStyleButton>
  </div>
</template>

<style scoped>
.export-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
