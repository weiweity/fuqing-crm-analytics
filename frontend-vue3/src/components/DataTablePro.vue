<script setup lang="ts">
import { NDataTable } from 'naive-ui'
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'

interface Props {
  columns: DataTableColumns<any>
  data: any[]
  loading?: boolean
  bordered?: boolean
  size?: 'small' | 'medium' | 'large'
  pagination?: false | { pageSize: number }
  rowKey?: string | ((row: any) => DataTableRowKey)
  className?: string
  maxHeight?: number | string
  scrollX?: number | string
  striped?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  bordered: true,
  size: 'small',
  pagination: () => ({ pageSize: 10 }),
  rowKey: 'key',
  striped: false,
})

const emit = defineEmits<{
  (e: 'update:sorter', sorter: any): void
}>()

const createRowKey = (row: any) => {
  if (typeof props.rowKey === 'function') {
    return props.rowKey(row)
  }
  return row[props.rowKey] as DataTableRowKey
}
</script>

<template>
  <n-data-table
    :columns="columns"
    :data="data"
    :loading="loading"
    :bordered="bordered"
    :size="size"
    :pagination="pagination"
    :max-height="maxHeight"
    :scroll-x="scrollX"
    :striped="striped"
    :row-key="createRowKey"
    class="bi-table"
    :class="className"
    @update:sorter="emit('update:sorter', $event)"
  />
</template>
