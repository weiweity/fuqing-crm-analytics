<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppFilterBar from '@/components/AppFilterBar.vue'
import NavBar from '@/components/NavBar.vue'

const route = useRoute()
const isImmersive = computed(() => route.meta.immersive === true)
</script>

<template>
  <div class="flex h-screen flex-col overflow-hidden" :class="isImmersive ? 'bg-[#061018]' : 'bg-slate-100'">
    <NavBar />
    <div v-if="!isImmersive" class="bg-slate-100">
      <div class="mx-auto max-w-[1600px]">
        <AppFilterBar />
      </div>
    </div>
    <main class="flex-1 overflow-y-auto" :class="isImmersive ? 'p-5 bg-[#061018]' : 'p-5'">
      <div :class="isImmersive ? 'max-w-[1800px] mx-auto' : 'max-w-[1600px] mx-auto'">
        <slot />
      </div>
    </main>
  </div>
</template>
