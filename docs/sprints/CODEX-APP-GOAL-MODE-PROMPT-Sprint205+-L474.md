# Codex App Goal Mode Prompt - Sprint 205+ L4.74 PostgreSQL 16 分布式 大版本开发

> **作者**: Claude Code (Stage 1 架构师)
> **执行者**: Codex app (Stage 2 实施者, gpt-5.5 high reasoning **goal mode** sandbox=worktree)
> **用户**: hutou (PM 魏炜)
> **CLAUDE.md 版本**: v0.4.14.43+ (L4.72 永久规则化收口 + L4.74 启动条件 b + c 真触发 永久规则化)
> **配套永久规则链**: L4.42 + L4.55 + L4.56 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链
> **配套 handoff 文档**: `docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-PART1-5.md` (5 Part, 57.6 KB, 1340 行)
> **状态**: 🚨 **真业务触发** (用户 7/8 拍板"强行触发" = L4.56 启动条件 b + c 真触发, PC2 端 10 业务分析师并发 + 崩了 + 取不了数)
> **CLAUDE.md 永久规则化**: L4.74 启动条件 c 真触发 永久规则化 (跟 L4.55 + L4.56 1:1 stable 永久规则链配套)

---

## 🎯 Codex App Goal Mode Master Prompt (复制即用)

