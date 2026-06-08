/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Sprint 11 S11-4: vitest 单元测试配置
// 跟 vite.config.ts 共享 alias + vue plugin
// jsdom env 给组件挂载 DOM
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{ts,tsx,js,jsx}'],
    exclude: ['node_modules', 'dist', 'e2e'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{vue,ts}'],
      exclude: ['src/**/*.{test,spec}.{ts,tsx}', 'src/main.ts', 'src/router.ts'],
    },
  },
})
