# CODEX-PROMPT-Sprint171 — 给 Codex app 复制的提示词

> **使用方式**：把下面 `=== CODEX PROMPT START ===` 到 `=== CODEX PROMPT END ===` 之间的内容**整段复制**到 Codex app 的对话框。
> Codex 会自动读 `AGENTS.md`（项目根） + 你给的 HANDOFF 文档，按 Stage 2 实施。

---

## === CODEX PROMPT START ===

你是 Codex app（Sprint 171 Stage 2 实施者）。本任务是把 `scripts/ad_hoc_query.py` 从「3 子命令 MVP」升级到「9 子命令 + AI 问数 + Excel 多 sheet」v2.0 版本。

**分支**：`feature/sprint171-ad-hoc-query-v2`（已建好，**不要再创建新分支**）

**必读文件**（按顺序读）：

1. `docs/sprints/HANDOFF-TO-CODEX-Sprint171.md` — **完整读**，这是任务全部规格
2. `~/.claude/skills/ad-hoc-query/SKILL.md` — v2.0 skill 规格
3. `scripts/ad_hoc_query.py` — 入口
4. `scripts/ad_hoc_queries/registry.py` — QuerySpec 注册表
5. `scripts/ad_hoc_queries/_utils.py` — 共享工具
6. `scripts/ad_hoc_queries/daily_gsv.py` + `yoy_battle.py` + `channel_slice.py` — 已实现 query 的范本
7. `backend/services/metrics/audience_summary.py` — `calculate_audience_summary` 用法
8. `backend/services/metrics/audience_table.py` — `get_audience_table` 用法
9. `backend/services/rfm/service.py` — `get_rfm_distribution` 用法
10. `backend/semantic/segments.py` — `R_SEGMENT_ORDER` 6 桶口径
11. `backend/services/__init__.py` — `PeriodBuilder` 用法
12. `backend/contracts/schemas.py` — `AudienceSummaryResponse` / `AudienceTableResponse` schema
13. `backend/tests/test_ad_hoc_query.py` + `test_ad_hoc_query_sprint61plus.py` — 现有 test 范本
14. `docs/development/services.md` — 加 service 规范
15. `docs/development/ratio-convention.md` — B1+B2 字段命名
16. `docs/development/testing.md` — test 写法
17. `AGENTS.md`（项目根）— 项目规则（Codex 自动注入）

**核心要求**（**0 妥协**）：

1. **直接 import backend services**（方案 A），禁 inline SQL、禁直连 DuckDB
2. **零写库**，只读 GET 端点等价物
3. **9 个子命令**：`daily-gsv` / `yoy-battle` / `channel-slice` / `two-year-overview` / `new-old-customer` / `rfm-repurchase` / `top-n` / `export-excel` / `dq-report` / `ask`（共 10 个，含 ask 路由）
4. **Excel 视觉规范**：深蓝 `#1F4E79` 表头、A 股红绿正负 `#D32F2F` / `#2E7D32`、**0 公式**
5. **Sheet 顺序**：`00_说明` / `01_数据排查报告` / `02_新老客30指标` / `03_单品概览TOP20` / `04_复购周期RFM` / `05_回购周期RFM` / `06_连带TOP20` / `07_品类流转矩阵` / `08_R区间回购周期` / `09_渠道概览` / `10_同品复购与回购店铺`
6. **R 6 桶**（Sprint 170 口径）：R1=0-7天 / R2=8-30 / R3=31-60 / R4=61-90 / R5=91-180 / R6=181+
7. **ask 路由不调 LLM**，纯关键词字典 + 简单正则

**实施步骤**（HANDOFF 第 6 节）：

1. 搭骨架（7 个新 query 文件 stub + 1 个 excel_styles + registry 注册）
2. 实现 service 调用层（每个 query 调对应 service 函数）
3. export-excel 多 sheet 装配（11 sheet + openpyxl 视觉）
4. dq-report 15 项校验（纯规则）
5. ask 路由（关键词字典）
6. pytest 配套（18 case: 5+3+5+5）
7. 全量验证

