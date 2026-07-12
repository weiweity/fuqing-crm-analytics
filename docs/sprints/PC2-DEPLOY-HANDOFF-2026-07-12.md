# PC2 生产环境部署 Handoff (2026-07-12)

> **部署日期**: 2026-07-13（明天）
> **部署人**: 运营 / 接手人
> **main HEAD**: `ef3f9d5`
> **VERSION**: 0.4.14.50

## 1. 部署步骤

在 PC2 上打开 PowerShell：

```powershell
# Step 1: 拉取最新代码
cd D:\fuqin-date\fuqing-crm-analytics
git pull origin main

# Step 2: 验证代码版本
git log --oneline -1
# 应该输出: ef3f9d5 merge docs: CLAUDE.md L4.x 永久规则迁移

# Step 3: 重启后端
nssm restart fuqing-uvicorn
# 等 5 秒让后端启动

# Step 4: 重建前端
cd D:\fuqin-date\fuqing-crm-analytics\frontend-vue3
npm install --legacy-peer-deps
npm run build

# Step 5: 重启前端
nssm restart fuqing-frontend
```

## 2. 验证清单

部署后在 PC2 浏览器打开 `http://localhost:5173`，依次检查：

| # | 验证项 | 怎么看 |
|---|--------|--------|
| 1 | 导航栏 tab 完整显示 | 顶部 5 个 tab 文字都不被截断（特别是"派样正装转化"）|
| 2 | 派样看板 03 各板块 | 应为 总-分 布局：上方 TTL派样 总览卡，下方 U先派样 + 百补派样 两张分卡 |
| 3 | 派样人数同比 | 01总览 + 03 各板块的"派样人数"都有同比百分比（不再显示"暂无同比"）|
| 4 | 后端 API 正常 | 能正常登录、切换页面、加载数据 |

## 3. 本次更新内容

### 3.1 新增功能
- **派样人数同比数据**: 01总览 + 03 各板块的"派样人数"现在显示真实的同比百分比
- **派样看板 03 总-分 布局**: TTL派样（总览卡，U先+百补汇总）→ U先派样 + 百补派样（两张分卡）

### 3.2 修复
- 导航栏 tab 文字显示不全（尤其是"派样正装转化"）
- 派样人数 sample_users + nonfull_repurchase_users 同比/环比缺失
- Pydantic schema 缺少 YOY 字段导致 API 静默过滤

### 3.3 文档
- CLAUDE.md L4.x 规则迁移到 `docs/rules/L4-permanent-rules.md`
- 历史文档整合归档

## 4. 回滚步骤（如果出问题）

```powershell
cd D:\fuqin-date\fuqing-crm-analytics
git checkout 9917940    # 回退到部署前的版本
nssm restart fuqing-uvicorn
cd frontend-vue3
npm run build
nssm restart fuqing-frontend
```

## 5. 技术摘要（接手人参考）

```
根因: backend contracts/sampling.py 的 SamplingChannelSummary Pydantic schema
漏了 4 个字段 → FastAPI response_model 序列化时静默丢弃。
修复: 补齐 sample_users_yoy_pct / sample_users_mom_pct /
nonfull_repurchase_users_yoy_pct / nonfull_repurchase_users_mom_pct。

涉及文件:
- backend/services/sampling_service.py (+9 行)
- backend/contracts/sampling.py (+5 行)
- frontend-vue3/src/api/sampling.ts (+5 行)
- frontend-vue3/src/views/SamplingView.vue (+162/-158 行)
- frontend-vue3/src/components/NavBar.vue (+12/-5 行)
```