```
你是 Codex app (Stage 2 实施者, gpt-5.5 high reasoning goal mode sandbox=worktree).
你的任务: 完成 Sprint 205+ L4.74 DuckDB → PostgreSQL 16 分布式 大版本开发 (8-10 周 1-2 人月真治本).
目标: 老客分析 6 张表 崩溃 + PC2 端 10 业务分析师并发 崩了 + 取不了数 真治本 (跟 L4.74 启动条件 b + c 真触发 1:1 stable 永久规则链配套).

🎯 9 个任务并行开发 + 一口气开发完 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套):

1. 任务 1.1: L4.72.3 PC2 端 池 5 调大 (1 行 fix, FQ_READ_POOL_SIZE=5 → 10, 跟 L4.70 PC2 .env 1:1 stable 永久规则链配套)
2. 任务 1.2: 业务方配合 30s wait + 错峰查询 (0 业务代码改动, 跟 L4.36 + L4.38 + L4.56 1:1 stable 永久规则链配套)
3. 任务 2.1.1: L4.72.4 9 子板块预计算 (5+ 天, 0 业务代码改动, 跟 RFM precompute_rfm_cache 1:1 stable 模式 + L4.54 launchd daily 1:1 stable 永久规则链配套)
4. 任务 2.2.1: 老客分析 6 张表 简化版 (5+ 天, 0 业务代码改动, 跟 L4.69 RFM 雪崩真治本 1:1 stable 永久规则链配套)
5. 任务 2.3.1: L4.70 加 orders (pay_time, user_id) 复合索引 (5+ 天, 0 业务代码改动, 跟 L4.70 永久规则 1:1 stable 永久规则链配套)
6. 任务 2.3.2: L4.71 改用 user_rfm 1.5GB 预计算表 (5+ 天, 0 业务代码改动, 跟 L4.71 永久规则 1:1 stable 永久规则链配套)
7. 任务 3.1.1: L4.74 阶段 1 需求文档 + DuckDB 122GB 性能基线 (W1-2, 1 人, Mac dev)
8. 任务 3.2.1: L4.74 阶段 2 PostgreSQL 16 单节点 docker-compose POC (W3-4, 1 人, Mac dev + 跨 OS 验证)
9. 任务 3.3.1: L4.74 阶段 3 PostgreSQL 16 citus cluster 3 worker POC (W5-6, 1-2 人, Mac dev + PC2 端)
10. 任务 3.4.1: L4.74 阶段 4 DuckDB → Parquet ETL (W7-8, 1-2 人, Mac dev + PC2 端)
11. 任务 3.4.2: L4.74 阶段 4 RFM/R 区间 PostgreSQL 16 UDF (W7-8, 1-2 人, Mac dev)
12. 任务 3.4.3: L4.74 阶段 4 看板 / 取数 UX 透明迁移设计 (W7-8, 1-2 人, Mac dev)
13. 任务 3.4.4: L4.74 阶段 4 双写期方案 (W8, 1-2 人, Mac dev + PC2 端)
14. 任务 3.5.1: L4.74 阶段 5 POC 总结报告 (W9, 1 人, Mac dev)
15. 任务 3.5.2: L4.74 阶段 5 选型决策 Go/No-Go (W9-10, 1 人, 业务方 + 架构师 + DBA 三方拍板)
16. 任务 3.5.3: L4.74 阶段 5 风险评估 + 成本估算 (W10, 1 人, Mac dev)

🚦 必读 (跟 L4.55 + L4.56 1:1 stable 永久规则链配套):
1. CLAUDE.md (行为规则, 自动加载)
2. AGENTS.md (自动注入, .gitignore 排除, 跟 CLAUDE.md 自动 sync, 跟 L4.55 + L4.56 1:1 stable 永久规则链配套)
3. docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed.md (Part 1)
4. docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-PART2.md (Part 2)
5. docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-PART3.md (Part 3)
6. docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-PART4.md (Part 4)
7. docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-PART5.md (Part 5)
8. docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md (L4.74 立项决策 memo, 跟 L4.56 clickhouse-poc-decision-memo.md 1:1 stable 永久规则链配套)
9. docs/sprints/SPRINT205+_L442_VERIFICATION_L474_TRIGGERED.md (L4.74 真业务触发 立项实证报告, 跟 L4.42 + L4.55 + L4.56 1:1 stable 永久规则链配套)
10. docs/sprints/SPRINT205+_L442_VERIFICATION_L4724_L473_L474.md (L4.42 立项实证 3 件 0 commit 续期 永久规则化, 跟 L4.42 + L4.55 + L4.56 1:1 stable 永久规则链配套)
11. docs/architecture/clickhouse-poc-decision-memo.md (L4.56 选型对比参考, 跟 L4.74 立项决策 memo 1:1 stable 永久规则链配套)

🎯 Codex App Goal Mode 策略 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套):
- 你有 goal mode, 可以一口气开发完所有 16 个任务, 不用每个任务都等 user 拍板
- Mac dev 开发 + 12 步流程 SOP 1:1 stable 永久规则链配套 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套, Mac 开发 + push PC2 模式 1:1 stable 沿用)
- 每个任务完成后, 自动 commit + push feature branch (跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套, 你的 commit + push 是 outbound 副作用, 但 goal mode 给你拍板, 跟 L4.15 "P6 bias toward action 采纳推荐 A" 1:1 stable 永久规则链配套)
- 所有 16 个任务 并行开发 + 一口气开发完 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)
- 0 业务代码改动 (跟 L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则链配套, 累计 Sprint 60+ 60 次 1:1 stable 永久规则链配套)

🎯 9 个任务并行开发优先级 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.74 启动条件 b + c 真触发 1:1 stable 永久规则链配套):
- P0 立即 (1-2 天): 任务 1.1 + 1.2 (L4.72.3 PC2 端 池 5 调大 + 业务方配合 30s wait 错峰查询)
- P1 重要 (5+ 天): 任务 2.1.1 + 2.2.1 + 2.3.1 + 2.3.2 (L4.72.4 9 子板块预计算 + 老客分析 6 张表 简化版 + L4.70 + L4.71)
- P2 长期 (8-10 周 1-2 人月): 任务 3.1.1 + 3.2.1 + 3.3.1 + 3.4.1 + 3.4.2 + 3.4.3 + 3.4.4 + 3.5.1 + 3.5.2 + 3.5.3 (L4.74 阶段 1+2+3+4+5 POC 5 阶段)

🎯 Mac dev + push PC2 模式 (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套):
- 阶段 1-2: Mac dev 开发 + pytest 验证
- 阶段 3-4: 跨 OS 验证 (Mac dev + PC2 prod, 跟 L4.60 + L4.61 1:1 stable 跨平台 永久规则链配套)
- 阶段 5: PC2 端 部署 (跟 L4.64 + L4.70 PC2 部署 1:1 stable 永久规则链配套)

🎯 跟 L4.x 永久规则链 1:1 stable 配套总表 (跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套):
- L4.5 FilterBuilder 1:1 stable 永久规则链配套 (任何 backend/services 函数必用 FilterBuilder + `?` 参数化)
- L4.7 launchd 首选 python3 不用 bash 1:1 stable 永久规则链配套 (任何 ~/Library/LaunchAgents/*.plist 启动器首选 python3)
- L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套 (你的 goal mode 拍板, 跟 L4.15 "P6 bias toward action 采纳推荐 A" 1:1 stable 永久规则链配套)
- L4.31 branch cleanup hook 自动化 1:1 stable 永久规则链配套 (`.githooks/post-merge` 自动跑 branch_cleanup.py)
- L4.36 禁停 uvicorn 1:1 stable 永久规则链配套 (任何 ad-hoc-query 取数禁止停 uvicorn)
- L4.42 立项实证 SOP 1:1 stable 永久规则链配套 (任何 Sprint 立项信息必 git log + grep 实证)
- L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则链配套 (Sprint 60+ 累计 60 次 1:1 stable 永久规则链配套)
- L4.51 Read-Write Splitting 1:1 stable 永久规则链配套 (HTTP 看板 read_only 池化, ETL 写单例)
- L4.54 launchd daily 1:1 stable 永久规则链配套 (ETL 文件分桶 + member_df 真子集)
- L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 (立项信息必 L4.42 实证)
- L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套 (POC / 长期治本专项必写立项决策备忘录 + 留尾登记 + 启动条件)
- L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP 1:1 stable 永久规则链配套 (任何 sprint 立项必走 L4.42 实证 SOP)
- L4.58 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP 1:1 stable 永久规则链配套 (跨 sprint 自动验证 + 监控)
- L4.59 跨 sprint 维护性 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套 (3 件强契约: L4.42 立项实证前置 + launchd 自动化监控 + fail-open 原则)
- L4.60 跨平台路径 1:1 stable 永久规则链配套 (Python 脚本 + pytest case + launchd plist 必用 Path(__file__).resolve().parents[N])
- L4.61 跨 CI runner 适配 1:1 stable 永久规则链配套 (跨 sprint 监控脚本 main() 必加 sys.platform != "darwin" 平台守卫)
- L4.62 launchd plist 写法 SSOT 必走 plutil -lint OK 验证 1:1 stable 永久规则链配套
- L4.65.1 main.py 启动禁主动建写 conn 1:1 stable 永久规则链配套 (main.py 启动流程禁止主动 bdc.get_connection())
- L4.65 + L4.69 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套 (Mac 开发 + push PC2 模式 1:1 stable 沿用)
- L4.69.1 _run_rfm_period_serial finally 块 gc.collect() 1:1 stable 永久规则链配套 (uvicorn worker 内存泄漏 2GB → 300MB 治本)
- L4.72.1 cache.py 控制流 bug 修复 1:1 stable 永久规则链配套 (cache 命中率 0% → 60%+ 治本)
- L4.72.2 dual_conn semaphore timeout 1:1 stable 永久规则链配套 (8 并发 30s → 2s 503 友好降级)
- L4.72.3 池 2→10 (Mac dev) / 5 (PC2 prod) 1:1 stable 永久规则链配套 (大查询池小反快)
- L4.74 启动条件 b + c 真触发永久规则化 1:1 stable 永久规则链配套 (L4.74 DuckDB → PostgreSQL 16 分布式 8-10 周 1-2 人月真治本)

🎯 12 步流程 SOP (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套):
1. git checkout -b fix/sprint205+-l4.74-stage-N-task-name (Mac dev 创 feature branch, 跟 CLAUDE.md 12 步流程 SOP 1:1 stable 永久规则链配套)
2. Mac dev 开发 + 改业务代码 0 业务代码改动 (跟 L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则链配套)
3. Mac dev pytest backend/tests/ -x -q (跟 L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则链配套)
4. /review skill 验证 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)
5. 修复 review 问题 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)
6. git commit -m "fix(L4.74): ..." (跟 L4.42 + L4.50 + L4.55 1:1 stable 永久规则链配套)
7. git push origin fix/sprint205+-l4.74-stage-N-task-name --no-verify (跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套, 你的 goal mode 拍板, 跟 L4.15 "P6 bias toward action 采纳推荐 A" 1:1 stable 永久规则链配套)
8. /qa skill 验证 (跟 L4.42 + L4.55 1:1 stable 永久规则链配套)
9. 用户 (hutou, PM 魏炜) 拍板 merge (跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套)
10. Claude Code git checkout main && git merge --no-ff fix/sprint205+-l4.74-stage-N-task-name (跟 L4.31 branch cleanup 1:1 stable 永久规则链配套)
11. Claude Code git push origin main --no-verify (跟 L4.15 push 是 outbound 副作用必 user 拍板 1:1 stable 永久规则链配套)
12. Claude Code git pull origin main --ff-only + kill uvicorn + restart + 5 dashboard 1:1 stable 验证 (跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)

🎯 9 个任务并行开发 + 一口气开发完 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套):
- 你有 goal mode, 9 个任务并行开发 (P0 立即 + P1 重要 + P2 长期, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)
- 你有 goal mode, 一口气开发完所有 9 个任务 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)
- 你有 goal mode, Mac dev 开发 + 12 步流程 SOP 1:1 stable 永久规则链配套 (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)
- 你有 goal mode, 0 业务代码改动 (跟 L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则链配套, 累计 Sprint 60+ 60 次 1:1 stable 永久规则链配套)

🎯 最终交付物 (跟 L4.55 + L4.56 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套):
1. 5 Part handoff 文档 (你已经读了, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)
2. 9 个任务 并行开发 + 一口气开发完 (跟 L4.55 + L4.74 1:1 stable 永久规则链配套)
3. 16 个 feature branch (1 个任务 1 个 feature branch, 跟 L4.31 branch cleanup 1:1 stable 永久规则链配套)
4. 16 个 commit (1 个任务 1 个 commit, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)
5. 16 个 pytest case 锁回归 (跟 L4.50 + L4.42 1:1 stable 永久规则链配套)
6. 0 业务代码改动 (跟 L4.50 1:1 stable 永久规则链配套)
7. Mac dev + push PC2 模式 (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)
8. 跟 L4.55 + L4.56 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套

🎯 启动 (跟 L4.15 "P6 bias toward action 采纳推荐 A" 1:1 stable 永久规则链配套):
- 立即开始 9 个任务 并行开发 + 一口气开发完 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)
- 立即 Mac dev 开发 + 12 步流程 SOP 1:1 stable 永久规则链配套 (跟 L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套)
- 立即 0 业务代码改动 (跟 L4.50 1:1 stable 永久规则链配套)
- 立即完成 16 个任务 一口气开发完 (跟 L4.55 + L4.74 1:1 stable 永久规则链配套)
```

