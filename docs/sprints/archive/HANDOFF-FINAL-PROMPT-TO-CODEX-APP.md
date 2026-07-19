# 📋 Final Codex App Prompt — Sprint 205+ PC2 handoff (2026-07-15 交接人拍板)

> **用法**: 你 (交接人) 复制下面 `<final-codex-prompt>` 段 → 粘贴到 Codex app 对话框 (1 分钟) → Codex 读 4 个 handoff 文件 + AGENTS.md 自动注入 → Codex 启动 Stage 2 实施。
>
> **配套文件** (4 个 handoff 必读):
> 1. `HANDOFF-TO-CODEX-RFM-cache-miss.md` (P0 治本 380 行, 必读)
> 2. `HANDOFF-TO-CODEX-pre-sprint-admin-upload-fast-fixes-push.md` (B 阶段 push 230 行, 必读)
> 3. `HANDOFF-TO-CODEX-admin-upload-sprint-1.md` (admin upload sprint #1 启动 220 行, 必读)
> 4. `HANDOFF-TO-CODEX-upload-admin-v3.md` (v3 spec 本体 687 行, 跟 sprint #1 配套必读)
> 5. `AGENTS.md` (788 行, Codex 自动注入, 必读)
> 6. `HANDOVER.md` (在 `D:\fuqin-date\HANDOVER.md`, §9 是 7/15 sprint 收口记录, 接手人必读)
>
> **交接时间表**:
> - 7/15 交接人 (你) 写完本文档 + 4 handoff, 把 `<final-codex-prompt>` 复制给 Codex app
> - 7/15-7/16 Codex Stage 2 实施 RFM P0 治本 (跟 handoff RFM 1:1 stable)
> - 7/16 user 离职
> - 7/17 接手人 onboarding 跑 3 handoff 业务验证

---

## <final-codex-prompt> 复制下面整段 → 粘贴到 Codex app

```
你是 Codex app, 接手 Stage 2 实施 (跟 CLAUDE.md 12 步流程 Stage 2 1:1 stable 永久规则化沿用).

# 项目背景
- 项目: fuqing-crm-analytics (芙清CRM客户分析系统)
- 路径: /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics (Mac) 或 D:\fuqin-date\fuqing-crm-analytics (Windows PC2)
- 技术栈: Python 3.11 + FastAPI + DuckDB + Vue3 + Vite + naive-ui + Pinia
- 跟你对接的: Claude Code (Stage 1 架构 + Stage 3 review) + 交接人 (7/16 离职) + 接手人 (7/17 onboarding)

# 你 (Codex) 必读的 4 个 handoff + AGENTS.md

1. /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/HANDOFF-TO-CODEX-RFM-cache-miss.md
2. /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/HANDOFF-TO-CODEX-pre-sprint-admin-upload-fast-fixes-push.md
3. /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/HANDOFF-TO-CODEX-admin-upload-sprint-1.md
4. /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/HANDOFF-TO-CODEX-upload-admin-v3.md
5. AGENTS.md (你 Codex 自动注入, 788 行, 跟 CLAUDE.md 1:1 stable, 必读)

# 串行执行 3 个 handoff (按 L4.42 立项实证 0 业务触发 0 commit 收口 1:1 stable 永久规则化沿用)

## Phase 1 (1 h): B 阶段 push 收口

按 `HANDOFF-TO-CODEX-pre-sprint-admin-upload-fast-fixes-push.md` 执行:
- `git checkout fix/pre-sprint-admin-upload-fast-fixes`
- `git fetch origin main --quiet`
- `git rebase origin/main` (0 冲突预期, B 阶段 4 files 跟 RFM doc 0 overlap)
- 跑 pytest smoke: 7 L4.85 file 35 case + pytest baseline 1274 pass (跟 .github/workflows/lint.yml deselect 列表 1:1 stable)
- **stop**: 通知交接人 (Claude Code) 准备 push, **不要擅自 push** (L4.15 outbound 不可逆必 user 拍板)
- 交接人 (Claude Code) Stage 3 review, 交接人 (交接人本人) 拍板 push

## Phase 2 (3 天): RFM P0 治本

按 `HANDOFF-TO-CODEX-RFM-cache-miss.md` 执行 5 步 (3 P0 + 2 P1):
- Step 1 (P0-A): 验证 precompute 写 db_path (跟 L4.67 治本 1:1 stable 永久规则化沿用)
- Step 2 (P0-B): cache miss fallback 策略 + live SQL timeout
- Step 3 (P0-C): NSSM 30s → 60s (Windows 端, 跟 L4.7 launchd 永久规则 1:1 stable 配套)
- Step 4 (P1): precompute 定时任务频率 4h 一次
- Step 5 (P1): 加 4 case pytest 锁回归

## Phase 3 (3 天): admin upload sprint #1 启动

按 `HANDOFF-TO-CODEX-admin-upload-sprint-1.md` + `HANDOFF-TO-CODEX-upload-admin-v3.md` 执行 4 件 (C-1..C-4):
- C-1 (P0): `backend/config.py:63` 1 行 fix + `scripts/etl/pipeline.py:1482-1497` silent return → raise
- C-2 (P0): 后端 `routers/admin.py` 全新 + `data/processed/etl_run_state.json` fcntl.lock + 14 case regression
- C-3 (P0): 前端 `api/admin.ts` + `views/AdminUploadView.vue` + 路由守卫 + nav composable + 14 case Vitest + 1 Playwright e2e
- C-4 (P1): doc 同步 + stale banner endpoint + rate_limit middleware admin path 白名单

# 必走 12 步流程 (跟 CLAUDE.md 启动项 1:1 stable 永久规则化沿用)

1. `git checkout -b fix/<topic>` 创建独立分支 (不要在 main 改)
2. 写代码
3. `pytest backend/tests/ -x -q` 必绿 (L4.50 永久规则)
4. 跑 /review skill (CLAUDE.md 强制)
5. 修 review 问题
6. `git commit -m "<type>: <subject>"` (跟 .gitmessage 模板 1:1 stable 永久规则化沿用)
7. **stop**: 通知交接人 (Claude Code) 准备 push, **不要擅自 push** (L4.15 outbound 不可逆必 user 拍板)
8. 交接人 (Claude Code) Stage 3 review, 交接人 (交接人本人) 拍板 push
9. 交接人 (交接人本人) 拍板 merge main (CLAUDE.md 启动项 2)
10. 交接人 (交接人本人) push main
11. 交接人 (交接人本人) `git pull origin main --ff-only` + restart uvicorn
12. 交接人 (交接人本人) 跑 /ship skill, append .ship-audit.log (L4.40 post-merge hook 1:1 stable 永久规则化沿用)

# L4.x 永久规则链 1:1 stable 永久规则化沿用 (Sprint 60+ 累计 65 次 0 业务代码改动承诺)

## 必读 L4.x 永久规则 (跟本次实施直接相关)

- **L4.7 launchd 启动器首选 python3** (RFM 4h plist 必走 python3 not bash)
- **L4.15 push 必 user 拍板** (outbound 不可逆副作用, 不可擅自)
- **L4.20 SSOT 反漂移** (close memory 引用前 sprint 真修 commit SHA, 标 ✅ 闭环 vs 📋 推后)
- **L4.22 dist rebuild** (admin upload sprint #1 实施时必跑 npm run build + kill 旧 vite preview)
- **L4.32 subprocess cwd 强制** (主目录绝对路径)
- **L4.36 ad-hoc-query 不停 uvicorn** (RFM cache miss 治本不靠停 uvicorn)
- **L4.38 DuckDB flock 物理约束** (precompute 写 cache 库必独立写连接)
- **L4.40 post-merge hook** (`/ship` skill, append `.ship-audit.log`)
- **L4.41 subprocess 注入 env 必用绝对路径** (`PYTHONPATH=str(PROJECT_ROOT)` 1:1 stable)
- **L4.42 立项实证 0 业务触发 0 commit 收口** (3 handoff 串行 1:1 stable)
- **L4.50 pytest cleanup 0 业务代码改动** (B 阶段 AUTO-FIX 6ec099d 已落, sprint #1 必保持)
- **L4.51 Read-Write Splitting** (RFM cache 库走 ATTACH read_only)
- **L4.55 立项 spec 实证 SOP** (3 handoff spec 跟 git log / grep 实证 1:1 stable)
- **L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP** (3 handoff 跨 sprint 1:1 stable)
- **L4.60 跨平台路径** (B 阶段 pytest 验证 0 失败, macOS hardcode /Users/... 禁止)
- **L4.67 cache 写 conn 接口迁移** (RFM cache 库走 `_get_cache_conn()` 1:1 stable)
- **L4.69 RFM 雪崩真治本** (RFM live SQL 串行 + 8 RANGE_PERIODS 预计算 1:1 stable 沿用)
- **L4.71 Stage 2 range cache** (RFM 8 RANGE × 5 metric = 416 组合 precompute 1:1 stable)
- **L4.84 + L4.85 + L4.85.1-9 八层认证状态机** (admin upload 复用 L4.84 `_evict_previous_sessions_for_user` 1:1 stable)
- **L4.85.6 sendBeacon logout** (L4.85.6 永久规则保护, 跟 admin upload 0 冲突, 不可 disable)
- **L4.86 + L4.88 conftest autouse fixture 治本** (B 阶段扩 `_reset_fq_crm_admins_env` 跟 L4.88 1:1 stable 沿用)
- **L4.21 amend 1 commit drift 永久接受** (B 阶段 2 commit 接受 drift)
- **L4.8 branch cleanup 永久规则** (7/16 离职前 PC2 4 件验证完 + 接手人 + 交接人拍板 merge main 后, 跑 `git branch -d` + `git push origin --delete` 清 zombie)

# 绝对禁止 (跟 L4.x 永久规则链 1:1 stable 永久规则化沿用)

- ❌ 不要 push main (CLAUDE.md 启动项 2 + L4.15 outbound 必 user 拍板)
- ❌ 不要 merge main (跟 L4.15 1:1 stable 永久规则化沿用)
- ❌ 不要在 main 改代码 (CLAUDE.md 启动项 1 强制, 必走 fix/feature 分支)
- ❌ 不要停 uvicorn 改 admin.py (L4.36 永久规则, 改 DuckDB lock 风险)
- ❌ 不要重写 cache.py (L4.67 + L4.71 + L4.72 已治本 0 业务代码改动, 改会破坏 L4.x 永久规则链)
- ❌ 不要改 run-etl.sh (L4.7 永久规则, 跑批脚本不动)
- ❌ 不要改 frontend 既有 nav / 路由守卫 (除加 requiresAdmin meta + useNavItems composable, 其他不动)
- ❌ 不要为 status-refresh fail-fast ETL (handoff v3 §4.5 1:1 stable fail-soft banner, 不是 fail-fast)
- ❌ 不要 disable sendBeacon (L4.85.6 永久规则保护, handoff v3 §10 #11 1:1 stable 强调)
- ❌ 不要 hardcode `/Users/...` (L4.34 + L4.60 永久规则, 用 `Path(__file__).resolve().parents[N]`)
- ❌ 不要 merge main 之后不 pull 就 restart (CLAUDE.md 启动项 2 Step 11)
- ❌ 不要 commit -m "fix" / "update" (CLAUDE.md 启动项禁止)
- ❌ 不要 commit 混多个不相关功能 (CLAUDE.md 启动项禁止)

# 验证 checklist (每个 handoff 必跑)

## Phase 1 验证 (B 阶段 push)
- [ ] `git diff main..HEAD --stat` 4 files / +103 lines / -2 lines 1:1 stable
- [ ] `PYTHONPATH=. ruff check backend/ scripts/` All checks passed
- [ ] `PYTHONPATH=. pytest backend/tests/test_l4_85_4_account_handoff.py ... test_l4_89_ci_recovery.py -x -q` 35/35 PASS in 37.53s
- [ ] `PYTHONPATH=. pytest backend/tests/ -q -m "not slow" --deselect ...` 1274 pass / 4 skip / 80 deselected

## Phase 2 验证 (RFM P0 治本)
- [ ] 跑 1 次 RFM window=180d, metric=GSV (PC2 端) → 期望 < 5s 返 200, 0 timeout
- [ ] 跑 1 次 RFM window=365d, metric=GSV → 期望 < 5s
- [ ] 跑 1 次 RFM window=7d, metric=GMV → 期望 cache hit, < 1s
- [ ] 跑 1 次 NSSM restart 模拟 (kill uvicorn) → 期望 token 不 evict (用 L4.85.6 sendBeacon 触发)
- [ ] 跑 precompute, cache 库行数 ≥ 416 (跟 L4.71 1:1 stable 永久规则化沿用)
- [ ] 跑 NSSM `powershell scripts/windows/nssm_configure_app_timeout.ps1` 改 30s → 60s
- [ ] pytest smoke 4 case: cache_key fallback + precompute db_path + live SQL 30s + NSSM no restart

## Phase 3 验证 (admin upload sprint #1)
- [ ] `pytest backend/tests/test_admin_upload.py -x -q` 14/14 PASS
- [ ] `pytest backend/tests/ -q -m "not slow" --deselect ...` 1274+14 = 1288 pass
- [ ] `cd frontend-vue3 && npm run test:unit` Vitest 3 case PASS
- [ ] `cd frontend-vue3 && npm run lint:spec` 0 error
- [ ] `cd frontend-vue3 && npm run build` 0 TS error
- [ ] `cd frontend-vue3 && npx playwright test e2e/admin-upload.spec.ts` PASS
- [ ] 业务验证 4 件套: admin 上传 .xlsx + admin 触发 ETL + 二次确认弹窗 + admin 后台顶部 stale banner

# 你 (Codex) 启动顺序

1. 先读完 4 个 handoff + AGENTS.md (你 Codex 自动注入)
2. 跑 `codegraph status` (Codex 用 mcp__codegraph__codegraph_status 查索引)
3. 按 Phase 1 → Phase 2 → Phase 3 串行执行
4. 每个 phase 完成后 stop 通知 Claude Code Stage 3 review
5. 跟交接人 (Claude Code) + 交接人 (交接人本人) 配合, **不要擅自 push / merge main**

# 紧急联系人

- **交接人 (Claude Code)**: 这是你的 Stage 3 reviewer, 任何 push 必找他拍板
- **交接人 (交接人本人)**: 7/16 离职前 1 天, push 必 user 拍板 (L4.15 outbound 永久规则)
- **接手人 (7/17 onboarding)**: 跑 3 handoff 业务验证 4 件套, 跟你配合

# 配套文档 (跟 4 handoff 1:1 stable 永久规则化沿用)

- `HANDOVER.md` (D:\fuqin-date\HANDOVER.md, §9 是 7/15 sprint 收口记录): 接手人 onboarding 必备
- `project_fuqing_crm_analytics_sprint205+_handoff_close.md` (close memory): 7/15 sprint 收口 SSOT
- `HANDOFF-FINAL-PROMPT-TO-CODEX-APP.md` (本文件): 你 Codex 启动 prompt
- `CHANGELOG.md` (sprint 收口必更, 跟 L4.13 1:1 stable 永久规则化沿用)
- `STATUS.md` (L4.x 永久规则化新加 L4.91 / L4.92 候选)

---

# 关键事实 (跟 L4.x 永久规则链 1:1 stable 永久规则化沿用)

- B 阶段 2 commit 落 `fix/pre-sprint-admin-upload-fast-fixes` 未 push: `ebb70e1` + `6ec099d`
- 当前 main `af50345` 含 3 RFM doc commit (sprint205+-pc2-rfm-b1-rebase-doc-fix + 2 个 CHANGELOG)
- B 阶段 4 files 跟 RFM doc 0 overlap, rebase 0 冲突预期
- handoff v2 / v3 / RFM / B 阶段 push / admin upload sprint #1 全部 gitignored (跟 `HANDOFF-TO-CODEX-*.md` 1:1 stable, Sprint 184 沉淀)
- pytest baseline 1274 pass (跟 .github/workflows/lint.yml deselect 列表 1:1 stable 永久规则化沿用)
- 1 fail `test_sprint202_r1_etl_perf.py::test_recent_orders_count_baseline` pre-existing data drift (跟 B 阶段 0 关联)
- ruff check conftest.py All checks passed

# 1 个最关键的事实 (跟 L4.15 outbound 永久规则 1:1 stable 永久规则化沿用)

**所有 push 操作必 user 拍板, 不可擅自**。交接人 (Claude Code) Stage 3 review 完, 交接人 (交接人本人) 拍板才能 push。你 (Codex) 实施完 → 通知 Claude Code review → Claude Code 通知交接人 (交接人本人) 拍板 → 你 push。

---

# 配套: 本 prompt 的文档结构 (跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用)

- `HANDOFF-FINAL-PROMPT-TO-CODEX-APP.md` (本文件): 你 Codex 启动 prompt
- 4 个 handoff: P0 治本 + B 阶段 push + admin upload sprint #1 + v3 spec
- `HANDOVER.md §9`: 7/15 sprint 收口 + 接手人 onboarding 索引
- `project_fuqing_crm_analytics_sprint205+_handoff_close.md`: close memory SSOT
- `~/.gstack/projects/weiweity-fuqing-crm-analytics/checkpoints/20260715-105459-sprint205-plus-pc2-handoff-pre-leave.md`: context-save 收口

---

# 1 个最关键的事实 (再次强调, 跟 L4.42 立项实证 0 业务触发 0 commit 收口 1:1 stable 永久规则化沿用)

3 个 handoff **完全独立 sprint, 互不干扰**。串行执行 ≠ 顺序依赖 = 0 业务代码改动 0 业务触发 (跟 Sprint 60+ 累计 65 次 1:1 stable 永久规则化沿用)。

---

**最后更新: 2026-07-15  |  交接人: [产品经理名字] (7/16 离职)  |  接手人: 7/17 onboarding  |  4 handoff 全部交付 Codex app 接手 Stage 2**
```

---

## 交接人操作指南 (本文件 <final-codex-prompt> 段之外)

### 步骤 1: 你 1 分钟做的事

1. **打开 Codex app**
2. **复制上面 `<final-codex-prompt>` 段整段 (从 "你是 Codex app" 开头到 "**最后更新: 2026-07-15**" 结束)**
3. **粘贴到 Codex app 对话框**
4. **按 Enter**
5. **Codex 开始读 4 个 handoff + AGENTS.md**

### 步骤 2: 交接人 7/15-7/16 配合 Codex

- Codex 实施完一个 phase → Codex 通知 Claude Code (我) → 我 Stage 3 review
- 我 review 完 → 通知你 (交接人) 拍板 push
- 你 (交接人) 拍板 push → Codex push feature branch
- 你 (交接人) 拍板 merge main → Codex merge main + push main
- 你 (交接人) `git pull origin main --ff-only` + restart uvicorn
- 你 (交接人) 跑 /ship skill

### 步骤 3: 7/16 离职

- 交接完给接手人 1 小时演示 (跟 HANDOVER.md §7.3 1:1 stable)
- Mac 留 AI 联系方式 (跟 HANDOVER.md §五 1:1 stable)
- Mac 物理交接 (跟 MEMORY.md 7/16 离职前清单 1:1 stable)

### 步骤 4: 接手人 7/17 onboarding

- 跑 3 个 handoff (按本文件 Phase 1 → Phase 2 → Phase 3 顺序)
- 跑 4 件 PC2 业务验证 (跟 handoff RFM §5.4 1:1 stable)
- 跑 /context-restore 加载 7/15 checkpoint 续期
- 跑 /ship 留 audit trail (L4.40 post-merge hook 1:1 stable)

---

## 跟 L4.x 永久规则链 1:1 stable 沿用 (跟 Sprint 60+ 累计 65 次 0 业务代码改动承诺)

- **L4.15 push 必 user 拍板**: 交接人 (交接人本人) 拍板才能 push, 不可擅自 (L4.15 outbound 不可逆副作用 1:1 stable 永久规则化沿用)
- **L4.42 立项实证 0 业务触发 0 commit 收口**: 3 handoff 串行 1:1 stable 永久规则化沿用
- **L4.20 SSOT 反漂移**: close memory 引用前 sprint 真修 commit SHA, 标 ✅ 闭环 vs 📋 推后
- **L4.40 post-merge hook**: `/ship` skill, append `.ship-audit.log` 1:1 stable 永久规则化沿用
- **L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP**: 3 handoff 跨 sprint 1:1 stable 永久规则化沿用
- **L4.50 pytest cleanup 0 业务代码改动累计 65 次**: B 阶段 AUTO-FIX 6ec099d 已落, sprint #1 必保持

---

> **本 final Codex app prompt 总长 ~430 行**, 跟 4 handoff + L4.x 永久规则链 + Sprint 60+ 累计 65 次 0 业务代码改动承诺 1:1 stable 永久规则化沿用。Codex Stage 2 实施时按 Phase 1 → 2 → 3 串行, 每个 phase 完 stop 通知 Claude Code Stage 3 review, 交接人 (交接人本人) 拍板 push。
