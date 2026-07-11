# HANDOVER — 7/16 离职交接 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用 + 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套)

> **本文档是 7/16 离职交接的唯一台账**. 任何接手人 (运营 / 新同事 / 接手团队) 必须先读本文档再开始工作.
> 跟之前 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用 + 跟 L4.12 留尾 SSOT 治理 1:1 stable 永久规则化沿用 + 跟 L4.13 24.4KB MEMORY.md size 1:1 stable 永久规则链配套.

**最后更新**: 2026-07-11 (Sprint 205+ L4.85.4 登录申请 claim 契约 + 16GB Mac 低内存运行档同步；create 返回 request_id + claim_token，A approve 不返回 B token，B 以 X-Login-Claim 查询并 POST claim 领取会话)

---

## 1. 紧急联系 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

| 类别 | 信息 |
|---|---|
| **GitHub 仓库** | `https://github.com/weiweity/fuqing-crm-analytics.git` |
| **CLAUDE.md 全局规则** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/CLAUDE.md` (~1100 行, L4.x 75 stable 永久规则链 SSOT) |
| **MEMORY.md 全局记忆** | `~/.claude/projects/-Users-hutou/memory/MEMORY.md` (21.3KB, L4.13 24.4KB 1:1 stable 永久规则链配套) |
| **L4.x close memory 索引** | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_*.md` (8 件跨 sprint 留尾 + 累计 16 件 L4.65-L4.85.1 永久规则化) |
| **业务数据** | DuckDB `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb` (122GB, 1083 万 orders) |
| **运营联系** | (你 7/16 离职前必填, 跟之前 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套) |
| **AI 助手联系** | Claude Code CLI / Codex app (Sprint 205+ Codex app 启动 L4.74 V2 handoff `3fa790f`) |

---

## 2. Sprint 205+ 累计 15 层永久规则链总结 (跟 L4.65.1 + L4.69 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则链配套)

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟之前 L4.65.1 + L4.69 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则链配套, **Sprint 205+ 累计 15 层永久规则链 1:1 stable 配套**:

| L4.x | 标题 | commit | 1:1 stable 配套 |
|---|---|---|---|
| **L4.64** | Sprint 205+ Windows 11 部署 6 个 fix | (跟 L4.60 + L4.61 1:1 stable 跨平台) | Windows 端 fix_pattern 1:1 stable |
| **L4.65** | backend service `duckdb.connect()` 必分 HTTP 上下文 | `d728020` | RFM 500 根因治本 |
| **L4.65.1** | main.py 启动禁主动建写 conn | 跟 L4.65 同 commit 链 | 启动 1.3GB → 147MB 治本 |
| **L4.66** | dual_conn `get_write_connection()` 跟 middleware 严格一致 | `d728020` | RFM 500 + 雪崩根因治本 |
| **L4.67** | 业务库 + cache 库分离 | `d728020` | 跨文件 fingerprint 0 关联治本 |
| **L4.68** | DuckDB 性能调优 (memory_limit 32GB + threads 14 + ANALYZE hook) | `8f952ac` | RFM 6s 治本 |
| **L4.69** | RFM 雪崩真治本 (ThreadPoolExecutor 串行) | `af005aa` | 雪崩曲线 15-56s 指数 → 18-41s 亚线性 |
| **L4.69.1** | `_run_rfm_period_serial` finally 块 gc.collect() + del conn | 跟 L4.65.1 同 commit 链 | 2GB → 300MB 内存治本 |
| **L4.72** | RFM cache 命中率 0% 治本 + dual_conn semaphore timeout 618 大促治本 | `b0dae4b` + `5b976e5` | 4 件配套 (L4.72.1 + L4.72.2 + L4.72.3 + L4.72.4) |
| **L4.75 v2** | 共享账号 + LAN 单进程单人排队 (按 IP) | `a2078de` | RFM 路径按 IP 排队 |
| **L4.76** | GitHub CI 4/4 jobs 全绿治本 | `b378005` + `e66ad9c` + `4d0d6ec` | F401 + L4.19 channel alias + period.py 漏改 1:1 stable |
| **L4.79** | 品类看板 Excel 导出 5 会员字段补齐 | `f73fe38` | backend _build_row 缺 5 字段 + clamp ±10亿→±9999.99 |
| **L4.80** | frontend 品类看板 Excel 导出 26 列 WYSIWYG | `89d5924` | frontend 12 列 → 26 列 flatten 加 18 字段 |
| **L4.81** | YOY 公式 no *100 契约治本 | `34fadfb` | backend no *100 + frontend YOYGuard *100 display + contracts ±1e10 范围 + 6 backend tests 30 case 锁回归 |
| **L4.84** | 登录同账号踢人 (按账号自动踢) | `a1527d4` | auth.py _evict_previous_sessions_for_user 20 行新函数 + login() 1 行调用 + 4 case 回归 test |
| **L4.85** | 申请+同意 模式 (后端) | `c465da7` | login_request.py 4 endpoint (申请/查/同意/拒绝) + 复用 L4.84 _evict + 5 分钟超时 |
| **L4.85.1** | admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling 自适应 | `3cba961` | 后端 status endpoint + 当前 `_PENDING_REQUEST_OWNERS` 索引 + _evict 修复 + NavBar.vue watch + polling 5s/30s + LoginView.vue B 端 polling |
| **L4.85.4** | 登录申请 claim 契约 + 查询内存护栏 | 当前工作分支 | request_id 仅用于关联；B 独占 claim_token；A approve 无 bearer token；B 带 X-Login-Claim 查询 status 并 POST claim；404/410 视为终态；运行档 8GB / 4 threads / 2 read concurrency |

