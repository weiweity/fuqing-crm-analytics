# YOY-GUARD-CONFIG — YOYGuard threshold 环境变量配置

> Sprint 19 P2-2 任务: 把 `YOYGuard.vue` 组件的异常值阈值从硬编码 `1e6` 改成可 env 覆盖.
> 落地日期: 2026-06-11. 拍板人: subagent C3.

---

## 1. 拍板

| 维度 | 拍板 |
|---|---|
| **环境变量名** | `VITE_YOY_GUARD_THRESHOLD` (Vite 前缀) |
| **默认值** | `1e6` (跟 Sprint 16.5 #92 + Sprint 18 #124 硬编码一致) |
| **类型** | number (`.env` 写浮点数字面量, 组件内 `Number(...)` 强转) |
| **优先级** | prop `threshold` 显式传入 > env > 默认 1e6 |
| **生效范围** | 整个 SPA build (Vite build-time 静态替换 `import.meta.env.VITE_*`) |
| **运行时改阈值** | 改完需 `npm run build` 重 build, dev server 改 `.env` 自动热更 |

---

## 2. 为什么加 env 配置?

### 2.1 当前痛点

`YOYGuard.vue` 阈值硬编码 `1e6` (Sprint 18 #124). 业务场景千变万化:

- 流量大盘 YOY 1e6 (万倍涨) 算合理 (e.g. 抖音新渠道上线).
- 私域复购 YOY 1e6 几乎一定是数据 bug (复购率不可能万倍涨).
- 内部 demo 演示需要把阈值调到 1e3 看守卫效果.

硬编码 = 改一次得 PR 一次. 改 env = 部署时按 env 调整.

### 2.2 跟 YOYBadge 契约一致

`YOYBadge` / `MetricCard` 早期也曾硬编码, Sprint 11+ 改成 caller 传值. 此次给 `YOYGuard` 暴露 env 阈值, 是同一思路: 框架给合理默认, 业务方按场景覆盖.

---

## 3. 用法

### 3.1 默认 (不配 env)

```bash
# .env / .env.production 不写 VITE_YOY_GUARD_THRESHOLD
# 组件 props.threshold 默认值 = 1e6 (跟 Sprint 16.5 / 18 行为一致)
```

### 3.2 调高 (流式大盘场景)

```bash
# frontend-vue3/.env.production
VITE_YOY_GUARD_THRESHOLD=1e9
```

效果: |v| > 1e9 才显示 "数据异常". 1e6 ~ 1e9 之间不再触发守卫.

### 3.3 调低 (私域复购场景, 严格守卫)

```bash
# frontend-vue3/.env.staging
VITE_YOY_GUARD_THRESHOLD=1e3
```

效果: |v| > 1000 就显示 "数据异常". 复购率超过 10 倍基本是数据 bug.

### 3.4 显式 prop 覆盖 (单组件粒度)

```vue
<!-- RFMSegmentDrilldown 表格某列, 阈值 1e3, 跟全局不一样 -->
<YOYGuard :value="v" unit="pp" :threshold="1e3" />
```

prop 优先级最高, 跟 env 无关.

---

## 4. 代码改动

### 文件: `frontend-vue3/src/components/YOYGuard.vue`

**改动 1 (line 14)**: JSDoc 加 env 提示.

```diff
- * - threshold: 异常值阈值, 默认 1e6
+ * - threshold: 异常值阈值, 默认 1e6, 可由 `VITE_YOY_GUARD_THRESHOLD` env 覆盖 (Sprint 19 P2-2)
```

**改动 2 (line 38-43)**: withDefaults 块.

```diff
   {
     unit: '%',
-    threshold: 1e6,
+    threshold: Number(import.meta.env.VITE_YOY_GUARD_THRESHOLD ?? 1e6),
     empty: '—',
     precision: 2,
   },
```

### 设计要点

1. **`Number(...)` 强转**: `.env` 写的是字符串 `'1e6'`, `Number('1e6')` → 1000000. 如果 env 是 `1e6` (数字), `Number(1e6)` 也是 1000000. 一致行为.
2. **`??` 兜底**: env 未设置时返 `undefined`, `?? 1e6` 兜底, 跟历史硬编码值一致.
3. **`import.meta.env.VITE_*` 静态替换**: Vite build-time 把 `import.meta.env.VITE_YOY_GUARD_THRESHOLD` 替换成 `'1e6'` 字面量, 不进 runtime 评估. 性能 / 安全都 OK.
4. **prop 优先级最高**: `withDefaults` 只在 prop 未传时生效, 显式 `<YOYGuard :threshold="x" />` 仍走 prop. 跟 `precision` / `empty` 行为一致.

---

## 5. .env 模板

仓库根 `.env.example` (若有) 跟 `frontend-vue3/.env.example` 加:

```bash
# YOYGuard 异常值阈值 (Sprint 19 P2-2)
# 默认 1e6, 业务方按场景覆盖 (流量大盘 1e9, 私域复购 1e3)
VITE_YOY_GUARD_THRESHOLD=1e6
```

> 注: 本次提交不强制更新 `.env.example` (P2-2 scope 只动 YOYGuard.vue 组件), 未来加 env 文档时一起补.

---

## 6. 测试

### 6.1 单元测试 (vitest)

`frontend-vue3/src/components/__tests__/YOYGuard.test.ts` (Sprint 18 #124 已写 3 个 test) 需加 1 个:

```typescript
it('uses VITE_YOY_GUARD_THRESHOLD env when threshold prop not provided', () => {
  // import.meta.env 模拟 (Vite test mode 需 vi.stubEnv)
  vi.stubEnv('VITE_YOY_GUARD_THRESHOLD', '100')
  const wrapper = mount(YOYGuard, { props: { value: 200 } })
  expect(wrapper.text()).toBe('数据异常')  // 200 > 100, 走守卫
  vi.unstubAllEnvs()
})
```

### 6.2 E2E 验证

`npm run build` 后 `VITE_YOY_GUARD_THRESHOLD=1e3 npm run preview` + 浏览器看 RFMSegmentDrilldown R 桶:
- value 1.5 pp (正常) → 显示 `1.50pp`
- value 5000 pp (异常, 业务场景 1e3 阈值) → 显示 `数据异常`

### 6.3 本次提交未加测试 (P2-2 scope 限制)

本次 P2-2 拍板只动 1 个文件 (YOYGuard.vue) + 1 个文档. 测试留 Sprint 19.5 mini-sprint (跟 6 P2 一样节奏) — 避免 1 个 env config 改动就 1 commit + 1 test commit, commit 颗粒度过细.

---

## 7. 后续 (Sprint 20+ 待办)

| # | 任务 | 备注 |
|---|---|---|
| 1 | 写 vitest 测试覆盖 env 路径 | 留 Sprint 19.5 |
| 2 | `.env.example` 模板加 `VITE_YOY_GUARD_THRESHOLD` | 跟 1 一起 |
| 3 | frontend-vue3/.env.production 决定默认值 | 走 ops 评审 |
| 4 | 监控 YOYBadge "数据异常" 出现频次 | 走埋点 |

---

**相关文档**:
- `frontend-vue3/src/components/YOYGuard.vue` (本 P2-2 改的文件)
- `frontend-vue3/src/components/YOYBadge.vue` (Sprint 16.5 #92 异常值守卫原版)
- `docs/SPRINT-18-PRE-COMMIT.md` (Sprint 18 #124 抽 YOYGuard 组件)
- `CLAUDE.md` "Ratio Convention" 章节 (前端契约 pass-through)
- Sprint 16.5 #92 异常值守卫决策 (1e6 阈值来源)

**Sprint 19 P2-2 完成**: YOYGuard threshold env 配置拍板, 代码改 1 行 + 文档 1 份.
