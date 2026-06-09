import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Sprint 11: 修用户报 Cmd+Shift+R 刷不了前端缓存.
// vite 默认 Cache-Control: no-cache 允许 "先 revalidate 再用",
// 但浏览器内存里的旧 module 仍可能 HMR 不更新.
// 改用显式 no-store 头 + HMR full-reload fallback:
//   - no-store: 强制每次都从 server 拉, 不允许 revalidate
//   - handleHotUpdate: 每次文件改动触发 server.ws.send({type:'full-reload'})
//     强制浏览器整页 reload, 跳过内存 HMR cache
export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'sprint11-force-reload-on-hmr',
      handleHotUpdate({ server }) {
        server.ws.send({ type: 'full-reload' })
        return []
      },
    },
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
    // 显式 no-store: 比 no-cache 更强, 强制每次从 server 拉新
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0',
    },
  },
})
