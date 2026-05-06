<script setup lang="ts">
import Sidebar from '@/components/Sidebar.vue'
import AppFilterBar from '@/components/AppFilterBar.vue'
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-slate-100">
    <Sidebar />
    <div class="flex flex-col flex-1 overflow-hidden">
      <AppFilterBar />
      <main class="flex-1 overflow-y-auto p-5">
        <div class="max-w-[1600px] mx-auto">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