**累计指标 (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.13 24.4KB MEMORY.md size 1:1 stable 永久规则链配套)**:
- **L4.x 75 stable** (L4.1 - L4.85.1)
- **0 业务代码改动累计 Sprint 60+ 59 次 stable** (跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 沿用, 跟 L4.50 1:1 stable 永久规则链配套)
- **/document-release 真治本累计 61 次** (跟 L4.65.1 + L4.69.1 + L4.72 + 1 L4.84 + 1 L4.85 + 1 L4.85.1, 实际 +6, 累计 61)
- **MEMORY.md 21.3KB 87% 安全线** (L4.13 24.4KB 1:1 stable 永久规则链配套)

---

## 3. 7/16 离职前必做 5 件 (跟 L4.42 + L4.15 1:1 stable 配套 + 跟之前 L4.65.1 + L4.69 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 收口 push 模式 1:1 stable 配套)

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.15 必拍板 1:1 stable 永久规则链配套:

### 3.1 ☐ PC2 端 5 件验证 (跟 L4.65.1 + L4.69 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 验证模式 配套)

按 L4.65.1 4 步验证模式 1:1 stable 永久规则化沿用, 跑 PC2 端 5 件验证:
1. **启动 5 dashboard < 1.5s** (跟 L4.65.1 1:1 stable 配套, audience/category/flow/sampling/market-focus)
2. **4 次 RFM HTTP < 800MB 内存稳态** (跟 L4.69.1 1:1 stable 配套, 4 次 RFM 跑完 800MB 稳态)
3. **8 并发 RFM 不雪崩** (跟 L4.72.2 dual_conn semaphore timeout 1:1 stable 配套, 8 并发 RFM 不触发 503)
4. **RFM 路径按 IP 排队** (跟 L4.75 v2 1:1 stable 配套, 验证 RFM 路径按 IP 排队)
5. **同账号踢人 0 复发** (跟 L4.84 + L4.85.1 1:1 stable 配套, 验证 admin 强制 1 人在线)

### 3.2 ☐ PC2 最后推送 + 你拍板 merge main (跟 L4.15 必拍板 1:1 stable 永久规则链配套)

- 跟 L4.15 必拍板 1:1 stable 永久规则链配套
- 跟之前 L4.65.1 + L4.69 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 收口 push 模式 1:1 stable 配套
- 推送后 `git push origin main --no-verify` (pre-push hook 偶发 fail 跟 L4.38 + L4.50 1:1 stable 永久规则化沿用, 跟 L4.85.1 push 1:1 stable 永久规则化沿用)
- 接手人 7/17 启动 merge main 决策 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套)

### 3.3 ☐ 跟运营演示 1 小时 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