**验证命令**：

```bash
cd /Users/hutou/Desktop/fuqin-date/wt-main-active
export DUCKDB_PATH="$(pwd)/data/processed/fuqing_crm.duckdb"
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py list-endpoints
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py two-year-overview --year 2026 --start 2026-01-01 --end 2026-06-30 --format xlsx --output /tmp/test_two_year.xlsx
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py dq-report --start 2026-01-01 --end 2026-06-30 --full
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py ask --text "最近7天各渠道GSV"
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py export-excel --start 2026-01-01 --end 2026-06-30 --output /tmp/test_export.xlsx
```

**禁止动作**：

- ❌ 不要 `git add / commit / push / checkout / merge`，git 留给 Claude Stage 3 review + Stage 4 commit
- ❌ 不要改 `backend/services/*` 已存在函数
- ❌ 不要改 `frontend-vue3/*`
- ❌ 不要改 `scripts/run_etl.py` `scripts/etl/cli.py` `backend/db/connection.py`
- ❌ 不要改 `backend/contracts/schemas.py`（如需新字段先回报 Claude）
- ❌ 不要调 LLM（ask 子命令必须规则路由）
- ❌ 不要直连 DuckDB
- ❌ 不要 inline SQL

**完成时回报 Claude**（用 prose）：

1. 改了哪些文件（路径 + 行数）
2. pytest 数量（baseline 795 + 新增 18 = 813 期望）
3. 手动跑通的 2-3 个 query 例子（XLSX 路径 + sheet 数）
4. 任何不确定或卡住的地方

**遇到这些情况立即停手回报**：

- backend service 函数签名跟 HANDOFF 描述不符
- 字段在 schema 找不到
- R 6 桶口径有歧义
- 视觉规范有歧义
- pytest baseline 已退化

不要自己拍板改 backend 或前端。

## === CODEX PROMPT END ===

---

## ⚠️ v2 修正（2026-06-30, 架构师回执你之前的 STOP）

如果你是**看到 v1 提示词就 STOP 了**，请把下面这段作为「v2 修正」追加到你收到的 v1 提示词末尾，然后再开始实施：

---

### v2 修正要点

**1. RFM service 路径修正**：
- ❌ `from backend.services.rfm.service import get_rfm_distribution`（不存在）
- ✅ `from backend.services.rfm.r_flow import get_rfm_r_flow`
- 签名：`get_rfm_r_flow(start_date, end_date, channel=None, metric_type='GMV')`
- 返回结构：`result["r_segments"]` 是 R 6 桶列表，每桶含 `name / user_count / gsv / aus / repurchase_rate / share_pct`

**2. R 6 桶真实口径**（不是 R1-R6，是中文名）：
- `近1个月已购客` (0-30 天)
- `近2-3个月已购客` (31-90 天)
- `近4-6月已购客` (91-180 天)
- `近7-12个月已购客` (181-365 天)
- `近13个月-近24个月已购客` (366-730 天)
- `2年外已购客` (731+ 天)
- `已购客TTL` (汇总)
- 写代码直接 `from backend.semantic.segments import R_SEGMENT_ORDER`

**3. 旧 MVP 重构决策**：
- ❌ 不需要重构 `daily_gsv.py` / `yoy_battle.py` / `channel_slice.py` / `_utils.py`
- ✅ 这 4 个文件保留 `read_only_conn` + inline SQL，**只加 Sprint 171 docstring 顶部说明**（不重构避免破坏 29 case）
- ✅ 新加的 6 个 query 文件 + `excel_styles.py` 必须走 service 函数，禁 inline SQL / duckdb.connect

**4. 验收标准 #7 修改**：
- 旧版：「scripts/ad_hoc_queries/ 下 duckdb.connect 0 命中」
- 新版：「scripts/ad_hoc_queries/ 下**新文件** duckdb.connect 0 命中；旧 4 个文件允许保留 duckdb.connect，但必须加 Sprint 171 docstring」

