# 天猫CRM 前端

Vue 3 + Vite + TypeScript + Tailwind CSS + naive-ui 构建的 CRM 数据分析前端。

## 技术栈

- Vue 3 (Composition API + `<script setup>`)
- Vite 5
- TypeScript
- Tailwind CSS
- naive-ui
- ECharts 5
- Pinia + TanStack Query

## 开发

```bash
npm install
npm run dev
```

访问 http://localhost:5173

## 构建

```bash
npm run build
```

产物输出到 `dist/`，可部署到 Nginx 静态托管。

## 测试

```bash
# 类型检查
npx vue-tsc --noEmit

# E2E 测试
npx playwright test
```