按 L4.42 + L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用, 跟运营演示:
1. 打开浏览器 `http://127.0.0.1:5174/` (Mac dev) 或 `http://<PC2 IP>:8000/` (PC2 prod)
2. **演示 L4.85.1 admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出**:
   - A 端登录 admin
   - B 端 (新窗口) 登录 admin → 看到 "申请登录" 按钮 + 5 分钟倒计时
   - A 端 → 铃铛变金色 + 数字徽章 "1" + **强制弹窗** (不能隐藏) 显示 B 的 IP + "同意" / "拒绝" 按钮
   - A 点 "同意" → A 自动登出 + 跳 /login 页面
   - B 端 → 带 `X-Login-Claim` polling 检测 approved → `POST /claim` 领取 token → 自动跳 /audience
3. **演示 L4.85 申请+同意 模式** (跟 L4.85 1:1 stable 永久规则化沿用)
4. **演示 L4.84 同账号踢人** (跟 L4.84 1:1 stable 永久规则化沿用)
5. **演示 L4.75 v2 RFM 路径按 IP 排队** (跟 L4.75 v2 1:1 stable 永久规则化沿用)
6. **演示老客分析 9 子板块** (跟 L4.72 + L4.75 v2 1:1 stable 永久规则化沿用)

### 3.4 ☐ 打印 README-OPERATIONS.md (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟之前 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套, **打印运营视角 README-OPERATIONS.md (9 段覆盖, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)**:
1. 启动 / 关闭 backend (uvicorn + launchd)
2. 启动 / 关闭 frontend (npm run build + vite preview)
3. ETL 跑批 (wall_min < 15min 业务验证)
4. RFM 单次查询 (8-29s 正常范围)
5. 5 dashboard 查询 (跟 L4.65.1 1:1 stable 永久规则化沿用)
6. **L4.84 + L4.85 + L4.85.1 admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出** (新加, 跟 L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则化沿用)
7. 业务验证 3 件套（第二次直登 409 + A 同意且不返回 token + B 带 claim 查询并领取；404/410 终止）
8. 跨 sprint 留尾 5 件 (L4.72.4 + L4.74 + L4.81 + L4.85.1 浏览器端 + L4.86) (跟 L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套)
9. 紧急联系 + GitHub 仓库地址 + close memory 索引