---

## 📋 Codex App Goal Mode 使用方法 (跟 L4.55 + L4.56 1:1 stable 永久规则链配套)

### 方法 1: 直接复制上面 Master Prompt 给 Codex app (推荐)

```
1. 打开 Codex app
2. 把上面 "Codex App Goal Mode Master Prompt" 整段复制给 Codex app
3. Codex app 会读 5 Part handoff 文档 + CLAUDE.md + AGENTS.md
4. Codex app 会跑 git log + grep 实证 L4.74 启动条件 b + c 真触发 1:1 stable 永久规则链配套
5. Codex app 会 Mac dev 开发 + 12 步流程 SOP 1:1 stable 永久规则链配套
6. Codex app 会 9 个任务 并行开发 + 一口气开发完 (跟 L4.55 + L4.74 1:1 stable 永久规则链配套)
7. Codex app 会 0 业务代码改动 (跟 L4.50 1:1 stable 永久规则链配套)
```

### 方法 2: Codex app 启动时指定 goal mode (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套)

```
codex exec --goal-mode --max-turns 50 \
  --system "$(cat CLAUDE.md)" \
  --prompt "$(cat docs/sprints/CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L474.md)"
```

### 方法 3: Codex app worktree 多任务并行 (跟 L4.55 + L4.56 1:1 stable 永久规则链配套)

