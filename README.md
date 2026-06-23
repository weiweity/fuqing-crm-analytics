# Sample CRM 客户分析系统

> 内部运营中台工具 · 数据驱动的客户洞察 · 每日 9 点自动推送

---

## 项目简介

Sample CRM 客户分析系统是为Sample电商运营团队打造的内部数据中台，处理 **1030 万订单 / 410 万用户**（2020-2026）的数据规模，提供实时的客户洞察能力。

### 核心价值

- ⏰ 每日 9 点自动推送运营洞察
- 📊 口径唯一可信，改一处全局生效
- 🔍 多维度分析：老客健康 / 市场对焦 / 品类 / 人群 / 地域
- 📤 一键导出复盘数据

### 当前状态

- ✅ 语义层 / 契约层 / 服务层 / 前端 Vue3 全部上线
- ✅ 核心看板：指标概览 / 老客健康分析 / 市场对焦 / 品类 / 人群
- ✅ ETL 增量更新正常（截至 2026-06-22：orders 10,747,441 / users 4,762,870 / 补 6/16 + 6/17 数据 +1.68M 行 / 6/22 baseline 入仓）
- ✅ 后端代码审计完成，大文件拆分完成
- ✅ CI/CD 防线：pre-commit (ruff + pytest) + pre-push (pytest) + GitHub Actions + ground-truth-lint (Sprint 17 #121)
- ✅ 测试 768 passed / 21 skipped (本地 macOS) + Linux CI runner 741 passed / 21 skipped / 62 deselected (Sprint 66 P1 治根实证) + Vite build 0 错误 + e2e 12/12 PASS + SQL f-string lint 0 violations + L3 FilterBuilder 14/14 service 100% 闭环 (v0.4.14.156, Sprint 90 收口; 累计 Sprint 34.1+36.4+50+50.1+53+53.5+54 共同构成 AI write safety net + Sprint 60+60.1+60.1.1+60.2 500 错误治根 + Sprint 61 P2 fail-fast + Sprint 62 /ad-hoc-query 3 子命令 + Sprint 62.5 4 项磁盘清理治根 (169GB→95GB+53GB 释放) + Sprint 63 CI 维修 + Sprint 64 ruff-action v4 revert + Sprint 66 CI 维修 P0+P1 (lint.yml FQ_DB_MODE 漏修跨 5+sprint 复发治根 + codex_clone_gc 平台检查从 gc_once 迁 main) + housekeeping 3 类清理 (2 stale remote + 6 git stash + 13 Codex turn-diffs checkpoint) + Sprint 67+68 留尾 SSOT 治理 (L4.12 永久规则) + Sprint 69 MEMORY dedupe + Sprint 70-88 累计 19 sprint 0 业务代码反思 + Sprint 89 暂收口 + Sprint 90 L4.7 ground-truth-lint 防回归真业务 sprint (Sprint 60+ 留尾 1 项闭环) + L4.1-L4.18 永久规则 18 条)
- ✅ 痛点 1 闭环：Sprint 22 #26 跑批 3 次平均 18.0 min (< 35 min 目标, CV 9.4%)
- ✅ DuckDB race 治根：Sprint 22 #30 验证 1.5.4 上游已修, 30 workers × 100 writes 0 race
- ✅ Claude Code 自动化：3 hooks (PreToolUse 禁 .env/.duckdb + PostToolUse regen 提醒 + ruff) + 3 skills (regen-types + ship-pr + /ad-hoc-query 即席查询 CLI, Sprint 62 扩 3 子命令 daily-gsv/yoy-battle/channel-slice) + MCP context7
- ✅ uvicorn 守护：Sprint 62 launchd plist KeepAlive 守护, kill -9 自动 8s restart (P3 治本, 防止 sleep/wake crash 复发)
- ✅ repo 公开：weiweity/fuqing-crm-analytics (PUBLIC, 2026-06-13)
- ✅ Sprint 25-29+#198 完整收口 (v0.4.14.98 备份系统 + v0.4.14.99 F6 mtime→lsof + v0.4.14.100 Tooltip 5346% + v0.4.14.101 冷启动 mtime 阈值 + v0.4.14.102 RFM config 冲突 + v0.4.14.103 disk full 上游 + #198 RFM stuck index)
- ✅ Sprint 30.1-30.5 完整收口 (v0.4.14.105 W4 540 combo batch INSERT 50.4× 加速 + v0.4.14.106 CHANGELOG post-merge hint + v0.4.14.107 cohort matrix B2 audit + v0.4.14.108 `*_rate` 文档对齐 + v0.4.14.109 端到端真验 W4 < 30s)
- ✅ Sprint 31.1-31.2 完整收口 (v0.4.14.111+v0.4.14.112 tracker-database 模式 5 次复发终极治根 + v0.4.14.113 P2 fix tracker DB 加进 _PROTECTED_BASENAMES + v0.4.14.115 Sprint 30.3 留 12 字段 ratio/rate 范围约束补标, 14 test case)
- ✅ Sprint 32.1 收口 (v0.4.14.114 Playwright HTTPS error tolerance — chromium v1208 SSL hardening, 2 layer fix 必要: 浏览器运行时 config + Node 端 cert 信任)
- ✅ Sprint 33-37 完整收口 (v0.4.14.118 vite build hook + 8 e2e view smoke + v0.4.14.119 churn.py:418 漏 f 前缀治根 + SQL f-string L1 lint + v0.4.14.125 types.ts 重新生成, S36-6 /v1/flow/sankey 前端 ghost 类型闭环, 净删 114 行)
- ✅ Sprint 38 收口 (v0.4.14.126 race flake 治标, 5 sprint 复发 S32.3/S34.1/S36-1/S37/S38 透明化, 3 个真连 test 加 _IN_XDIST_PARALLEL skipif, pre-push 加 uvicorn 状态检测, ATTACH 真治本 ROI 重评为低)
- ✅ Sprint 39.1 收口 (v0.4.14.127 GH Actions CI 爆红修复, 7+ sprint 一直红闭环, conftest.py 加 _PROD_DUCKDB_AVAILABLE 跨 3 个真连 test 加 skipif, 模拟 CI DUCKDB_PATH=/tmp/nonexistent 跑 16 skipped / 0 failed / exit 0)
- ✅ Sprint 39.2 收口 (v0.4.14.128 visitor chain + export/report chain ground-truth audit doc 闭环, Sprint 36-1 plan-eng-review "visitor 业务风险高" 误判校正, 实查 visitor backend 100% 活跃 + frontend API 100% 活跃 + AudienceView 真消费, 唯一缺 = frontend router 注册; Sprint 52 已激活 visitor 路由)
- ✅ Sprint 40 收口 (v0.4.14.129 Sprint 40+ ground-truth audit + 推后排期, 6 项 Sprint 40+ 候选 ROI 重评, Sprint 41 CI e2e 本 sprint 执行)
- ✅ Sprint 41 收口 (v0.4.14.131 CI 跑 e2e 自动化, Sprint 32.1 留尾 7 sprint 闭环, 3 commit 实战: Sprint 41 加 e2e job + Sprint 41.1 disk full fix + Sprint 41.2 npm ci --legacy-peer-deps, GH Actions 4 job 自动化: lint + ground-truth-lint + pytest + e2e)
- ✅ Sprint 41 实战 follow-up (v0.4.14.132, 12 follow-up commits: Sprint 41.1 disk + 41.2 npm ci + 41.3 vue-tsc + 41.4 uvicorn + 41.5 token + 41.6 spec typo + 41.7 serial + 41.8/41.9/41.10 3 个 timeout + 41.11 set -e + 41.12 e2e advisory, GH Actions 实战 fix 闭环 0→1 失败改 advisory 0→1 跟 ground-truth-lint 一致, 实战教训写入 `docs/operating/ci-e2e-history.md`)
- ✅ Sprint 42 收口 (v0.4.14.132 spec-lint 预防层 + CI 实战 fix 框架沉淀, doc-only, 4 产出物: `docs/operating/ci-defense-playbook.md` 3 层防御 + Q1-Q4 决策树 + 5 步响应流程 + `frontend-vue3/e2e/lint/spec-lint.sh` 3 条规则防 Sprint 41.5/41.6/41.8/41.9 复发 + regression test 3/3 case pass + `CLAUDE.md` L5.1 + L5.2 永久规则, 起步 advisory 跟 ground-truth-lint 一致; 实战 fix 模式 ROI 重评: 治本 < 1 天 + 治本后 0 复发 → 治本, 治本 > 2 天 OR 治本不现实 → 治标, 跟 Sprint 38 race flake 治标同源)
- ✅ Sprint 50+ #S43-L2 收口 (v0.4.14.135 L2 AST parser 升级 spec-lint, 3 文件新功能: `frontend-vue3/e2e/lint/spec-lint-l2.py` 357 行 + wrapper + 5 case regression test, L1 保留 fallback, VERSION drift fix 0.4.14.132 → 0.4.14.135)
- ✅ Sprint 50.1 收口 (v0.4.14.136 pre-commit spec-lint hook 默认切 L2 wrapper + `frontend-vue3/package.json` 新增 `lint:spec` npm script, L1 fallback 保留, 不加未使用 npm tree-sitter 包)
- ✅ Sprint 51 收口 (v0.4.14.137 DQ 磁盘/增长监控 + e2e auth fixture 抽离 + sampling timeout 修复)
- ✅ Sprint 52 收口 (v0.4.14.138 visitor 路由激活 + 50m scale benchmark + commit-msg diff 一致性 WARN hook, Codex 协作工作流验证)
- ✅ Sprint 53 收口 (v0.4.14.138 race flake 真治本: per-worker tmp DuckDB + ATTACH read_only, 5 sprint 复发根因消除, 677 passed / 1 skipped)
- ✅ Sprint 53.5 收口 (v0.4.14.138 L3 FilterBuilder 治本: churn.py 5 处 `{valid_sql}` + 用户输入 f-string 内嵌全部参数化, 闭环 CLAUDE.md L3 backlog, 683 passed / 1 skipped)
- ✅ Sprint 54 收口 (v0.4.14.138 L3 FilterBuilder 100% 闭环 14/14 service + 6 case regression test + 749 passed / 1 skipped, Codex 3-lane 并行 Lane A/B/C + Stage 3 review 抓 1 真 bug distribution.py channel_filter NameError)
- ✅ Sprint 55 收口 (v0.4.14.138 CI 实战 fix 4 次: 55.0 HEALTH_API_KEY env + 55.1 F401 unused import + 55.2 test_lint debug print + 55.3 subprocess cwd 显式传修 CI Python 3.14 venv crash)
- ✅ Sprint 55.5 收口 (v0.4.14.139 22 项 audit workflow 5 phase 闭环 + docs 子目录化 11 git mv + P0 命名重构 facade 删 + sample → asset_focus + 4 新 doc + 4 stub 填 P0 死链接, 758 passed / 1 skipped)
- ✅ Sprint 56 收口 (v0.4.14.140 doc-only 5 phase + Phase 3 后置 drift fix 闭环 + CHANGELOG 1734→1286 行 + 4 stub doc DRY 拆解 + testing.md + services.md + SPRINT_INDEX.md)
- ✅ Sprint 57 收口 (v0.4.14.141 文档沉淀主题 3 worktree + Claude 接管 fallback + #10 LESSONS_LEARNED.md 679 行 9 pattern + #9 4 doc 扩内容 +458 行 + #7 services.md §5 asset_* 命名混淆)
- ✅ Sprint 58 收口 (v0.4.14.142 工具链实战 fix 闭环 + #4 CI e2e 持久化 + auto_recover_ci.sh + #1 OOM 治本 DuckDB ATTACH + #2 commit-msg blocking 误报率 0%)
- ✅ Sprint 59 收口 (v0.4.14.143 收割季 + Codex consult 24/24 全部吸收 + #6 STATUS.md 自动化 + #5 CHANGELOG 按行数归档 ≤ 900 行 + #8 audit 措辞 SOP only)
- ✅ Sprint 60+ 累计 4 sprint 收口 (v0.4.14.147 main HEAD ea44dd4 + 9 commit 0 debt + Sprint 60 params 顺序错位 + Sprint 60.1 Binder 500 channel 别名 + Sprint 60.1.1 Pydantic 422 + distribution 漏修 + Sprint 60.2 RFM 8 象限 老客 GSV TTL 100%)
- ✅ Sprint 60.3+ 收口 (v0.4.14.149 main HEAD f31626e + fix(ci) CI test job 排除 pytest.mark.slow 避免 10.6M 行 DuckDB integration 测试 hang + CI 4/4 全绿)
- ✅ Sprint 61 收口 (v0.4.14.150 main HEAD 71a3ebc + 4 dead code 删 + 2 过气 doc 删 + CHANGELOG 归档 + STATUS 同步 + 7 commit 0 debt + README Sprint 54-61 状态行 + 后端 main.py 启动 fail-fast + /ad-hoc-query skill MVP)
- ✅ Sprint 62 收口 (v0.4.14.150 main HEAD 4a5a3e3 / feat/sprint62-rollup-2026-06-22 + /ad-hoc-query 扩 yoy-battle + channel-slice 2 子命令 + P3 uvicorn launchd 守护脚本 + 8 文件 +995 行, 29/29 pytest pass)
- ✅ Sprint 57 收口 (v0.4.14.141 文档沉淀主题 3 worktree + Claude 接管 fallback + #10 LESSONS_LEARNED.md 679 行 9 pattern + #9 4 doc 扩内容 +458 行 + #7 services.md §5 asset_* 命名混淆)
- ✅ Sprint 58 收口 (v0.4.14.142 工具链实战 fix 闭环 + #4 CI e2e 持久化 ci-e8-history.md + auto_recover_ci.sh + #1 OOM 治本 DuckDB ATTACH read_only + #2 commit-msg blocking 误报率 0% THRESHOLD_RATIO 10 + MIN_DIFF_LINES 100)
- ✅ Sprint 59 收口 (v0.4.14.143 收割季 + Codex consult 24/24 全部吸收 + #6 STATUS.md 自动化 scripts/status_update.py + #5 CHANGELOG 按行数归档 ≤ 900 行 + #8 audit 措辞 SOP only AUDIT-WORDING.md)
- ✅ Sprint 60+ 累计 4 sprint 收口 (v0.4.14.147 main HEAD ea44dd4 + 9 commit 0 debt + Sprint 60 params 顺序错位 DuckDB excess parameters + Sprint 60.1 Binder 500 channel 字段加 o. 别名 + Sprint 60.1.1 Pydantic 422 wool_party_ratios > 1.0 强截断 + distribution 漏修同根因跨 lane + Sprint 60.2 RFM 8 象限老客 GSV TTL 100%)
- ✅ Sprint 60.3+ 收口 (v0.4.14.149 main HEAD f31626e + fix(ci) CI test job 排除 pytest.mark.slow 避免 10.6M 行 DuckDB integration 测试 hang + CI 4/4 全绿 lint + ground-truth-lint + test + e2e advisory)
- ✅ Sprint 61 cleanup (v0.4.14.149 + 4 dead code 删 + 2 过气 doc 删 + CHANGELOG 归档 ≤ 900 行 + STATUS 同步 + 768 pytest 持续 + docs/sprint61-readme-sync-2026-06-22 README 同步 Sprint 34.1→61)

---

## 快速开始

### 一次性激活 githooks

```bash
bash scripts/setup-hooks.sh   # 激活 pre-commit / pre-push (一次性, session 保持)
```

> **根因 (B1 P1-3 review, 2026-06-06)**: `core.hooksPath` 默认指向空目录, `.githooks/pre-commit` 在大多数开发者机器上是死代码。演示代码检查 (gstack review / autopilot) 会跳过 hooks, 必须手动激活。

### 启动服务

```bash
cd "/Users/yourname/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend \
  >> /tmp/fuqin-crm-backend.log 2>&1 &
cd frontend-vue3 && npm run dev
```

- 后端 API: http://localhost:8000
- 前端界面: http://localhost:5173
- API 文档（无需登录）: http://localhost:8000/docs

### ETL 增量更新

```bash
# 必须用 homebrew Python 3.14（workbuddy Python 3.13 有代码签名冲突）
PYTHONPATH="$(pwd)" /Users/yourname/homebrew/bin/python3 scripts/run_etl.py --update
```

### 即席查询 CLI（`/ad-hoc-query` skill, Sprint 62 3 子命令）

```bash
# 日序列 GSV + customers + YOY% (Sprint 61 MVP)
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py daily-gsv \
  --start 2026-06-01 --end 2026-06-21

# 双窗口 YOY 战斗, --metric all 一键 4 指标 (Sprint 62 新增)
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py yoy-battle \
  --baseline-start 2025-06-01 --baseline-end 2025-06-21 \
  --current-start  2026-06-01 --current-end  2026-06-21 \
  --metric all

# 按 channel 切片日维度, 全店排第一行 (Sprint 62 新增)
PYTHONPATH="$(pwd)" python3 scripts/ad_hoc_query.py channel-slice \
  --date 2026-06-21 --compare yoy

# 走 Claude Code skill (跟 .claude/skills/ 注册同步)
# 直接说: "跑 daily-gsv 2026-06-01~2026-06-21" 或 "yoy-battle 618 大促去年 vs 今年"
```

输出双层目录规则（不传 `--output` 时）：

```
~/Desktop/fuqin date/取数/
└── 2026年/                                      ← 业务基期年份
    └── 2026年6月22日/                          ← 生成日期
        └── 2026年-2026年6月22日-YOY对比/        ← 业务上下文
            └── YOY对比-2026-06-01至2026-06-21.csv
```

设计原则：复用 `backend/semantic/` 口径层（`OrderFilters.valid_order` / `calculations.yoy_absolute` / `safe_ratio`）+ `read_only=True` DuckDB 连接跟 uvicorn 共存（Sprint 53 race flake 治本同模式）+ 时间窗口 ≤ 366 天（防 OOM）。详见 `.claude/skills/ad-hoc-query/SKILL.md`。

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 数据处理 | Python + Pandas + DuckDB |
| 后端 API | FastAPI + Pydantic |
| 前端界面 | Vue3 + Vite + ECharts 6 + Tailwind CSS + naive-ui |
| 状态管理 | Pinia + TanStack Query |
| 语义层 | backend/semantic/（口径唯一真实数据源） |
| 契约层 | backend/contracts/schemas.py（Pydantic → OpenAPI → TypeScript） |

---

## 项目结构

```
fuqing-crm-analytics/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 应用入口（端口 8000）
│   ├── semantic/               # 语义层（口径定义唯一来源）
│   ├── contracts/              # 契约层（Pydantic 模型，135个类）
│   ├── services/               # 业务逻辑层（按业务域拆分为包）
│   │   ├── category_service/   # 品类分析（flow/repurchase/distribution/...）
│   │   ├── health/             # 老客健康分析（rfm_analysis/overview/repurchase/...）
│   │   ├── metrics/            # 指标服务
│   │   ├── rfm/                # RFM 区间流转（r_flow/f_flow/m_flow/segment_orders）
│   │   ├── breakdown_service/  # 一键拆解（forward/reverse/suggestions/main）
│   │   └── dmp_asset_service/  # DMP 资产（store/product/other）
│   ├── routers/                # API 路由（16 个模块）
│   ├── db/                     # 数据库连接
│   └── tests/                  # 单元测试（41 个 test 文件, 499+ passed / 15 skipped）
├── frontend-vue3/              # Vue3 前端
├── scripts/                    # ETL 脚本
├── config/                     # 配置（健康评分、RFM 阈值）
├── data/                       # 数据（raw/processed/parquet/cache）
└── docs/                       # 项目文档（CLAUDE.md / CHANGELOG.md / TECH-DEBT.md / ...）
```

---

## 架构原则

1. **语义层唯一真实数据源**：口径只定义一次，禁止在 Service 中硬编码 SQL
2. **双保险过滤**：`is_refund=FALSE` 且 `order_status!='交易关闭'`
3. **契约层外置**：所有 Pydantic 模型统一从 contracts/schemas.py 导入
4. **前端只做展示**：禁止前端计算 YOY/占比等业务指标
5. **连接零泄漏**：DuckDB 连接必须 try/finally 关闭

---

## 文档导航

完整文档列表见 `docs/` 目录 + `CHANGELOG.md` 版本变更记录。

### 核心文档速查

| 文档 | 说明 |
|---|---|
| [CLAUDE.md](./CLAUDE.md) | **项目权威参考**（Git 工作流 + 架构 + 规范 + AI 检查点） |
| [CHANGELOG.md](./CHANGELOG.md) | 版本变更记录 (v0.4.14.155, Sprint 66 收口) |
| [docs/operating/automation.md](./docs/operating/automation.md) | Claude Code 自动化配置 (3 hooks + 2 skills + MCP) |
| [docs/operating/ship.md](./docs/operating/ship.md) | /ship skill 使用文档 |
| [docs/operating/linting.md](./docs/operating/linting.md) | ground-truth-lint 规则 (Sprint 17 #121) |
| [docs/architecture/50m-scale-architecture.md](./docs/architecture/50m-scale-architecture.md) | 50M 订单规模架构设计 |

---

## 运维安全 / 磁盘治理

2026-06-05 治理后,系统落地 6 层防护防止子 agent 调试 / ETL 异常退出 / subagent 走手动 shutil.copy2 漏写时 `/private/tmp` 累积巨型 duckdb 孤儿（曾一度 7 个 38-44GB 文件吃满 349GB 磁盘）。接手者必读。Sprint 4 加 P0-2 launchd 每日备份变第 5 层 (数据灾备兜底)。Sprint 6 P0-3 加 hourly 兜底变第 6 层 (subagent 路径加固, 防 437GB disk 涨重复 — Sprint 5 deep dive 教训).

### 6 层防护

| 层 | 路径 | 触发 | 作用 |
|---|---|---|---|
| 1. atexit 钩子 | `scripts/etl/cli.py:_cleanup_fq_tmp_orphans` | ETL 进程退出 | 主防线:扫 `FQ_TMP_PREFIXES` 白名单,删 24h+ / 5 文件 / 100GB cap,软失败+持久日志 |
| 2. zshrc 告警 | `~/.zshrc:_check_fq_tmp_orphans` | zsh 启动 | 人因防线:检测 50GB+ 占用打印告警,不删 |
| 3. workbuddy cache | `~/.workbuddy/cache/fq-etl-validation/` | 调试时主动 cp | 调试便捷:30 天 TTL + 时间戳命名,不再污染 /tmp |
| 4. launchd weekly cleanup | `scripts/etl/cleanup_backups.sh` + plist | 每周日 03:00 | data 目录独立防线:`data/processed/backups/` 7 天保留清理 |
| 5. **launchd daily backup (Sprint 4 P0-2)** | `scripts/etl/backup_duckdb.py` + `com.fuqing.duckdb-backup.daily.plist` | 每日 03:30 | 数据灾备:103GB DuckDB shutil.copy2 (os-level, 不冲突 uvicorn 持锁) + zstd 压缩 → 40GB (.duckdb.zst, 2.575:1 压缩比, level 3), 7 天由 weekly cleanup 兜底, 含 post-copy verify 防 APFS torn copy |
| 6. **launchd hourly subagent cleanup (Sprint 6 P0-3)** | `scripts/etl/cleanup_subagent.py` + `com.fuqing.tmp-cleanup.hourly.plist` | 每日每 1 小时 | subagent 路径兜底:扫 `/private/tmp` + `/tmp` 下 1h+ 1GB+ 非白名单文件 (排除项目根 + layer 1 自身状态文件 + 代码/日志扩展名), cap 5 文件 / 100GB. 解决 Sprint 5 deep dive 教训:subagent 走手动 `shutil.copy2` 复制 production 55GB × 8 次 = 440GB 在 `/private/tmp/p0_3_dive/`, 5 层防护因白名单设计 (FQ_TMP_PREFIXES) 都没拦. |

### 紧急清理命令

```bash
# 紧急清理 /tmp 下 fq_ 系列孤儿（不依赖 ETL 触发,运维手动跑）
PYTHONPATH="$(pwd)" python3 scripts/etl/cli.py --cleanup-tmp
```

### launchd 调度状态

```bash
launchctl list | grep fuqing
# 期望输出 4 行 (Sprint 6 P0-3 加 hourly 后):
# - 126  com.fuqing.backup-cleanup.weekly
# - 0    com.fuqing.tmp-cleanup.hourly      ← Sprint 6 P0-3 (Layer 6)
# - 0    com.sample.duckdb-backup.daily
# - 1    com.fuqing.etl.daily
```

### 审计与状态查询

| 文件 | 含义 |
|---|---|
| `/tmp/fuqing-tmp-cleanup.log` | Layer 1 钩子执行日志（持续增长,60KB+ 正常） |
| `/tmp/fuqing-subagent-cleanup.log` | Layer 6 钩子执行日志（hourly 跑, subagent 路径兜底） |
| `/tmp/fuqing-etl-marker.json` | F3 marker（ETL 运行时存在,退出时删,缺失 = 上次异常退出） |
| `/tmp/fuqing-etl-health.json` | SRE 0 飞书 0 代码状态查询入口（最近一次 ETL 跑批结果） |
| `/tmp/fuqing-backup-cleanup.lock` + `.log` | Layer 4 锁文件 + 执行日志 |

### 重要协议

- **F3 marker 不要 rm** — 钩子依赖 marker 判断上次是否异常退出,强删会导致下次误判
- **`/private/tmp/_fq_ro*` / `fuqing_*` / `claude-501/tmp*` 不要强删** — atexit 自动处理,强删会留 marker 孤儿
- **ms-playwright 缓存删除前** — 先 `find ~/Library/Caches/ms-playwright/ -name 'headless_shell*'` 确认无活跃进程,备份当前版本号 `cat ~/Library/Caches/ms-playwright/.links` 记录,删后 `playwright install --with-deps` 不会自动恢复 1208 版本（gstack browse 唯一兼容版本）

---

## 测试

### 后端单元测试

```bash
cd "/Users/yourname/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" pytest backend/tests/ -v
```

当前测试覆盖（741 passed / 21 skipped，Linux CI runner 实证 v0.4.14.155 Sprint 66 收口；本地 macOS 768 passed / 21 skipped）：
- `test_exceptions.py` - 异常类型和 HTTP 状态码映射
- `test_segments.py` - RFM 分群注册表和阈值定义
- `test_flow_service.py` - 人群流转服务
- `test_calculations.py` - YOY/MOM/safe_ratio
- `test_filters.py` - OrderFilters/FilterBuilder
- `test_time.py` - PeriodBuilder
- `test_channels.py` - 渠道漏斗/映射
- `test_api_integration.py` - FastAPI 集成测试
- `test_health_overview.py` - 健康概览
- `test_rfm_analysis.py` - RFM 分析
- `test_fill_parquet_cache.py` - Parquet 缓存
- `test_etl_atomicity.py` - ETL 原子写入
- `test_wo_cleanup_orphans.py` - /tmp 孤儿清理钩子（F3 marker + F7 symlink + cap 边界，20 用例）
- `test_w3w4_pipeline_smoke.py` - W3/W4 pipeline CI smoke test (P1-1 sprint 3, 8 用例, 端到端跑 run_full_etl)
- `test_w4_t7_integration.py` - W4 T-7 真跑验证 (痛点 3 闭环, 4 用例)
- `test_check_review_ground_truth.py` - P1-3 ground-truth lint (28 用例, 含 6 B2 idx/lineno + 7 H1 hex color + 8 B2 NOOP committed mode + 3 M1 fallback + 4 集成 e2e)

### CI/CD

PR 和 main push 自动运行 ruff lint + pytest。本地 pre-commit/pre-push hooks 在 commit/push 前拦截。

### E2E 测试

```bash
cd frontend-vue3
npx playwright test
```

当前 E2E 覆盖：
- `customer-health.spec.ts` - 老客健康页面路由和 Tab 渲染

---

## 核心数据指标

| 指标 | 口径 |
|---|---|
| GSV | 剔除购物金 + 退款的有效订单金额 |
| GMV | 剔除购物金，含退款的订单金额 |
| 新老客 | cutoff = 查询起始日 - 1 天，此前有购买 = 老客 |
| RFM | R=最近购买天数, F=购买频次, M=消费金额 |

---

## 变更历史

详细变更记录见 [CHANGELOG.md](./CHANGELOG.md)（semver 格式）。

| 日期 | 事件 |
|---|---|
| 2026-03-27 | 项目启动，v1.0 架构设计 |
| 2026-04-16 | v3.0 架构重构（语义层 + 契约层） |
| 2026-04-20 | Vue3 前端上线，RFM 8 象限重构 |
| 2026-04-28 | 安全加固（API Key、SQL 注入、CORS） |
| 2026-04-29 | ETL 增量更新完成，1030 万条数据 |
| 2026-05-04 | 文档整理，创建文档索引 |
| 2026-05-28 | 后端代码审计（23 问题修复），大文件拆分（6 个包），SPU 版本化 |
| 2026-05-29 | SQL 注入修复，未来日期警告，/docs 白名单，CHANGELOG 建立 |
| 2026-05-30 | pp 值双重乘法修复，173 lint 错误清理，pre-commit/CI 防线建立 |
| 2026-05-31 | 17 项 FIX-TASK-LIST 全部完成归档；v0.3.4 release |
| 2026-06-01 ~ 06-04 | RFM 4 端点 P0/P1 修复合集：8 象限 repurchase 改 ≥2 单（修 100%/0% 异常）、R/F/M TTL 修、value-tiers channel='全店' 特判、rfm-category-drilldown 500→400 |
| 2026-06-04 | 增量 ETL 跑批 6/4（real elapsed 63.2min / step sum 126.4min，4 新源文件）；baseline wall_time 字段歧义修；rfm_analysis_cache fail-soft 修（pipeline.py read_only 改默认 READ_WRITE） |
| 2026-06-06 ~ 06-07 | **Sprint 3 收口 4/5** (P0-1 痛点 1 W1 GROUPING SETS 13.4 min 闭环 + P1-1 W3/W4 CI smoke + P1-2 16 root tests isolation + P1-3 ground-truth lint 4 轮修). P0-2 DuckDB 备份 deferred Sprint 4. CI 三连绿 |
| 2026-06-13 ~ 06-14 | **Sprint 22-23 收口** (痛点 1 跑批 18 min 达标 + DuckDB race 治根 + 3 hooks + 2 skills + MCP context7 + repo 公开 + 项目整洁清理) |
| 2026-06-16 | **Sprint 24 收口** (Step 8 strict mode 修 v0.4.14.92 + 4 处 sibling read_only 治根 v0.4.14.95 + P2 清理 v0.4.14.96 + 3 条债全闭环 v0.4.14.97) |
| 2026-06-17 | **Sprint 25-29+#198 完整收口** (v0.4.14.98 备份系统可信化 + v0.4.14.99 F6 mtime→lsof 副检 + v0.4.14.100 Tooltip 5346% 治根 + v0.4.14.101 冷启动 mtime 阈值 + v0.4.14.102 RFM config 冲突 + v0.4.14.103 disk full 上游 + #198 RFM stuck index. 5 次复发 recurring pattern 治根, 端到端 ETL 跑批 ~32min ×2 验证, codex 第三方架构评审砍 Sprint 28+ #1/#4 patch 路线. 569/569 pytest + ruff pass + /qa 100/100. Sprint 30-32 待办: W4 540 combo batch INSERT + tracker-database 模式 + CHANGELOG post-merge) |
| 2026-06-17 | **Sprint 30.1-30.5 完整收口** (v0.4.14.105 W4 540 combo batch INSERT 50.4× 加速 + v0.4.14.106 pre-commit CHANGELOG 改 post-merge hint + v0.4.14.107 cohort retention matrix 4 字段 B2 audit + v0.4.14.108 `*_rate` 文档对齐 + v0.4.14.109 端到端真验 W4 < 30s. 591/591 pytest + ruff pass. 留 Sprint 30.3 剩余 contract 字段走 Sprint 31+) |
| 2026-06-17 | **Sprint 31.1 收口** (v0.4.14.111+v0.4.14.112 tracker-database 模式替代 prefix matching 机制错误, 5 次复发终极治根, SQLite sidecar `/private/tmp/fuqing-tmp-tracker.db` source of truth, bootstrap 1 run 治根 + 24h list_expired 2 run 治本. 564/564 pytest + ruff pass + 6 层防护表更新) |
| 2026-06-17 | **Sprint 31.1 P2 fix + VERSION 同步** (v0.4.14.113 tracker DB 加进 _PROTECTED_BASENAMES defense-in-depth, 2 P3 fix 闭环) |
| 2026-06-17 | **Sprint 32.1 收口** (v0.4.14.114 Playwright HTTPS error tolerance — chromium v1208 SSL hardening, 2 layer fix 必要: 浏览器运行时 config + Node 端 cert 信任, 部署侧 `NODE_EXTRA_CA_CERTS=certifi cacert.pem` 修 SELF_SIGNED_CERT_IN_CHAIN. 571 pass / 15 skip + 2/3 e2e 验证. 留 Sprint 32.2 e2e spec 回归) |
| 2026-06-18 | **Sprint 31.2 收口 + codex P3 fix** (v0.4.14.115 Sprint 30.3 留 12 字段 ratio/rate 范围约束补标 — TierFlowRow 5 ratio + 1 PpField + NewCustomerConversionFunnel 4 rate + MarketBasketItem 2 ratio, 14 test case, 业务实证 `yoy_repurchase_rate` = PpField 来自 `semantic.calculations.py:70-80`. 633 pass / 15 skip + 0 linter violation + codex review P3 fix: 删 `_YOY_PPT_FIELDS` dead code 3 行) |
| 2026-06-22 | **Sprint 60.3+ CI fix + Sprint 61 cleanup (v0.4.14.149 + f31626e + 285d912, CI 4/4 pass)** |
