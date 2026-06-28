# HANDOFF TO CODEX — Sprint 158 派样正装转化 UI 重大重构 (3 层级导航)

> **目标**: 取消侧边栏 + 整合到导航栏 + 3 层级导航 (天猫CRM+数据分析平台 / 6 板块 tabs / 第 3 层级内容) + 板块布局参考阿里巴巴生意参谋 (深蓝 gradient header)
>
> **Stage 1 (Claude)**: 写架构 + handoff ✅
> **Stage 2 (Codex 实施)**: 你读这文档后直接实施, 不动 git (不 commit / push / merge)
> **Stage 3 (Claude)**: review + 12 步流程收口
>
> 跟 Sprint 144 模式 stable 1 turn 跑完, 你的发挥空间在架构选型 + 组件拆分 + 深蓝 gradient 美学.

---

## 1. 用户原始需求 (4 大块)

### 1.1 取消侧边栏

当前 `<DefaultLayout />` 用了 `<Sidebar />` 组件, 在最左侧. 需求: 删 Sidebar, 把它的内容整合到导航栏.

### 1.2 侧边栏选项合并到导航栏

当前 `Sidebar.vue` 有 6 板块 (人群看板/老客分析/品类看板/市场对焦/派样正装转化/地域分析). 需求: 这 6 板块改成 3 层级导航的"第 2 层级 tabs".

### 1.3 导航栏 3 层级设计

- **第 1 层级**: header — **天猫CRM项目** (logo) + 小字 **数据分析平台** (subtitle) + 右侧 user menu (主店/我的/帮助/退出, 参考生意参谋)
- **第 2 层级**: tabs — 6 板块横排 (人群看板｜老客分析｜品类看板｜**市场对焦**｜派样正装转化｜地域分析). active tab 高亮 (底部下划线), **鼠标悬停**对应板块时弹出**悬停弹窗**, 弹窗显示该板块的所有 tab 名称.
- **第 3 层级**: 当前导航栏的**内容** (当前时间/对比日期/对比模式/渠道 等 AppFilterBar 现有字段) — 这是用户对导航栏 3 层级的描述, 实际就是 AppFilterBar 集成到 NavBar 下方.

### 1.4 板块放的地方参考阿里巴巴生意参谋