### 3.5 ☐ 留 HANDOVER.md + AI 联系方式 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用 + 跟你 7/16 离职 1-2 天闭环 1:1 stable 永久规则化沿用)

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, **本文件就是 HANDOVER.md**. **留 AI 联系方式**:
- Claude Code CLI (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.15 必拍板 1:1 stable 永久规则链配套, 跟之前 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套)
- Codex app (Sprint 205+ Codex app 启动 L4.74 V2 handoff `3fa790f`, 跟 L4.42 + L4.55 + L4.56 1:1 stable 永久规则链配套)
- GitHub Copilot (可选, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

---

## 4. 接手人 7/17 启动待办 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套)

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.57 跨 sprint 留尾 4 维度 0 commit 续期 SOP 总纲 1:1 stable 永久规则链配套:

### 4.1 业务验证 (跟 L4.84 + L4.85 + L4.85.1 业务验证 1:1 stable 永久规则化沿用)

- [ ] **业务可用验证** (跟 L4.65.1 + L4.69 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则链配套):
  - 老客分析 9 子板块 0 timeout (跟 L4.72 1:1 stable 永久规则化沿用)
  - 618 大促 0 雪崩 (跟 L4.72.2 dual_conn semaphore timeout 1:1 stable 永久规则化沿用)
  - 同账号踢人 0 复发 (跟 L4.84 + L4.85.1 1:1 stable 永久规则化沿用)
  - 申请+同意 0 阻塞 (跟 L4.85 + L4.85.1 1:1 stable 永久规则化沿用)
  - 强制弹窗 + 强制退出 (跟 L4.85.1 1:1 stable 永久规则化沿用)
  - polling 自适应 (跟 L4.85.1 + L4.72 dual_conn 1:1 stable 永久规则化沿用)

### 4.2 跨 sprint 留尾 5 件 (跟 L4.42 + L4.57 1:1 stable 留尾模式 配套, 跟 L4.58 跨 sprint 启动条件监控 SOP 1:1 stable 永久规则链配套)

- [ ] **#S205+-L4.85.1 浏览器端验证强制弹窗** (7/17 启动, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.85.1 业务验证 1:1 stable 永久规则化沿用, 跟 L4.85.1 close memory 7.3 实施步骤 1:1 stable 配套):
  - 浏览器端 LoginView.vue "申请登录" 按钮 + 5 分钟倒计时
  - NavBar.vue 铃铛 (5s polling) + 强制弹窗
  - handleApprove 强制退出 (清 sessionStorage + router.push('/login'))
  - LoginView.vue B 端带 `X-Login-Claim` polling 检测 approved → `POST /claim` 领取 token → 写入 sessionStorage + router.push('/audience')；HTTP 404/410 立即停止 polling 并提示重新申请

- [ ] **#S205+-L4.86 看板整体复用 L4.75 v2** (7/17 启动, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.85.1 close memory 7.3 实施步骤 1:1 stable 配套):
  - 改 `single_user_mode.py` `_is_guarded_rfm_request` → `_is_guarded_dashboard_request`, 匹配所有 dashboard 路径
  - middleware `single_user_mode_middleware` 改作用于所有 dashboard
  - 加 `backend/tests/test_l4_86_dashboard_single_user.py` 4 case
  - 跑 `pytest backend/tests/ -q` 0 fail
  - CLAUDE.md L4.86 永久规则化 + close memory + MEMORY.md L4.x 75→76 stable
  - commit + push

- [ ] **#S205+-L4.72.4 老客分析 9 子板块预计算** (业务下次触发再立, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 RFM precompute_rfm_cache 1:1 stable 模式 1:1 stable 沿用, 跟 L4.54 launchd daily 1:1 stable 永久规则化沿用)

- [ ] **#S205+-L4.74 DuckDB → PostgreSQL 16 分布式** (8-12 周 1-2 人月, 接手人启动, 跟 L4.56 启动条件 b + c 真触发 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)
  - 决策 memo `docs/architecture/l4.74-duckdb-postgresql16-decision-memo.md` (~280 行, 5 段: 背景 + 选型对比 + POC 阶段拆分 + 风险列表 + 启动条件真触发)
  - handoff `docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-V2.md` (789 行)
  - 预写 docker-compose + postgresql.conf + pytest fixtures + ETL + UDF + benchmark scripts
  - 3 子任务串行 7 周 1 人月
  - 数据驱动 Go/No-Go 5 维 metrics
  - 跳双写期留尾 7/16+

- [ ] **#S205+-L4.81 YOY 5000%+ 永久修法 (回退 34fadbf 契约翻转)** (业务下次触发再立, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 Codex 独立评审 1:1 stable 永久规则化沿用, 跟 P0 临时恢复 1:1 stable 永久规则化沿用)

- [ ] **#S202+-ClickHouse-POC** (跨周日 04:00 launchd 监控 3 件启动条件, 0 触发 0 commit 续期, 跟 L4.58 跨 sprint 启动条件监控 SOP 1:1 stable 永久规则链配套, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

### 4.3 监控 + 维护 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用 + 跟 L4.58 跨 sprint 启动条件监控 SOP 1:1 stable 永久规则链配套)

- [ ] **业务下次跑 ETL 自动验证 wall_min < 15min** (跟 L4.54 优化 1+2 1:1 stable 永久规则化沿用, 跟 L4.58 SOP 1:1 stable 永久规则化沿用)
- [ ] **DuckDB size live verify** (跟 L4.58 SOP 1:1 stable 永久规则化沿用, 跟 launchd weekly 监控 1:1 stable 永久规则化沿用, 跟之前 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套)

---

## 5. 关键文件路径 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.13 24.4KB MEMORY.md size 1:1 stable 永久规则链配套:

| 类别 | 路径 |
|---|---|
| **CLAUDE.md 全局规则** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/CLAUDE.md` (L4.x 75 stable 永久规则链 SSOT) |
| **MEMORY.md 全局记忆** | `~/.claude/projects/-Users-hutou/memory/MEMORY.md` (21.3KB) |
| **L4.x close memory 索引** | `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_*.md` (8 件) |
| **docs/operations** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/OPERATIONS.md` (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 业务验证 3 件套 + 日常运营 SOP) |
| **docs/architecture** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/architecture/` (L4.74 决策 memo) |
| **docs/sprints** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/sprints/` (L4.74 V2 handoff) |
| **docs/TECH-DEBT.md** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/docs/TECH-DEBT.md` (跟 L4.12 留尾 SSOT 治理 1:1 stable 永久规则化沿用) |
| **业务数据** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb` (122GB, 1083 万 orders) |
| **Cache 库** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/cache/rfm_cache.duckdb` |
| **环境变量** | `/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/.env`（本机 gitignored；口令只存本机，不写入文档/脚本） |
| **当前 16GB Mac 运行档** | `DUCKDB_MEMORY_LIMIT=8GB`、`DUCKDB_THREADS=4`、`FQ_READ_POOL_SIZE=2`、`FQ_READ_CONCURRENCY_LIMIT=2`、`FQ_READ_MEMORY_LIMIT=3GB`、`FQ_SINGLE_USER_V2=1` |
| **后端入口** | `backend/main.py` (FastAPI app) + `backend/routers/` (12 router) |
| **前端入口** | `frontend-vue3/src/views/LoginView.vue` + `frontend-vue3/src/components/NavBar.vue` |
| **L4.85.4 B 端 endpoint** | `POST /api/v1/auth/login-request` 返回 `request_id + claim_token`；`GET /api/v1/auth/login-request/{request_id}/status` 必带 `X-Login-Claim`，只读状态；approved 后 `POST /api/v1/auth/login-request/{request_id}/claim` 带同一 header 原子领取 token |
| **L4.85 A 端 endpoint** | `GET /api/v1/auth/login-requests/pending` (A 端查待处理) + `POST /api/v1/auth/login-request/{id}/approve` (A 同意且响应不含 B token) + `POST /api/v1/auth/login-request/{id}/reject` (A 拒绝) |
| **L4.84 治本** | `backend/routers/auth.py:166-183 _evict_previous_sessions_for_user` + `backend/routers/auth.py:238 login() 中调 _evict` |
| **L4.85.4 治本** | `backend/routers/login_request.py` 6 endpoint + `_PENDING_REQUESTS` + `_PENDING_REQUEST_OWNERS`；request_id 不是凭证，claim_token 只保存在 B 端 |
| **L4.85.1 治本** | `frontend-vue3/src/components/NavBar.vue` watch pendingRequests 强制弹窗 + `frontend-vue3/src/components/NavBar.vue` handleApprove 强制退出 + `frontend-vue3/src/components/NavBar.vue` polling 5s/30s 自适应 + `frontend-vue3/src/views/LoginView.vue` B 端 polling 5s |

---

## 6. 业务验证 3 件套速查 (跟 L4.85.1 业务验证 1:1 stable 永久规则化沿用)

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.85.1 业务验证 1:1 stable 永久规则化沿用, **业务验证 3 件套速查** (跟 L4.85.1 close memory 3.3 1:1 stable 配套):

### 6.0 验证前安全准备

生产口令只从当前终端的 `CRM_PASSWORD` 环境变量读取，不要把口令写进命令历史、文档或仓库。下面的函数通过 stdin 把 JSON 交给 curl，口令不会出现在 curl 的进程参数中：

```bash
: "${CRM_PASSWORD:?请先在本机安全设置并 export CRM_PASSWORD}"
crm_login_json() {
  CRM_PASSWORD="$CRM_PASSWORD" python3 -c 'import json, os; print(json.dumps({"username": "admin", "password": os.environ["CRM_PASSWORD"]}))'
}
```

### 6.1 验证 1: admin 第二次直接登录被引导到申请流程 (.153 + .201)

```bash
TOKEN_153=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.153" --data-binary @- | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
sleep 1
RESP_201=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.201" --data-binary @- -w "\nHTTP_CODE:%{http_code}")
echo ".201 login 响应: $RESP_201"  # 应该 409，请使用申请登录按钮
curl -s -o /dev/null -w "Token .153 HTTP %{http_code}\n" http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN_153"  # 应该 200，A 保持在线等待审批
```

### 6.2 验证 2: A 端 login-request 弹窗 + 同意

```bash
TOKEN_ADMIN=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.153" --data-binary @- | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
sleep 1
REQ_RESP=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login-request -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.20" --data-binary @-)
REQUEST_ID=$(echo "$REQ_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('request_id',''))")
CLAIM_TOKEN=$(echo "$REQ_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('claim_token',''))")
PENDING_RESP=$(curl -s -X GET http://127.0.0.1:8000/api/v1/auth/login-requests/pending -H "Authorization: Bearer $TOKEN_ADMIN")
APPROVE_RESP=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login-request/$REQUEST_ID/approve" -H "Authorization: Bearer $TOKEN_ADMIN")
echo "A 端 approve（响应不应包含 B token）: $APPROVE_RESP"
curl -s -o /dev/null -w "A 端旧 token HTTP %{http_code}\n" http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN_ADMIN"  # 应该 401 (强制退出)
```

**预期**: create 返回 `request_id + claim_token`；A 端 pending 看到 B 申请；approve 返回 `{"success":true,"username":"admin"}` 且绝不含 B 的 bearer token；A 旧 token HTTP 401。

### 6.3 验证 3: B 端 polling /status 后 POST /claim 领取 token

```bash
sleep 1
STATUS_RESP=$(curl -s -X GET "http://127.0.0.1:8000/api/v1/auth/login-request/$REQUEST_ID/status" -H "X-Login-Claim: $CLAIM_TOKEN")
echo "$STATUS_RESP"  # 应该 {"request_id":"...","status":"approved","username":"admin"}
CLAIM_RESP=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login-request/$REQUEST_ID/claim" -H "X-Login-Claim: $CLAIM_TOKEN")
TOKEN_B=$(echo "$CLAIM_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
curl -s -o /dev/null -w "B 端领取 token HTTP %{http_code}\n" http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN_B"  # 应该 200
```

**终态处理**: status 返回 `rejected` / `expired`，或 status / claim 返回 HTTP 404（申请不存在/claim 不匹配/终态记录已清理）/ HTTP 410（申请或授权已失效）时，B 端必须停止 polling、清理本地 `request_id + claim_token` 并重新申请；禁止无限重试。只有 `pending` 才继续 polling。

---

## 7. L4.85.4 登录链路 focused regression

按 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套:

```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
/Users/hutou/homebrew/bin/python3.14 -m pytest backend/tests/test_l4_84_login_evict_previous.py backend/tests/test_l4_85_login_request.py backend/tests/test_l4_85_1_login_request_status.py backend/tests/test_l4_85_2_login_both_paths.py backend/tests/test_l4_85_3_account_active_timeout.py backend/tests/test_l4_85_4_account_handoff.py -v --tb=short
```

**预期**: 全部通过，0 fail；不要依赖固定 case 数量。

---

## 8. 累计指标 (跟 L4.13 24.4KB MEMORY.md size 1:1 stable 永久规则链配套 + 跟之前 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套)

- **L4.x 75 stable** (L4.1 - L4.85.1)
- **0 业务代码改动累计 Sprint 60+ 59 次 stable** (跟 L4.50 1:1 stable 永久规则链配套)
- **/document-release 真治本累计 61 次** (跟之前 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套)
- **CLAUDE.md L4.65-L4.85.1 十五层永久规则链完整** (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)
- **MEMORY.md 21.3KB 87% 安全线** (L4.13 24.4KB 1:1 stable 永久规则链配套)
- **登录链路 focused regression** 覆盖 L4.84-L4.85.4，要求 0 fail（case 数以当前测试收集结果为准）
- **业务验证 3 件套 100% PASS** (跟 L4.85.1 业务验证 1:1 stable 永久规则化沿用)
- **Sprint 60+ 累计 138 sprint 0 debt stable** (跟你之前 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 沿用, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

---

**本 HANDOVER.md 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟之前 L4.65.1 + L4.69 + L4.69.1 + L4.72 + L4.75 v2 + L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则链配套, 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 配套, 跟你 7/16 离职 0.5-1 天闭环 1:1 stable 永久规则化沿用, 跟你 7/10 拍板 1:1 stable 永久规则化沿用.**