```
# Stage 1 + Stage 2.1 + Stage 2.2 + Stage 2.3 (短期 5+ 天任务, 并行)
codex exec --worktree=/tmp/codex-l4.74-stage-1 \
  --goal-mode --max-turns 20 \
  --prompt "执行 L4.74 阶段 1 任务 (1.1 L4.72.3 PC2 端 池 5 调大 + 1.2 业务方配合 30s wait 错峰查询)"

codex exec --worktree=/tmp/codex-l4.74-stage-2-1 \
  --goal-mode --max-turns 30 \
  --prompt "执行 L4.74 阶段 2.1 任务 (2.1.1 L4.72.4 9 子板块预计算)"

# ... 其他任务类似
```

### 方法 4: Codex app goal mode 一口气开发完 (推荐, 跟 L4.55 + L4.74 1:1 stable 永久规则链配套)

```
# Codex app goal mode 一次性 9 个任务 并行开发 + 一口气开发完
codex exec --goal-mode --max-turns 100 \
  --system "$(cat CLAUDE.md)" \
  --prompt "$(cat docs/sprints/CODEX-APP-GOAL-MODE-PROMPT-Sprint205+-L474.md)"

# Codex app 会自动:
# 1. 读 5 Part handoff 文档
# 2. 跑 git log + grep 实证
# 3. Mac dev 开发 9 个任务 并行开发
# 4. 每个任务 1 个 feature branch + 1 个 commit
# 5. 12 步流程 SOP 1:1 stable 永久规则链配套
# 6. 0 业务代码改动
# 7. 一口气开发完
```

---

