# 芙清 CRM 项目 - 工作台交接文档

**交接时间**: 2026-04-06
**项目**: 芙清 CRM 客户分析系统
**路径**: `/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics`

---

## 📋 项目概览

| 周 | 主题 | 状态 |
|----|------|------|
| Week 1 | 核心指标看板 | ✅ 完成 |
| Week 2 | RFM 模型 | ✅ 完成 |
| Week 3 | 人群流转 | ✅ 完成 |
| Week 4 | 人群画像（地域/品类/PPT导出） | ✅ 完成 |
| Week 5 | 缺口追踪 | ⏳ 待启动 |

### 启动命令
```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
# 后端（端口8000）
~/.workbuddy/binaries/python/envs/default/bin/python backend/main.py
# 前端（端口5173）
cd frontend-vue3 && npm run dev
```

---

## 🛠️ 技术栈

- **数据处理**: Python + Pandas + DuckDB
- **后端**: FastAPI + Pydantic
- **前端**: Vue3 + Vite + ECharts 5 + Tailwind CSS + Pinia（已完全迁移，原 Streamlit 已废弃）
- **导出**: python-pptx
- **DUCKDB_PATH**: 统一从 `backend.config` 导入，禁止硬编码

### 数据库结构
- **orders 表**: 32列，核心字段 order_id/user_id/order_time/actual_amount/province/channel
- **SPU 字段**: spu_category, spu_type, spu_tier, spu_product_class, spu_product_subclass, spu_cosmetic, spu_spec
- **user_rfm 表**: 17字段，主键 (user_id, analysis_date, metric_type, lookback_days)
- **数据规模**: 13,933,881 订单 / 848,631 用户

### 关键业务参数
- 新老客基准日期: `2025-01-01`
- RFM 固定阈值: R=[14/30/60/90] F=[1/2/3/5] M=[100/300/500/1000]
- 流失定义: 动态阈值（典型周期×150%）+ 单品类

### 8象限定义
| ID | 名称 | ID | 名称 |
|----|------|----|------|
| 1 | 钻石会员 | 6 | 清新路人 |
| 2 | 潜力新贵 | 7 | 沉睡土豪 |
| 3 | 忠实金主 | 8 | 流失用户 |
| 4 | 频次买家 | 9 | 其他 |
| 5 | 豪气新客 | | |

---

## 📝 经验规则（Week 1-4 沉淀）

1. **契约先行**：前后端分离项目，必须先定义并锁定接口契约
2. **禁止 SELECT ***：SQL 查询必须显式列出目标列
3. **类型锁定**：DuckDB INSERT + CTE 场景必须显式列类型
4. **Owner 唯一**：多 Agent 并行时，每个文件一个 Owner
5. **参数化查询**：存在用户输入的地方必须参数化
6. **库版本差异**：python-pptx RGBColor 在 `pptx.dml.color`，非 `pptx.util`
7. **前端类型安全**：Vue3 前端必须通过 openapi-typescript 从 `/openapi.json` 自动生成 API 类型，禁止手写 TypeScript 类型定义

### API 契约执行规范（Week 4 教训）

**问题**：后端实际返回格式与前端期望不一致，导致数据流阻塞。

**预防规则**：
1. 后端 API 必须输出 Returns 注释，说明实际返回格式
2. 前端数据层必须验证实际返回，不能假设格式
3. 并行开发时后端先交付示例 JSON 给前端
4. API 变更必须通知前端，更新 api-contract.md

### Vue3 前端开发规范
```typescript
// API 调用必须使用自动生成的类型（禁止手写）
import { useApi } from '@/api/base'
const { data } = useApi('/api/v1/metrics/overview')
```

---

## 🐛 Bug 修复记录（Week 1-4）

| Bug | 文件 | 状态 |
|-----|------|------|
| SQL 注入 | metrics_service.py | ✅ |
| DuckDB CTE 类型推断 | flow_service.py | ✅ |
| Plotly update_layout | rfm_charts.py | ✅ |
| python-pptx RGBColor | export_service.py | ✅ |
| Plotly choropleth 不支持 China | geo_charts.py | ✅ 改用 Scattergeo |
| geo 省份匹配失败 | geo_charts.py | ✅ 添加全称到简称映射 |
| geo_data name vs province 字段 | geo_data.py | ✅ |
| export_data segments 结构 | export_data.py | ✅ |
| geo_data 交叉矩阵转换 | geo_data.py | ✅ |
| category_data 交叉矩阵转换 | category_data.py | ✅ |

---

## 📂 技术文档索引

详细技术规范参考：
- `docs/week4/requirements.md` - Week 4 需求规格
- `docs/week4/api-contract.md` - API 接口契约
- `docs/week4/tech-plan.md` - 技术实现计划
- `docs/week4/HANDOFF-TO-NEXT.md` - Week 4 完整交接文档

---

## ⏳ 待办事项（已过时）

> ⚠️ 本文档为 2026-04-06 版本，内容已过时。
> 最新版本见 `HANDOFF.md`（项目根目录）。

**已完成的待办**：
- ✅ 8象限语义确认 → 2026-04-16 升级为11象限（新增「偶遇沉睡」「边缘组合」）
- ✅ 618标签实现 → 尚未需要埋点数据，可暂缓

**当前待办（见主 HANDOFF.md）**：
- [ ] 缺口追踪需求确认
- [ ] 预测模型：识别潜在流失用户
- [ ] 预警系统：实时监控指标异常

---

**祝开发顺利！🎉**
