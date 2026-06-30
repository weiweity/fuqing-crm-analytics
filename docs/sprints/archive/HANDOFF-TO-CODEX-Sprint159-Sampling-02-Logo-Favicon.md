# HANDOFF TO CODEX — Sprint 159 派样 02 板块重排 + Logo/Favicon 固定化

> **目标**: 派样 02 回购周期分布板块重排 (类似总览 5 卡片格式) + NavBar logo 改 png (base64 inline) + 浏览器 favicon 改 png (base64 inline)
>
> **Stage 1 (Claude)**: 写架构 + handoff ✅
> **Stage 2 (Codex 实施)**: 你读这文档后直接实施, 不动 git (不 commit / push / merge)
> **Stage 3 (Claude)**: review + 12 步流程收口
>
> 跟 Sprint 158 模式 stable 1 turn 跑完, 你有发挥空间 (Vue 3 + Naive UI + ECharts 集成).
> **关键: user 报"固定化调整 + 我之前改的又调整回去了" — 你不要再改回 Sprint 158 文字 logo 方案, 严格走 base64 inline png 治根**

---

## 1. User 反馈 (3 改动 + 1 担忧)

### 1.1 派样 02 回购周期分布板块重排

User 当前看到的 (Sprint 158 实施完):
- 02 板块显示: 4 桶回购周期柱状图 (0-7d / 8-30d / 31-60d / 61-90d) + 滚动去年对比
- 风格: 卡片 + 标题 + 柱状图 + 导出图片按钮
- user 报"类似总览卡片" 反馈: 改成像 01 总览 4 卡片格式

User 期望 (拍板):
- 02 板块改成 5 卡片 (跟 01 总览同 layout 风格 + 加 AUS 卡片)
  - 卡片 1: 派样人数 (2026 1,334 + YOY badge)
  - 卡片 2: 回购人数 (2026 + YOY badge)
  - 卡片 3: 正装回购人数 (2026 + YOY badge)
  - 卡片 4: 正装回购 GSV (2026 ¥13.9万 + YOY badge)
  - 卡片 5: AUS (2026 ¥104 / 2025 ¥47 双值 + YOY badge)
- 删原来的 4 桶柱状图 (跟 user 报"类似的数据不用保留" 一致)
- 删 4 桶"滚动去年"柱状图 (Sprint 158 加的)
- 删 导出图片按钮 (无数据可导)

数据来源: 跟 01 总览卡片同, 用 `roiData.summary.channels[TTL派样]` 里的数据 (sample_users / repurchase_users / full_repurchase_users / full_repurchase_gsv / full_repurchase_aus), YOY/MOM 字段从 `compareValue` helper 拿 (跟 03 板块卡片同).

### 1.2 NavBar logo 改 png

User 当前看到的 (Sprint 158 收口后):
- NavBar 顶部 header 圆形 logo: 文字"天" 占位符 (Sprint 158 png LFS fail 治根)
- 视觉: `background: rgba(255, 255, 255, 0.18); border: 1.5px solid rgba(255, 255, 255, 0.4); border-radius: 50%;` + 文字"天"

