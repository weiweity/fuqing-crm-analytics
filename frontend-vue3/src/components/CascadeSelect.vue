<script setup lang="ts" generic="T extends string | number">

import { NSelect, type SelectOption } from 'naive-ui'

export interface CascadeLevel {
  /** Level key used in v-model binding */
  key: string
  /** Label shown in UI */
  label: string
  /** Current selected value (v-model) */
  value: string
  /** Available options for this level */
  options: SelectOption[]
  /** Placeholder text */
  placeholder?: string
  /** Width of the select */
  width?: number | string
}

const props = defineProps<{
  /** Cascade levels from L1 to L3 */
  levels: CascadeLevel[]
  /** Callback fired when any level changes - handles clear of dependent levels + API call */
  onChange: (changedKey: string, newValue: string) => void
}>()

const emit = defineEmits<{
  'update:levels': [levels: CascadeLevel[]]
}>()

/**
 * Handle selection change for a specific level
 * - Updates the level's value
 * - Clears all dependent levels (levels after the changed one)
 * - Calls onChange callback for API fetching
 */
function handleChange(levelKey: string, newValue: string) {
  const levelIndex = props.levels.findIndex((l) => l.key === levelKey)
  if (levelIndex === -1) return

  // Update the changed level
  const updatedLevels = props.levels.map((level, idx) => {
    if (idx === levelIndex) {
      return { ...level, value: newValue }
    }
    // Clear dependent levels (levels after the changed one)
    if (idx > levelIndex) {
      return { ...level, value: '' }
    }
    return level
  })

  emit('update:levels', updatedLevels)

  // Notify parent to fetch new options for dependent levels
  props.onChange(levelKey, newValue)
}


</script>

<template>
  <div class="flex items-center gap-3">
    <template v-for="(level, index) in levels" :key="level.key">
      <!-- Level label -->
      <span v-if="level.label" class="text-sm text-gray-500 whitespace-nowrap">
        {{ level.label }}
      </span>

      <!-- Level selector -->
      <n-select
        :model-value="level.value"
        :options="level.options"
        :placeholder="level.placeholder ?? `请选择${level.label}`"
        :style="{ width: (level.width ?? 140) + 'px' }"
        size="small"
        clearable
        @update:model-value="(val: string) => handleChange(level.key, val)"
      />

      <!-- Separator between levels (not after last level) -->
      <span v-if="index < levels.length - 1" class="text-gray-300">/</span>
    </template>
  </div>
</template>