生意参谋 header 设计 (Image #2):
- **深蓝渐变** (类似 `linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)`, #1e3a8a 深蓝 → #2563eb 蓝)
- 左侧: 圆形 logo + 项目名 (白色, 生意参谋 / 我们是 "天猫CRM")
- 中间偏左: "主店" selector (灰色文字 + 下拉箭头)
- 中间: 搜索框 (生意参谋有 AI 问数 / 我们可以暂不做搜索, 留扩展位)
- 右侧: user menu (惠商/我的/帮助/退出, icon + 文字)
- 底部: 二级 tabs (生意参谋的 12 个 tabs / 我们 6 板块 tabs)

我们要实现的就是这个深蓝 gradient header + 6 板块 tabs (第 2 层级) + hover 弹窗 (第 2 层级扩展).

### 1.5 6 板块的 tab 列表 (hover 弹窗内容)

| 板块 | tabs (hover 弹窗显示) |
|---|---|
| **人群看板** (`/audience`) | 数据总览 / 渠道概览 / 30指标对比 |
| **老客分析** (`/customer-health`) | 健康总览 / 健康分布 / 健康趋势 |
| **品类看板** (`/category`) | 现状概览 / 连带分析 / 品类复购周期 / 品类回购分析 / 品类流转 / 羊毛党分析 / 风险预警 |
| **市场对焦** (`/market-focus`) | 商品-人群分析 / 店铺资产 / 商品资产 / 其他商品资产 |
| **派样正装转化** (`/sampling`) | 派样正装转化分析 / 0.01派样分析 / Cohort 留存矩阵 / 滚动同期对比 |
| **地域分析** (`/geo`) | 省份分布 / 地域-象限矩阵 / 地域趋势 |

---

## 2. 现状摸底 (L3 精准修改起点)

### 2.1 文件清单 (改动范围 5+ files, 删 1 file)

| 文件 | 当前状态 | Sprint 158 改动 |
|---|---|---|
| `frontend-vue3/src/components/Sidebar.vue` | 6 板块列表, 240px 宽, fixed 左侧 | **删** |
| `frontend-vue3/src/layouts/DefaultLayout.vue` | `<Sidebar />` + `<AppFilterBar />` + main + 1600px 容器 | 删 Sidebar, **加** `<NavBar />` 第 1+2 层级 + `<AppFilterBar />` 第 3 层级 |
| `frontend-vue3/src/router/index.ts` | 7 路由 (含 `/market-focus`) | **保留 6 板块路由 + `/category-detail/:id`** (市场对焦保留, 6 板块全要) |
| `frontend-vue3/src/components/NavBar.vue` | (不存在) | **新建** — 3 层级 NavBar (header + tabs + hover 弹窗) |
| `frontend-vue3/src/config/navigations.ts` | (不存在) | **新建** — 单一 source of truth (6 板块 + tabs data) |
| `frontend-vue3/src/components/AppFilterBar.vue` | 现状不动 | 集成到 NavBar 下方 (DefaultLayout 调整位置) |

> 重要决策: **市场对焦保留**, 6 板块全部在 NavBar tabs 列表. 之前 Claude 1 turn 方案拍板"删市场对焦", User 后续反馈"6 板块包含市场对焦", **以 user 最新拍板为准: 保留 6 板块**.

### 2.2 DefaultLayout.vue 当前结构

```vue
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
```

Sprint 158 期望结构 (建议, 你可以微调):

```vue
<template>
  <div class="flex flex-col h-screen overflow-hidden bg-slate-100">
    <NavBar />              <!-- 第 1+2 层级 (header + 6 板块 tabs + hover 弹窗) -->
    <AppFilterBar />         <!-- 第 3 层级 (日期/对比/渠道) -->
    <main class="flex-1 overflow-y-auto p-5">
      <div class="max-w-[1600px] mx-auto">
        <slot />
      </div>
    </main>
  </div>
</template>
```

### 2.3 各 view 的 tabs 实际名称 (你 handoff 后实际查 view, 不需要按之前列表)

User 给的 tab 列表来自各 view 的 `<n-tab-pane tab="...">` 标签, 你实施时可以直接 grep 各 view 查 tab 列表. 如果有出入, 以 view 实际 tab 为准 (单一 source of truth).

---

## 3. 实施范围 (你的发挥空间)

### 3.1 必须做 (架构定下)

1. **删 `Sidebar.vue`** 文件
2. **新建 `NavBar.vue`** (3 层级, ~200-300 行 Vue 3 + TypeScript)
3. **新建 `config/navigations.ts`** (单一 source of truth, ~50 行 TypeScript)
4. **改 `DefaultLayout.vue`** (删 Sidebar 引用, 加 NavBar, ~10 行 diff)
5. **不改 `AppFilterBar.vue`** (Sprint 158 不动, 后续 sprint 集成到 NavBar 内部可单开)
6. **不改 router** (6 板块全保留, 跟 user 报对齐)
7. **不改 view 内部** (L3 精准修改, Sprint 158 只动 layout + nav)
8. **不改后端** (前端 UI 重构, 0 后端改动)
9. **不改后端类型契约** (跟 Sprint 144+155 模式 stable, frontend-only 改动)

### 3.2 推荐设计 (你的发挥空间)

#### 3.2.1 NavBar 第 1 层级 (深蓝 gradient header)

```vue
<header class="navbar-header" style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)">
  <div class="navbar-header-inner max-w-[1600px] mx-auto px-6 flex items-center justify-between">
    <!-- 左侧: logo + 项目名 -->
    <div class="flex items-center gap-3">
      <div class="navbar-logo-icon w-8 h-8 rounded-full bg-white/20 border border-white/40 flex items-center justify-center text-white text-sm font-semibold">天</div>
      <div>
        <h1 class="text-base font-semibold text-white leading-tight">天猫CRM</h1>
        <p class="text-[11px] text-white/70 leading-tight">数据分析平台</p>
      </div>
    </div>
    <!-- 右侧: user menu (留扩展位, 跟生意参谋 惠商/我的/帮助/退出) -->
    <nav class="flex items-center gap-5">
      <a class="text-white/85 text-sm hover:text-white" href="#">主店</a>
      <a class="text-white/85 text-sm hover:text-white" href="#">我的</a>
      <a class="text-white/85 text-sm hover:text-white" href="#">帮助</a>
    </nav>
  </div>
</header>
```

颜色建议:
- 深蓝 gradient: `linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)` (跟生意参谋蓝色调一致)
- logo 圆形背景: `bg-white/20` 半透明白 + `border-white/40` 边
- 项目名: `text-white` (主色) + `text-white/70` (副标题)

#### 3.2.2 NavBar 第 2 层级 (6 板块 tabs + hover 弹窗)

```vue
<nav class="navbar-tabs-bar bg-white border-b border-slate-200">
  <div class="navbar-tabs-inner max-w-[1600px] mx-auto px-6 flex items-center gap-1">
    <div
      v-for="item in NAV_ITEMS"
      :key="item.key"
      class="navbar-tab-wrapper relative"
      @mouseenter="onTabEnter(item.key)"
      @mouseleave="onTabLeave"
    >
      <router-link
        :to="item.key"
        class="navbar-tab inline-flex items-center gap-1 px-4 py-3.5 text-sm font-medium text-slate-600 hover:text-slate-900 border-b-2 border-transparent"
        :class="{ 'navbar-tab--active text-blue-600 border-blue-600 font-semibold': activeKey === item.key }"
      >
        <span>{{ item.label }}</span>
        <span v-if="item.tabs.length" class="text-[10px] text-slate-400">▾</span>
      </router-link>

      <!-- hover 弹窗: 该板块的 tab 列表 -->
      <div
        v-if="hoverKey === item.key && item.tabs.length"
        class="navbar-popover absolute top-full left-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 min-w-[200px] p-2"
        @mouseenter="onPopEnter"
        @mouseleave="onPopLeave"
      >
        <div
          v-for="tab in item.tabs"
          :key="tab.key"
          class="navbar-popover-item block px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-blue-600 rounded cursor-pointer"
          @click="navigate(item, tab.key)"
        >
          <span>{{ tab.label }}</span>
        </div>
      </div>
    </div>
  </div>
</nav>
```

交互细节:
- hover 进 tab: 显示 popover, **150ms 防抖** 避免误触 (timer)
- hover 出 tab: 150ms 延迟隐藏 (给用户移到 popover 的时间)
- hover 进 popover: 取消隐藏 timer
- click popover item: 跳到 `item.key` + 锚点 `tab.key` (Vue Router hash 模式)
- active tab: 蓝色文字 + 蓝色底部 border

#### 3.2.3 config/navigations.ts (单一 source of truth)

```ts
export interface NavTab {
  key: string  // 路由 hash 锚点 (e.g. '#audience-overview')
  label: string
}

export interface NavItem {
  key: string  // 路由 path
  label: string
  tabs: NavTab[]
}

export const NAV_ITEMS: NavItem[] = [
  { key: '/audience', label: '人群看板', tabs: [
    { key: '#audience-overview', label: '数据总览' },
    { key: '#audience-channel', label: '渠道概览' },
    { key: '#audience-metrics', label: '30指标对比' },
  ]},
  { key: '/customer-health', label: '老客分析', tabs: [
    { key: '#customer-health-overview', label: '健康总览' },
    { key: '#customer-health-distribution', label: '健康分布' },
    { key: '#customer-health-trend', label: '健康趋势' },
  ]},
  { key: '/category', label: '品类看板', tabs: [
    { key: '#category-overview', label: '现状概览' },
    { key: '#category-association', label: '连带分析' },
    { key: '#category-repurchase', label: '品类复购周期' },
    { key: '#category-repurchase-rate', label: '品类回购分析' },
    { key: '#category-flow', label: '品类流转' },
    { key: '#category-wool', label: '羊毛党分析' },
    { key: '#category-risk', label: '风险预警' },
  ]},
  { key: '/market-focus', label: '市场对焦', tabs: [
    { key: '#market-focus-product-customer', label: '商品-人群分析' },
    { key: '#market-focus-store-assets', label: '店铺资产' },
    { key: '#market-focus-product-assets', label: '商品资产' },
    { key: '#market-focus-other-product-assets', label: '其他商品资产' },
  ]},
  { key: '/sampling', label: '派样正装转化', tabs: [
    { key: '#sampling-roi', label: '派样正装转化分析' },
    { key: '#sampling-lock', label: '0.01派样分析' },
    { key: '#sampling-cohort', label: 'Cohort 留存矩阵' },
    { key: '#sampling-rolling', label: '滚动同期对比' },
  ]},
  { key: '/geo', label: '地域分析', tabs: [
    { key: '#geo-distribution', label: '省份分布' },
    { key: '#geo-matrix', label: '地域-象限矩阵' },
    { key: '#geo-trend', label: '地域趋势' },
  ]},
]
```

> 注: tab key 用 `#` 前缀的 hash 锚点, 实际跳转通过 Vue Router 的 `hash` 模式. 如果你判断应该用 query string 替代, 你的发挥空间决定.

---

## 4. 验收标准 (跟 Sprint 144+155 stable)

### 4.1 build / lint / pytest
- `cd frontend-vue3 && npm run build` PASS (vue-tsc + vite, ~750ms)
- pre-commit hook 全过: vite build + L1 SQL f-string consistency lint 0 violations + ruff F841 PASS
- `python -m backend.contracts._lint` OK (后端 0 改动, 应该 PASS)

### 4.2 视觉验收 (user 试看)
- ✅ 侧边栏消失, 整页左侧只有 NavBar
- ✅ NavBar 第 1 层级 header 深蓝 gradient (类似生意参谋 #1e3a8a → #2563eb)
- ✅ NavBar 第 1 层级 logo + "天猫CRM" + "数据分析平台" + 右侧 user menu
- ✅ NavBar 第 2 层级 6 板块 tabs (人群看板｜老客分析｜品类看板｜市场对焦｜派样正装转化｜地域分析)
- ✅ active tab 高亮 (蓝色文字 + 蓝色底部 border)
- ✅ hover 任意 tab 弹出 popover, 显示该板块的 tab 列表 (e.g. hover 派样正装转化 → 弹窗显示 派样正装转化分析 / 0.01派样分析 / Cohort 留存矩阵 / 滚动同期对比)
- ✅ click popover item 跳到对应路由
- ✅ 第 3 层级 AppFilterBar 在 NavBar 下方 (保持原样, 集成位置改到 NavBar 之后)
- ✅ 1600px 容器保留 (Sprint 156 改的, 不要破坏)

### 4.3 pytest baseline
- pytest 803 passed / 23 skipped / 0 failed 不退化
- 抽样跑 `backend/tests/test_sampling_roi_yoy.py` 等 (L4.4 跳过真连 DuckDB test)

### 4.4 git log 干净
- 1 个 commit (Sprint 158), 改了 5+ files, 删 1 file
- commit message: `feat(navbar): Sprint 158 派样正装转化 3 层级导航重构 (删 Sidebar + 6 板块 tabs + 深蓝 gradient + hover 弹窗)`
- L4.7 100% 精准: 不动 router 路由 / 不动 view 内部 / 不动 AppFilterBar

---

## 5. L4.x 永久规则 (你必须遵守)

| 规则 | 说明 |
|---|---|
| **L3 精准修改** | 只动 layout + nav (DefaultLayout / NavBar / config), 不动 view / router / 后端 / 类型契约 |
| **L4.7 100% 精准** | 1 个 sprint 1 个 commit, 不拆分逻辑 |
| **L4.1 SQL f-string** | 不动 SQL 字符串 (这次 Sprint 158 0 SQL 改动) |
| **L4.5 FilterBuilder** | 不动 SQL 拼接 (这次 Sprint 158 0 SQL 改动) |
| **L4.19 channel alias** | 不动 channel 字段 (这次 Sprint 158 0 channel 改动) |
| **L4.4 真连 test skip** | pytest sampling 真连 test 跳过 (CI / fresh checkout 缺 DuckDB) |
| **L4.13 MEMORY size** | MEMORY.md < 24.4KB (你写 close memory 后查) |
| **L4.8 cleanup** | merge --no-ff 后删本地 + 远程 feature 分支 |

---

## 6. 跟 Sprint 144 stable 模式 (你读这个)

- Stage 1 (Claude): 写架构 + handoff ✅ 你现在读
- Stage 2 (Codex): 实施 5+ files, **不动 git** (不 commit / push / merge)
- Stage 3 (Claude): review + 12 步流程收口 (pytest + build + /review + commit + push + /qa + merge --no-ff + push main + pull + restart + L4.22 + CHANGELOG + audit trail + L4.8)

**你的发挥空间** (Sprint 144 模式允许):
- Vue 3 + TypeScript 组件设计 (Composition API + script setup, 跟项目其他组件一致)
- 深蓝 gradient 美学实现 (CSS variables / Tailwind / styled-components / scoped css 自由选择)
- hover 弹窗动画 (fade / slide / 150ms 防抖 / 200ms 过渡)
- 响应式布局 (mobile / tablet 适配 - 你可加可省, 跟项目当前状态)
- accessibility (键盘导航 / ARIA 属性 - 你可加可省, 跟项目当前状态)

**你的限制** (L3 精准 + L4.7):
- 不改 router (6 板块全保留)
- 不改 view (用户没要求)
- 不改后端 (前端 only)
- 不改类型契约 (frontend types.ts / types.generated.ts)

---

## 7. 实施步骤建议 (你拍板)

1. **新建 `config/navigations.ts`** (单一 source of truth, ~60 行)
2. **新建 `components/NavBar.vue`** (3 层级, ~250 行: 深蓝 header + 6 tabs + hover popover + 防抖 timer)
3. **删 `components/Sidebar.vue`** (1 个 file delete)
4. **改 `layouts/DefaultLayout.vue`** (删 Sidebar import + 改 1 行 template)
5. `cd frontend-vue3 && npm run build` 验证

完成后, 你只需要做 `git diff` 看改动, **不 commit / 不 push**. Stage 3 留给 Claude.

---

## 8. 测试 user 验收

完成后 user 试看:
1. 访问 http://localhost:5173/audience
2. 看 NavBar 顶部深蓝 gradient header
3. 看 6 板块 tabs (人群看板 active 高亮)
4. hover 派样正装转化 → 弹窗显示 4 个 tab
5. click 弹窗里 0.01派样分析 → 跳到 /sampling
6. 看 AppFilterBar 在 NavBar 下方 (跟之前一样)
7. 看 main content 1600px 容器 (跟之前一样)

如果 user 反馈需要 amend, Sprint 159 跑 (跟 Sprint 144+145+155+157 stable).

---

## 9. 跟项目规范对齐

- **TS strict**: 用 TypeScript, 不在 `any` 旁路 (L4.7 100% 精准)
- **Vue 3 Composition API**: `<script setup lang="ts">` (跟 App.vue / 其他 view 一致)
- **Naive UI**: 跟其他组件一致 (但 hover popover 自己实现, 不用 n-popover 因为 fixed 定位 + 150ms 防抖复杂)
- **Tailwind**: 跟其他组件一致 (utility-first, 不写 scoped css 太多)
- **路径别名**: `@/components/NavBar.vue` / `@/config/navigations` (跟项目 tsconfig 一致)

---

## 10. 收口期望 (Stage 3 Claude 跑)

合并 main HEAD: `git log --oneline -1` 应该看到 1 个新 commit 描述 Sprint 158 范围.
pytest baseline: 803/23/0 不退化.
L4.22 vite preview rebuild + restart PID HTTP 200.
CHANGELOG.md +11~15 lines (Sprint 158 entry).
.ship-audit.log append (audit trail).
L4.8 cleanup feature 分支 (本地 + 远程).
累计 sprint 0 debt 81 (Sprint 158 完成, 累计 81 sprint 0 debt 持续).

---

**Stage 2 启动: 读完整文档, 实施 5+ files, 不动 git. 实施完, 报告 user 验收.**