User 期望 (拍板): 用 png 文件 (跟 user 报 image #7 一致):
- png 源文件: `/Users/hutou/Downloads/logo2.png` (3KB)
- 期望: NavBar 顶部 header 圆形 logo 用 png 替代文字"天"
- user 担忧: "我之前改的又调整回去了" — 你不要再改回 Sprint 158 文字 logo 方案

### 1.3 浏览器 tab favicon 改 png

User 当前看到的 (Sprint 158 收口后):
- 浏览器 tab: favicon.svg (Sprint 158 png LFS fail 治根, 删了 favicon.png)
- 实际: index.html 只 link favicon.svg, 删了 favicon.png (跟 .gitattributes `*.png filter=lfs` 冲突)

User 期望 (拍板): 用 png 文件 (跟 user 报 image #8 一致):
- png 源文件: `/Users/hutou/Downloads/芙清logo.png` (21KB)
- 期望: 浏览器 tab favicon 用 png 替代 svg
- 跟 1.2 logo 一样, "我之前改的又调整回去了" 你不要再改回 Sprint 158 svg 方案

---

## 2. 资产策略 (治根, 避免 LFS 推送 fail 复发)

### 2.1 png LFS fail 根因 (Sprint 158 治标复发)

Sprint 158 push 报 `GH008: Your push referenced at least 2 unknown Git LFS objects`:
- 仓库有 `.gitattributes` `*.png filter=lfs diff=lfs merge=lfs -text` 规则
- 但 git lfs 凭证缺 (本地没装 `git lfs` 凭证, 远端 LFS storage 走通需要 GitHub LFS 配置)
- Codex 直接 `git add` png, 触发 LFS filter, 但 LFS objects 没上传, push fail

### 2.2 拍板: base64 inline 治根 (不依赖 LFS, 永远不 fail)

Sprint 159 治根方案:
- **不依赖 png 文件** (避免 LFS filter)
- **不依赖 .gitattributes 改动** (避免项目规范改)
- **base64 inline png 到 Vue 组件 / HTML** (跟 data URI 同理, 0 推送问题)

实施方案:

**NavBar.vue** logo 改 base64 inline:
```vue
<template>
  <div class="navbar-brand">
    <img class="navbar-logo" :src="logoDataUri" alt="天猫CRM" />
    <div class="min-w-0">
      <h1 class="text-base font-semibold leading-tight text-white">天猫CRM</h1>
      <p class="mt-0.5 text-[11px] font-medium leading-tight text-white/70">数据分析平台</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import logoPngBase64 from '@/assets/logo2.png?raw&base64'  // 1. 读 png → base64 string
// 2. data URI: data:image/png;base64,<base64>
const logoDataUri = computed(() => `data:image/png;base64,${logoPngBase64}`)
</script>
```

**vite.config.ts** 加 `?raw` + `?base64` 插件支持:
```ts
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'fs'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue(),
    // 自定义 ?raw&base64 插件: 读文件 → base64 string
    {
      name: 'raw-base64',
      transform(code, id) {
        if (id.includes('?raw&base64')) {
          const filePath = id.split('?')[0]
          const content = readFileSync(resolve(filePath)).toString('base64')
          return {
            code: `export default ${JSON.stringify(content)}`,
            map: null,
          }
        }
      },
    },
  ],
})
```

或者更简单 (不写 vite 插件, 直接 hardcode base64 string):
```vue
<script setup lang="ts">
// Stage 2 拍板: 直接 hardcode base64 字符串 (3KB png → ~4KB base64), 不依赖 vite 插件
const logoPngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAA...<完整 base64>'
const logoDataUri = `data:image/png;base64,${logoPngBase64}`
const faviconDataUri = 'iVBORw0KGgoAAAANSUhEUgAAA...<完整 base64>'
</script>
```

**index.html** favicon 改 base64 inline (用 meta 或 link 嵌入):
```html
<link rel="icon" type="image/png" :href="faviconDataUri" />
```

或者更简单 (index.html 没法用 script, 静态 inline):
```html
<!-- Stage 2 拍板: 用 <link rel="icon" href="data:image/png;base64,..."/> 内嵌 base64 -->
<link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAA..." />
```

**Png 源文件处理** (关键):
- `/Users/hutou/Downloads/logo2.png` (3KB) → Codex 自己用 `base64` 命令或 `cat` 工具生成 base64 string
- `/Users/hutou/Downloads/芙清logo.png` (21KB) → 同样
- **不要 cp 到 `frontend-vue3/public/`** (避免 LFS filter 触发, 跟 Sprint 158 推送 fail 复发)
- 临时放本地 `/tmp/` 用于生成 base64, 不 commit

### 2.3 为什么 base64 inline 治本 (跟 LFS 治本对比)

| 方案 | 优点 | 缺点 | 推送 fail 风险 |
|---|---|---|---|
| Sprint 158 文字 logo (治标) | 0 png 资产, 永远不 fail | 跟 user 期望 png 视觉不一致 | 0 |
| Sprint 159 base64 inline (治本) | 跟 user 期望 png 视觉一致 + 0 推送 fail 风险 | 1.5KB / 21KB base64 字符串会增大代码体积 | 0 |
| LFS 治根 (.gitattributes + git lfs track) | 真 png 资产上仓, 视觉一致 | 需 Git LFS 凭证 (GitHub LFS storage 配置), 跨 sprint 跨项目治理 | 高 (凭证缺就 fail) |

**拍板: base64 inline 治本** — 跟 user 期望 png 视觉一致, 0 推送 fail 风险, 不依赖外部凭证.

---

## 3. 现状摸底 (L3 精准修改起点)

### 3.1 文件清单 (改动范围 2 files)

| 文件 | 当前状态 | Sprint 159 改动 |
|---|---|---|
| `frontend-vue3/src/components/NavBar.vue` | 文字 "天" 占位符 (`.navbar-logo-placeholder` div) | 删 placeholder, 加 base64 inline `<img>` logo |
| `frontend-vue3/src/views/SamplingView.vue` | 02 板块: 4 桶柱状图 + 滚动去年对比 + sr-only table | 删柱状图 + 滚动去年 + sr-only table + export button, 改 5 卡片格式 (跟 01 总览同) |
| `frontend-vue3/index.html` | `<link rel="icon" type="image/svg+xml" href="/favicon.svg?v=20260629" />` | 改 `<link rel="icon" type="image/png" href="data:image/png;base64,..." />` |

### 3.2 NavBar.vue 当前 logo 块 (line 86-94)

```vue
<div class="navbar-brand">
  <div class="navbar-logo-placeholder">天</div>
  <div class="min-w-0">
    <h1 class="text-base font-semibold leading-tight text-white">天猫CRM</h1>
    <p class="mt-0.5 text-[11px] font-medium leading-tight text-white/70">数据分析平台</p>
  </div>
</div>
```

`.navbar-logo-placeholder` CSS (Sprint 158 加):
```css
.navbar-logo-placeholder {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  border: 1.5px solid rgba(255, 255, 255, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 15px;
  color: #fff;
}
```

Sprint 159 改动: 删 `.navbar-logo-placeholder` div + CSS, 加 base64 inline `<img class="navbar-logo">` (复用 Sprint 158 删了的 `.navbar-logo` CSS):
```css
.navbar-logo {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 50%;
  object-fit: contain;
  background: rgba(255, 255, 255, 0.18);
  border: 1.5px solid rgba(255, 255, 255, 0.4);
  padding: 4px;
}
```

### 3.3 SamplingView.vue 02 板块当前 (Sprint 158 实施)

派样 02 板块: `回购周期分布` (line 718-777 原始, Sprint 158 上移到 02 位置)
- `<n-card>` 包含:
  - `<div ref="recharts">` 4 桶柱状图 (0-7d / 8-30d / 31-60d / 61-90d)
  - 滚动去年对比 (Sprint 158 加的双柱图)
  - sr-only 真 table (4 桶) 屏幕阅读器
  - 导出图片按钮 (Sprint 158 加的)
- `compareData` 跟 `buckets` 数据从 `repurchaseCompareDistribution` useQuery 拿

Sprint 159 改动: **删整个 02 板块卡片** (`<n-card>` 包含柱状图/滚动去年/sr-only table/export 全部), 改 5 卡片格式 (跟 01 总览 layout 风格).

### 3.4 01 总览 5 卡片格式参考 (Sprint 158 实施)

派样 01 总览 (line 496-540 当前):
```vue
<section class="sampling-section" aria-labelledby="sampling-section-overview">
  <h2 class="section-title"><span class="section-num">01</span>总览</h2>
  <n-grid :cols="4" :x-gap="16" :y-gap="16" class="mb-4" responsive="screen">
    <n-gi>
      <n-card :bordered="false" segmented>
        <div class="text-sm text-slate-500">派样人数</div>
        <div class="text-3xl font-bold tabular-nums text-slate-800 mt-2">
          {{ formatNumber(totalSampleUsers) }}
        </div>
        <div class="text-xs text-slate-400 mt-1">TTL (U先 ∪ 百补, 去重)</div>
      </n-card>
    </n-gi>
    <!-- 同样格式 3 卡片: 回购人数 / 正装回购人数 / 正装 GSV -->
  </n-grid>
</section>
```

派样 02 板块新 5 卡片 (Sprint 159 改):
- 派样人数
- 回购人数
- 正装回购人数
- 正装回购 GSV (¥13.9万)
- AUS (¥104 / 2025 ¥47 双值 + YOY badge)

数据结构: 跟 03 板块卡片同 (用 `compareValue` helper 拿 YOY/MOM):
```ts
const totalRepurchaseUsers = computed(() => ttlSummary.value?.repurchase_users ?? 0)
const totalFullRepurchaseUsers = computed(() => ttlSummary.value?.full_repurchase_users ?? 0)
const totalFullRepurchaseGsv = computed(() => ttlSummary.value?.full_repurchase_gsv ?? 0)
const totalFullRepurchaseAus = computed(() => safeRatio(totalFullRepurchaseGsv.value, totalFullRepurchaseUsers.value))
```

(上面这些 computed 已经在 Sprint 140+146+154 实施, 你直接用).

---

## 4. 实施范围 (你的发挥空间)

### 4.1 必须做 (架构定下)

1. **NavBar.vue** 改 base64 inline logo (不写 vite 插件, 直接 hardcode base64 字符串到 .vue `<script setup>`):
   - 删 `.navbar-logo-placeholder` div (line 87) + CSS (line 178-189)
   - 删 `import { computed, onBeforeUnmount, ref } from 'vue'` 中的 `computed` 如果不再用 (Sprint 158 用了)
   - 加 base64 const `const logoPngBase64 = '...'` + computed `const logoDataUri = computed(() => \`data:image/png;base64,${logoPngBase64}\`)`
   - 改 template `<img class="navbar-logo" :src="logoDataUri" alt="天猫CRM" />`
   - 复用 Sprint 158 删掉的 `.navbar-logo` CSS (38x38 圆形, 加 padding + object-fit: contain + 半透明白背景)
2. **index.html** 改 base64 inline favicon:
   - 删 `<link rel="icon" type="image/svg+xml" href="/favicon.svg?v=20260629" />`
   - 加 `<link rel="icon" type="image/png" href="data:image/png;base64,..." />` (base64 字符串内嵌)
3. **SamplingView.vue** 改 02 板块 5 卡片 (跟 01 总览同 layout 风格):
   - 删整个 02 板块卡片 (含柱状图/滚动去年/sr-only table/export 按钮)
   - 加 5 卡片 (派样人数/回购人数/正装回购人数/正装 GSV/AUS) 跟 01 总览同 n-grid :cols="4" 改 n-grid :cols="5" 容纳 5 卡片
   - AUS 卡片用双值 format (跟 03 板块 `¥{{ formatCurrency(ch.full_repurchase_gsv, 'wan') }}` 类似)
   - YOY badge 用 `compareValue` helper 拿 (跟 03 板块同)
   - **删 repurchaseDistribution useQuery** (02 板块不要了, 解放 1 个 query)
   - **删 repurchaseCompareDistribution useQuery** (Sprint 158 加的滚动去年)
   - **删 repurchaseBuckets computed** (02 板块数据)
   - **删 repurchaseCompareRange** (Sprint 158 加的)
   - **删 `fetchSamplingRepurchaseDistribution` import** (不再需要)
4. `cd frontend-vue3 && npm run build` 验证 (vue-tsc + vite PASS)

### 4.2 推荐设计 (你的发挥空间)

#### 4.2.1 02 板块 5 卡片 layout (跟 01 总览 4 卡片同)

```vue
<section class="sampling-section" aria-labelledby="sampling-section-buckets">
  <h2 id="sampling-section-buckets" class="section-title"><span class="section-num">02</span>回购周期分布</h2>
  <n-grid :cols="5" :x-gap="16" :y-gap="16" class="mb-4" responsive="screen">
    <n-gi>
      <n-card :bordered="false" segmented>
        <div class="text-sm text-slate-500">派样人数</div>
        <div class="text-3xl font-bold tabular-nums text-slate-800 mt-2">
          {{ formatNumber(totalSampleUsers) }}
        </div>
        <div class="text-xs text-slate-400 mt-1">TTL (U先 ∪ 百补, 去重)</div>
      </n-card>
    </n-gi>
    <n-gi>
      <n-card :bordered="false" segmented>
        <div class="text-sm text-slate-500">回购人数</div>
        <div class="text-3xl font-bold tabular-nums text-slate-800 mt-2">
          {{ formatNumber(totalRepurchaseUsers) }}
        </div>
        <div class="text-xs text-slate-400 mt-1">回购率 {{ formatPercent(totalRepurchaseRate) }}</div>
      </n-card>
    </n-gi>
    <n-gi>
      <n-card :bordered="false" segmented>
        <div class="text-sm text-slate-500">正装回购人数</div>
        <div class="text-3xl font-bold tabular-nums text-rose-600 mt-2">
          {{ formatNumber(totalFullRepurchaseUsers) }}
        </div>
        <div class="text-xs text-slate-400 mt-1">
          正装转化率 {{ formatPercent(totalFullRepurchaseRate) }}
        </div>
      </n-card>
    </n-gi>
    <n-gi>
      <n-card :bordered="false" segmented>
        <div class="text-sm text-slate-500">正装回购 GSV</div>
        <div class="text-3xl font-bold tabular-nums text-emerald-600 mt-2">
          {{ formatCurrency(totalFullRepurchaseGsv, 'wan') }}
        </div>
        <div class="text-xs text-slate-400 mt-1">
          AUS ¥{{ totalFullRepurchaseAus.toFixed(0) }}
        </div>
      </n-card>
    </n-gi>
    <n-gi>
      <n-card :bordered="false" segmented>
        <div class="text-sm text-slate-500">AUS</div>
        <div class="text-3xl font-bold tabular-nums text-slate-800 mt-2">
          ¥{{ totalFullRepurchaseAus.toFixed(0) }}
        </div>
        <div class="text-xs text-slate-400 mt-1">客单价 (U先 + 百补 + TTL)</div>
      </n-card>
    </n-gi>
  </n-grid>
</section>
```

#### 4.2.2 NavBar logo base64 inline 模板

```vue
<script setup lang="ts">
import { ref, onBeforeUnmount, watch } from 'vue'  // 删 computed (不再用)
import { useRoute, useRouter } from 'vue-router'
import { NAV_ITEMS, type NavItem } from '@/config/navigations'

// Sprint 159: Logo base64 inline png (3KB → 4KB base64) 治 LFS push fail 根因
const logoPngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAA...<完整 base64>'
const logoDataUri = `data:image/png;base64,${logoPngBase64}`

// ... 其他 logic 不变
</script>

<template>
  <header class="navbar-shell">
    <div class="navbar-header">
      <div class="navbar-header-row">
        <div class="navbar-brand">
          <img class="navbar-logo" :src="logoDataUri" alt="天猫CRM" />
          <div class="min-w-0">
            <h1 class="text-base font-semibold leading-tight text-white">天猫CRM</h1>
            <p class="mt-0.5 text-[11px] font-medium leading-tight text-white/70">数据分析平台</p>
          </div>
        </div>
        <!-- ... 右侧 user menu 不变 ... -->
      </div>
    </div>
    <!-- ... 6 板块 tabs 不变 ... -->
  </header>
</template>
```

#### 4.2.3 index.html favicon base64 inline

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <!-- Sprint 159: Favicon base64 inline png (21KB → 28KB base64) 治 LFS push fail 根因 -->
    <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA...<完整 base64>" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>芙清 CRM - 数据分析平台</title>
  </head>
  <body>
    <!-- ... 不变 ... -->
  </body>
</html>
```

---

## 5. Png → base64 转换 (Codex 自己用 shell 跑)

```bash
# 1. 读 logo2.png 转 base64
LOGO_BASE64=$(base64 -i /Users/hutou/Downloads/logo2.png | tr -d '\n')
echo "Logo base64: $LOGO_BASE64"  # 复制到 NavBar.vue logoPngBase64 const

# 2. 读 芙清logo.png 转 base64
FAVICON_BASE64=$(base64 -i /Users/hutou/Downloads/芙清logo.png | tr -d '\n')
echo "Favicon base64: $FAVICON_BASE64"  # 复制到 index.html link href

# 3. 验证 base64 长度 (logo2.png 3KB → ~4KB base64; 芙清logo.png 21KB → ~28KB base64)
echo "Logo base64 length: ${#LOGO_BASE64}"
echo "Favicon base64 length: ${#FAVICON_BASE64}"
```

**Codex 实施时必跑这两个 base64 命令**, 把输出 copy 到 .vue / .html.

---

## 6. 验收标准

### 6.1 build / lint / pytest
- `cd frontend-vue3 && npm run build` PASS (vue-tsc + vite, ~750ms)
- pre-commit hook 全过: vite build + L1 SQL f-string consistency lint 0 violations + ruff F841 PASS
- `python -m backend.contracts._lint` OK (后端 0 改动)
- `pytest backend/tests/` 741 passed / 66 skipped (跟 Sprint 158 baseline 一致, L4.4 race flake 接受)

### 6.2 视觉验收 (user 试看)
- ✅ 派样 02 板块显示 5 卡片 (派样人数/回购人数/正装回购人数/正装 GSV/AUS) 跟 01 总览同 layout
- ✅ 删 4 桶柱状图 + 滚动去年对比 + sr-only table + 导出图片按钮
- ✅ NavBar 顶部 header logo 用 png (image #7) 替代文字 "天"
- ✅ 浏览器 tab favicon 用 png (image #8 芙清logo)
- ✅ 页面 0 推送 LFS fail (base64 inline 治根)

### 6.3 git log 干净
- 1 个 commit (Sprint 159), 改了 3 files (NavBar.vue / SamplingView.vue / index.html)
- commit message: `feat(sampling-ui): Sprint 159 派样 02 5 卡片重排 + NavBar logo 改 png + favicon 改 png (base64 inline 治 LFS 推送 fail)`
- L4.7 100% 精准: 不动 router / 后端 / 任何 png 文件 (治根 LFS 不用 png 二进制)
- **不要 commit png 文件** (避免 LFS filter 触发, 跟 Sprint 158 push fail 复发)

### 6.4 跟 Sprint 158 治标对比
- Sprint 158 治标: 删 png 改文字 logo (user 不满意, 报"我之前改的又调整回去了")
- Sprint 159 治本: 保留 png 视觉, base64 inline (0 推送 fail 风险, 0 外部凭证)
- **你不要再改回 Sprint 158 文字 logo 方案** (user 担忧, 写在 handoff 强制)

---

## 7. L4.x 永久规则 (你必须遵守)

| 规则 | 说明 |
|---|---|
| **L3 精准修改** | 只动 NavBar.vue / SamplingView.vue / index.html 3 files, 不动 router / 后端 / 任何 png 文件 |
| **L4.7 100% 精准** | 1 commit 3 files 改, 不拆分逻辑, 不 commit png 二进制 |
| **L4.1 SQL f-string** | 0 SQL 改动 (前端 only) |
| **L4.4 pytest** | 跑全量 pytest 验证 741 passed / 66 skipped (跟 Sprint 158 baseline 一致) |
| **L4.13 MEMORY size** | Sprint 159 close memory 后查 < 24.4KB |
| **L4.8 cleanup** | merge --no-ff 后删本地 + 远程 feature 分支 |
| **L4.18 png LFS fail** | 治根 base64 inline 治本, 不 commit png 二进制 (避免 Sprint 158 push fail 复发) |

---

## 8. 实施步骤 (Stage 2 Codex 跑)

1. **读 handoff 完整文档** (本文件 8 段, ~280 行)
2. **跑 base64 命令** 生成 logo2.png + 芙清logo.png base64 字符串 (见第 5 段)
3. **改 NavBar.vue** (Sprint 159 02.4.1 步骤 1):
   - 删 `<div class="navbar-logo-placeholder">天</div>` + 删 `.navbar-logo-placeholder` CSS
   - 加 `const logoPngBase64 = '...'` + `const logoDataUri = ...`
   - 加 `<img class="navbar-logo" :src="logoDataUri" alt="天猫CRM" />`
   - 复用 Sprint 158 删掉的 `.navbar-logo` CSS
4. **改 index.html** (Sprint 159 02.4.1 步骤 2):
   - 删 `<link rel="icon" type="image/svg+xml" href="/favicon.svg?v=20260629" />`
   - 加 `<link rel="icon" type="image/png" href="data:image/png;base64,..." />`
5. **改 SamplingView.vue** (Sprint 159 02.4.1 步骤 3):
   - 删整个 02 板块卡片 (含柱状图/滚动去年/sr-only table/export 按钮)
   - 加 5 卡片 (派样人数/回购人数/正装回购人数/正装 GSV/AUS) 跟 01 总览同 layout
   - 删 repurchaseDistribution useQuery (Sprint 158 加的 4 桶柱状图数据)
   - 删 repurchaseCompareDistribution useQuery (Sprint 158 加的滚动去年)
   - 删 repurchaseBuckets computed
   - 删 repurchaseCompareRange ref
   - 删 `fetchSamplingRepurchaseDistribution` import
   - **保留 4 桶相关 computed 暂时不动** (后续 sprint 159.5 删, Sprint 159 只删 02 板块 UI)
6. `cd frontend-vue3 && npm run build` 验证 PASS
7. **不要 commit png 文件** (避免 LFS filter 触发)
8. 实施完报告 user 验收

---

## 9. 跟项目规范对齐

- **TS strict**: 用 TypeScript, 不在 `any` 旁路 (L4.7 100% 精准)
- **Vue 3 Composition API**: `<script setup lang="ts">` (跟 App.vue / 其他 view 一致)
- **base64 inline**: data URI `data:image/png;base64,...` 格式 (跟 LFS 治本, 永远不推送 fail)
- **Naive UI**: 跟其他组件一致 (但 02 板块重排 不需要新组件)
- **路径别名**: `@/components/NavBar.vue` (跟项目 tsconfig 一致)

---

## 10. 收口期望 (Stage 3 Claude 跑)

合并 main HEAD: `git log --oneline -1` 应该看到 1 个新 commit 描述 Sprint 159 范围.
pytest baseline: 741/66/0 不退化 (跟 Sprint 158 一致).
L4.22 vite preview rebuild + restart PID HTTP 200.
CHANGELOG.md +11~15 lines (Sprint 159 entry).
.ship-audit.log append (audit trail).
L4.8 cleanup feature 分支 (本地 + 远程).
累计 sprint 0 debt 82 (Sprint 159 完成).

---

**Stage 2 启动: 读完整文档, 实施 3 files 改, 不动 git. 实施完, 报告 user 验收.**

**关键: 不要再改回 Sprint 158 文字 logo 方案! user 担忧明确写在 handoff. 严格走 base64 inline png 治本.**
