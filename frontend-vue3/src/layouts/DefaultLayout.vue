<script setup lang="ts">
import AppFilterBar from '@/components/AppFilterBar.vue'
import NavBar from '@/components/NavBar.vue'
</script>

<template>
  <div class="flex h-screen flex-col overflow-hidden bg-slate-100">
    <NavBar />
    <div class="bg-slate-100">
      <div class="mx-auto max-w-[1600px]">
        <AppFilterBar />
      </div>
    </div>
    <main class="flex-1 overflow-y-auto p-5">
      <div class="max-w-[1600px] mx-auto">
        <slot />
      </div>
    </main>
  </div>
</template>
