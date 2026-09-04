# AI 增长董事会：架构与提交收口审计

> 审计时间：2026-09-05。本文是当前黑客松分支的架构解释、质量证据与剩余任务清单。运行契约仍以 `/openapi.json` 为准，产品路线以 [ROADMAP.md](./ROADMAP.md) 为准。

## 结论

当前产品已经不是“给旧 CRM 页面加一个聊天框”，而是一条独立、可审计的 CEO 决策链：系统从合成订单中识别一个经营 Mission，允许用户用受控语义工具追问证据，经人工审批后只生成带 90/10 对照组的草稿名单，再等待真实效果回收。

这个边界适合黑客松演示，也为后续“无人电商”保留了正确升级路径。现阶段不应开放任意 SQL，不应自动发短信，也不应把合成指标描述成真实公司业绩。

## 系统边界

```text
代码生成器
  └─ 合成订单 + 稳定 synthetic_user_id
       ├─ synthetic DuckDB（分析，只读）
       └─ manifest（来源、行数、内容哈希、contains_real_data=false）
                    │
                    ▼
MissionService（确定性经营逻辑）
  ├─ 今日唯一 Mission
  ├─ 渠道质量 / 生命周期 / 商品角色三类问数
  ├─ SQLite 控制面（状态、版本、审批、幂等）
  └─ 草稿导出目录（90% 实验组 / 10% holdout）
                    │
                    ▼
FastAPI Mission API（权限、If-Match、Idempotency-Key、OpenAPI）
                    │
                    ▼
Vue CEO 增长董事会（证据 → 追问 → 审批 → DRAFT_EXPORT）

归档真实 DuckDB（约 131GB）
  └─ 只服务既有分析系统；Mission 演示链不会回退读取它
```

### 数据面与控制面分离

| 边界 | 唯一职责 | 写入规则 |
|---|---|---|
| 合成 DuckDB | 订单、首付费渠道、生命周期和渠道质量分析 | 生成后只读 |
| manifest | 证明数据由代码生成且不含真实信息 | 与数据集一起生成，运行时复验 |
| MissionService | 把指标转成一个可决策的经营命题 | 不写分析库 |
| SQLite 控制面 | 保存版本、审批、幂等键和导出记录 | 仅状态接口可写 |
| 导出目录 | 保存合成用户的实验/对照组草稿 | 管理员审批后生成；重置时归档旧文件 |
| 前端 | 展示服务端事实并发起明确动作 | 不计算业务指标 |

## 对外业务契约

主链只有六个动作：

1. `mission_get_today`：读取今日 Mission。
2. `mission_diagnose`：调用三类确定性问数工具，不执行模型生成 SQL。
3. `mission_approve`：记录人类批准，要求版本和幂等键。
4. `mission_create_draft_export`：生成实验组与 holdout 草稿。
5. `mission_download_draft_export`：显式下载，不触发短信或 CRM 推送。
6. `mission_reset_demo`：仅本地管理员可用，归档旧草稿后恢复演示初态。

字段、错误码和调用示例见 [AI-TOOL-CALLING.md](./AI-TOOL-CALLING.md) 与 [MISSION-API.md](./MISSION-API.md)。

## 模块合理性评估

### 已经合理

- Mission 路由、Pydantic 契约、业务服务、前端 API 客户端和页面职责可追踪。
- 合成数据与真实库硬隔离；响应携带 `data_provenance` 和内容哈希。
- 写操作有管理员权限、乐观并发和幂等保护；导出后进入 `WAITING_MEASUREMENT`。
- 首付费渠道按稳定用户标识关联跨渠道订单，能解释“直播规模大但货架客户更值钱”的经营冲突。
- 本地重置采用归档而非删除，适合反复演示和审计。

### 需要在提交前收口

- `GrowthBoardView.vue` 同时承担数据编排、状态机和大量视觉实现。视觉重构应拆成品牌壳、Mission 英雄区、渠道表、自由问数和审批工作流组件，页面只负责组装。
- 旧全局导航和页面标题仍使用“芙清/天猫 CRM”品牌，与伸美黑客松作品不一致。
- 启动脚本的前端健康签名仍依赖旧页面标题；品牌重构时必须同步更新并补回归测试。
- 工作树里的空 `data/processed/fuqing_crm.duckdb` 可通过“文件存在且可连接”检查，却没有 `orders` 表，导致数据依赖测试误报。测试就绪条件应验证核心 schema，而不是只做 `SELECT 1`。
- 4 项旧测试依赖个人 `~/.claude/skills/ad-hoc-query/SKILL.md`，不属于可移植仓库依赖。后续应把契约测试改为读取仓库内资源，不能靠修个人电脑软链维持绿色。