完整 v2 addendum 见 `docs/sprints/HANDOFF-TO-CODEX-Sprint171.md` 末尾「ADDENDUM v2」章节。

---

### v3 修正要点（2026-06-30, 架构师再次 STOP 回执）

**1. codegraph 教训**：架构师 v1 凭记忆写 R 6 桶边界导致完全错误。Codex 已经查证。架构师永久规则：**写代码相关业务规格前必须 `codegraph_search` + `git grep` 实证，不脑补业务口径**。

**2. R 6 桶 vs 老客分析 防串台硬规则**：

| Sheet | 字段前缀 | 走 service |
|---|---|---|
| Sheet 02 新老客 30 指标 | `new_gsv` / `old_gsv` / `member_gsv` / `all_gsv` | `calculate_audience_summary` |
| Sheet 04 复购周期 RFM | `r_seg_name` / `r_seg_user_count` / `r_seg_gsv` / `r_seg_repurchase_rate` / `r_seg_share_pct` | `get_rfm_r_flow` |
| Sheet 09 渠道概览 | `channel_name` / `channel_gsv` / `channel_user_count` | channel-slice 内部 |

**硬规则**：
- ❌ 任何 sheet 不能用裸 `gsv` / `users` / `aus` 字段名
- ✅ 必须带 sheet 专属前缀（`new_` / `old_` / `r_seg_` / `channel_`）
- ❌ Sheet 02 和 Sheet 04 不共享任何中间变量
- ✅ 每个 sheet 调**独立**的 service 函数（不调一次 service 后拆给多个 sheet 复用）
- ✅ `new_old_customer.py` 和 `rfm_repurchase.py` 顶部加防串台 docstring（互相独立声明）

**3. XLSX 表头用合并单元格明示维度**：

```
Sheet 02 表头（一级 + 二级）：
| 维度: 新老客       | GSV_2026 | GSV_2025 | GSV_yoy | 人数_2026 | 人数_2025 | 人数_yoy | AUS_2026 | AUS_2025 | AUS_yoy |
| 全店 (all)         |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |
| 新客 (new)         |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |
| 老客 (old)         |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |
| 会员 (member)      |   ...    |   ...    |   ...   |    ...    |    ...    |   ...    |    ...   |    ...   |   ...   |

Sheet 04 表头：
| 维度: R 区间       | 人数 | GSV | AUS | 复购率(%) | 占比(%) |
| 近1个月已购客     | ...  | ... | ... |   ...     |   ...   |
| 近2-3个月已购客   | ...  | ... | ... |   ...     |   ...   |
| ...                |      |     |     |           |         |
```

**4. Stage 2 验收标准追加 3 条（v3 总共 13 条）**：
- #11: 新文件 `new_old_customer.py` 和 `rfm_repurchase.py` 顶部加防串台 docstring
- #12: Sheet 02/04/09 字段前缀严格分离（grep `_gsv\b` 验证 export_excel.py 里 0 裸 `gsv` 字段）
- #13: export_excel.py 每个 sheet 调独立 service，不复用中间 dict

完整 v3 addendum 见 `docs/sprints/HANDOFF-TO-CODEX-Sprint171.md` 末尾「ADDENDUM v3」章节（F codegraph 教训 + G 防串台 + H 验收标准）。

---

---

## 备忘（给 Claude 自己看，不复制给 Codex）

- HANDOFF 在 `docs/sprints/HANDOFF-TO-CODEX-Sprint171.md`
- SKILL 升级在 `~/.claude/skills/ad-hoc-query/SKILL.md`（已完成）
- 改完 Codex 回报后，Claude 进入 Stage 3 review → Stage 4 commit/push
- 12 步流程：feature branch（已建）→ codex 改 → pytest → review → qa → merge → push main → pull → restart → 删分支 → audit