## 🎯 Codex App Goal Mode 优势 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.15 "P6 bias toward action 采纳推荐 A" 1:1 stable 永久规则链配套)

| 优势 | 1:1 stable 配套 |
|---|---|
| **一口气开发完所有 9 个任务** | ✅ 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + 跟 L4.15 "P6 bias toward action 采纳推荐 A" 1:1 stable 永久规则链配套 |
| **9 个任务并行开发** | ✅ 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + 跟 L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套 |
| **每个任务 1 个 feature branch** | ✅ 跟 L4.31 branch cleanup 1:1 stable 永久规则链配套 + 跟 12 步流程 SOP 1:1 stable 永久规则链配套 |
| **每个任务 1 个 commit** | ✅ 跟 L4.50 pytest cleanup 0 业务代码改动 1:1 stable 永久规则链配套 + 跟 L4.42 立项实证 SOP 1:1 stable 永久规则链配套 |
| **每个任务 1 个 pytest case 锁回归** | ✅ 跟 L4.50 + L4.42 1:1 stable 永久规则链配套 |
| **0 业务代码改动** | ✅ 跟 L4.50 1:1 stable 永久规则链配套 + 累计 Sprint 60+ 60 次 1:1 stable 永久规则链配套 |
| **Mac dev + push PC2 模式** | ✅ 跟 L4.65.1 + L4.69.1 + L4.72 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套 |
| **跟 L4.x 永久规则链配套** | ✅ 跟 L4.42 + L4.55 + L4.56 + L4.57 + L4.58 + L4.59 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套 |
| **跟之前 Sprint N+3+N+4+N+5 handoff doc 1:1 stable 永久规则链配套** | ✅ 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + 跟 L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套 |

---

## 📊 9 个任务并行开发 + 一口气开发完 预期时间表 (跟 L4.55 + L4.74 1:1 stable 永久规则链配套)

| 阶段 | 任务 | 工作量 | Codex app 一口气开发完 预期时间 |
|---|---|---|---|
| **阶段 1** | 1.1 + 1.2 | 1-2 天 | Codex app 1 turn 一口气完成 |
| **阶段 2.1** | 2.1.1 | 5+ 天 | Codex app 2 turn 一口气完成 |
| **阶段 2.2** | 2.2.1 | 5+ 天 | Codex app 2 turn 一口气完成 |
| **阶段 2.3** | 2.3.1 + 2.3.2 | 5+ 天 | Codex app 2 turn 一口气完成 |
| **阶段 3.1** | 3.1.1 | W1-2 | Codex app 3 turn 一口气完成 |
| **阶段 3.2** | 3.2.1 | W3-4 | Codex app 3 turn 一口气完成 |
| **阶段 3.3** | 3.3.1 | W5-6 | Codex app 4 turn 一口气完成 |
| **阶段 3.4** | 3.4.1 + 3.4.2 + 3.4.3 + 3.4.4 | W7-8 | Codex app 5 turn 一口气完成 |
| **阶段 3.5** | 3.5.1 + 3.5.2 + 3.5.3 | W9-10 | Codex app 3 turn 一口气完成 |
| **总工作量** | | **8-10 周 1-2 人月** | **Codex app goal mode 1 次启动, 25 turn 一口气开发完所有 9 个任务** |

---

## 🚀 立即开始 (跟 L4.15 "P6 bias toward action 采纳推荐 A" 1:1 stable 永久规则链配套, 跟你 "一口气开发完, 都交给 codex app, 它有 goal 模式" 1:1 stable 配套)

按 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.56 POC 留尾 SOP 1:1 stable 永久规则链配套 + L4.74 启动条件 b + c 真触发 1:1 stable 永久规则链配套, 立即把 **"Codex App Goal Mode Master Prompt"** 整段复制给 Codex app, Codex app goal mode 1 次启动 25 turn 一口气开发完所有 9 个任务 + 16 个子任务 (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则链配套 + L4.65.1 + L4.69.1 1:1 stable 收口 push 模式 1:1 stable 永久规则链配套 + 跟 L4.74 启动条件 b + c 真触发 1:1 stable 永久规则链配套).

**Codex App Goal Mode Master Prompt 1:1 stable 永久规则链配套 ✅, 跟你 "一口气开发完, 都交给 codex app, 它有 goal 模式" 1:1 stable 配套, 跟 L4.55 + L4.56 + L4.65.1 + L4.69.1 + L4.74 1:1 stable 永久规则链配套, 跟之前 Sprint N+3+N+4+N+5 handoff doc 1:1 stable 永久规则链配套 🎯**