## 文档合理性

### 主线

| 读者问题 | 入口 |
|---|---|
| 这是什么、为什么老板要看 | [CEO-PITCH.md](./CEO-PITCH.md) |
| 比赛表单怎么填 | [SUBMISSION-COPY.md](./SUBMISSION-COPY.md) |
| 评委怎么演示 | [README.md](./README.md) |
| AI 怎么安全调用 | [AI-TOOL-CALLING.md](./AI-TOOL-CALLING.md) |
| HTTP 字段与状态机是什么 | [MISSION-API.md](./MISSION-API.md) |
| 为什么这样设计、当前是否可交 | 本文 |
| 9 月与 10 月分别做什么 | [ROADMAP.md](./ROADMAP.md) |
| 商业判断有哪些外部依据 | [research/report-source.md](./research/report-source.md) |

### 文档规则

- `README.md` 只做入口，不再堆实现历史。
- `MISSION-API.md` 描述 HTTP；`AI-TOOL-CALLING.md` 描述 Agent 行为，避免混写。
- `ROADMAP.md` 只保留未完成工作；已完成证据进入本文或 `CHANGELOG.md`。
- 行业结论至少保留两个独立来源；代码能力只能由代码、测试或运行证据证明。

## 质量与远端证据

### 本地分支

分支 `codex/fix-local-demo-startup` 基于 `origin/main@89d3423`，当前有 4 个本地提交，未 push、未建 PR、未部署。

| 检查 | 结果 | 说明 |
|---|---|---|
| Vue 类型检查 | 通过 | 0 error |
| 前端单元测试 | 151 passed | 本轮真实执行 |
| 前端构建 | 通过 | Vite production build |
| Mission 后端测试 | 22 passed | 主链、重置、权限、幂等与隐私边界 |
| 数据 API 集成测试 | 9 passed | 显式只读指向真实库后通过 |
| 全仓 Ruff | 9 个旧错误 | 均位于 `origin/main` 既有脚本，本分支未新增 |
| 全量后端测试 | 未形成绿色证明 | 4 项个人 Skill 环境依赖失败；应在提交前消除或从 CI 合同中明确隔离 |

### GitHub 快照

- 当前 open PR：0。
- PR #65、#66 已合并；`origin/main` 为 `89d3423`。
- 该 SHA 的 CI、Nightly Health Check、E2E Smoke 均为 success。
- 本分支新增 4 个提交尚未进入远端，因此上述绿色记录不能替代本分支提交前验证。

## 剩余任务与执行顺序

| 顺序 | 任务 | 完成标准 | 状态 |
|---:|---|---|---|
| 1 | 伸美 VI + Liquid Glass 设计源 | Figma 有桌面/移动首屏和组件规则 | 下一步 |
| 2 | 前端组件化重构 | 数据与动作零丢失，消除超宽白边 | 待做 |
| 3 | 全局品牌壳统一 | Logo、标题、导航不再出现旧品牌 | 待做 |
| 4 | 测试就绪条件治本 | 空 DuckDB 不再造成假运行；个人 Skill 测试边界明确 | 待做 |
| 5 | 全量测试、构建、浏览器 QA | 目标分支证据可复跑，关键链路无控制台错误 | 待做 |
| 6 | 演示初态收口 | 页面停在“等待 CEO 审批”，重置可重复 | 待做 |
| 7 | 本地分支评审与 PR | 需用户单独批准 push / PR / merge | 未授权 |
| 8 | 公网部署与演示账号 | 等平台、域名和账号策略确定 | 明确暂缓 |

## 10 月前不该挤进本轮的能力

- 真实人群生命周期引擎与品类补货周期校准。
- 使用真实订单重算首次获客渠道和跨渠道生命周期。
- 自动营销计划、CRM 人群推送、短信供应商接入和失败补偿。
- 实验效果回收、增量毛利和长期 holdout 衡量。

这些是从“可演示的 L3 人机共驾”升级到“受控无人电商”的下一层，不应以隐藏副作用塞进 `DRAFT_EXPORT`。

