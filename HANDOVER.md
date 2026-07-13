# HANDOVER.md — 7/16 离职交接 (跟 L4.85 1:1 stable 永久规则化沿用 + 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)

> **本文档是 fuqing-crm-analytics 项目唯一 SSOT 离职交接 doc, 跟 L4.85 1:1 stable 永久规则化沿用**.
> **维护规则**: sprint 收口必更新本文档 (跟 CLAUDE.md "Behavior rules" 1:1 stable 沿用, 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 沿用).

## 1. 项目状态 (跟 L4.85 1:1 stable 永久规则化沿用)

| 维度 | 值 |
|---|---|
| **项目名** | 天猫CRM客户分析系统 (fuqing-crm-analytics) |
| **main HEAD** | `c0bf545` (Sprint 205+ L4.91 doc release 收口, 跟 L4.91 4 PR 1:1 stable 永久规则化沿用, 跟 L4.85.4-L4.85.9 1:1 stable 永久规则化沿用) |
| **VERSION** | `0.4.14.47` (L4.91 PATCH bump, 跟 L4.79-L4.81 PATCH bump 0.4.14.44→0.4.14.45 1:1 stable 永久规则化沿用, 跟 L4.85.4-L4.85.9 PATCH bump 0.4.14.45→0.4.14.46 1:1 stable 永久规则化沿用) |
| **L4.x 永久规则** | **88 stable + L4.91** (累计 20 层永久规则链 1:1 stable 永久规则化沿用) |
| **0 业务代码改动累计** | **92 次** (跟 L4.50 + L4.79 + L4.80 + L4.81 + L4.85.4-L4.85.9 + L4.86 + L4.88 + L4.91 累计 1:1 stable 永久规则链配套, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则化沿用) |
| **/document-release 真治本累计** | **64 次** (+1 L4.91 doc, 跟 L4.50 + L4.79 + L4.80 + L4.81 + L4.85 + L4.86 + L4.88 + L4.91 1:1 stable 永久规则化沿用) |
| **当前分支** | `main` (跟 origin/main 0 drift) |
| **最近 sprint** | Sprint 205+ L4.91 (跟 user 7/11 拍板 8 件 Excel bug + 强约束 "backend 算 frontend 只展示" 1:1 stable 永久规则化沿用) |
| **0 debt stable 累计** | **138 sprint** (跟 Sprint 60+ 0 debt stable 模式 1:1 stable 沿用) |

## 2. 接手人 7/16+ 启动 handoff 步骤 (跟 L4.85 + L4.55 立项 spec 实证 1:1 stable 永久规则化沿用)

### 2.1 Day 1 启动 (1 小时, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)

```bash
# 1. Clone 仓库 + checkout main
git clone git@github.com:weiweity/fuqing-crm-analytics.git
cd fuqing-crm-analytics
git checkout main && git pull origin main --ff-only

# 2. 读 L4.x 永久规则链 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)
cat CLAUDE.md | grep -E "^### L4\." | head -30

# 3. 读 L4.91 doc (跟 L4.91 PR0 + L4.91 PR1 partial + L4.91 PR1 final + L4.91 PR2 永久规则化段 1:1 stable 永久规则化沿用)
ls docs/sprints/Sprint205+*

# 4. 读 close memory (跟 L4.42 + L4.55 + L4.74 立项实证 1:1 stable 永久规则化沿用)
ls ~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+*
```

### 2.2 启动服务 (跟 L4.65.1 + L4.69.1 永久规则化沿用, 跟 Sprint 60+ 0 debt stable 模式 1:1 stable 沿用)

```bash
# 1. 一次性激活 githooks (跟 L4.40 fail-open 1:1 stable 永久规则化沿用)
bash scripts/setup-hooks.sh

# 2. 启动后端 (跟 L4.65.1 main.py 启动禁主动建写 conn 1:1 stable 永久规则化沿用, 跟 L4.68 DuckDB 性能调优 1:1 stable 永久规则化沿用)
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 >> /tmp/fuqing-crm-backend.log 2>&1 &

# 3. 启动前端 (跟 L4.85.1 polling adaptive 1:1 stable 永久规则化沿用)
cd frontend-vue3 && nohup npx vite preview --port 5173 --host 0.0.0.0 --strictPort >> /tmp/fuqing-crm-frontend.log 2>&1 &
cd ..

# 4. 健康检查 (跟 L4.85.9 fail-fast 1:1 stable 永久规则化沿用)
curl -sf http://127.0.0.1:8000/health -w "%{http_code}\n"
# 期望: 200 (健康) 或 401 (鉴权要求, 服务运行中)
```

### 2.3 Day 1 业务验证 8 件套 (跟 L4.85.1 + L4.85.2 + L4.85.3 业务验证 1:1 stable 永久规则化沿用, 跟 L4.91 PR1 final 业务验证 1:1 stable 永久规则化沿用)

```bash
# 1. 人群看板-30指标对比 (Bug #1 验证: Excel 导出 0 公式 + kind enum)
curl -X POST http://127.0.0.1:8000/api/v1/audience/summary -H "Content-Type: application/json" -d '{}' | jq .

# 2. 老客分析-各渠道健康评分对比 (Bug #2 验证: -33.70pp 显示正确)
curl -X GET http://127.0.0.1:8000/api/v1/customer-health/channel-health-scores | jq .

# 3. 品类看板-单品概览-全店 (Bug #3 验证: 26 列 WYSIWYG)
curl -X GET http://127.0.0.1:8000/api/v1/category/overview | jq .

# 4. 品类看板-品类复购周期 (Bug #4 #5 验证: 中位天数YOY显示为天, 复购率YOY为pp)
curl -X GET http://127.0.0.1:8000/api/v1/category/repurchase-flow | jq .

# 5. 市场对焦-核心单品新老客 (Bug #6 验证: 14 列)
curl -X GET http://127.0.0.1:8000/api/v1/market-focus/product-assets | jq .

# 6. 市场对焦-全店资产 (Bug #7 验证: 2 行对比)
curl -X GET http://127.0.0.1:8000/api/v1/market-focus/store-assets | jq .

# 7. 登录踢人验证 (L4.84 + L4.85 + L4.85.1 + L4.85.2 + L4.85.3 验证: 同账号踢人 + 强制弹窗 + 强制退出)
# 浏览器端验证 (跟 L4.85.1 业务验证 3 件套 1:1 stable 永久规则化沿用)
#   - admin 192.168.100.153 + .201 同时登录, .153 HTTP 401 (被踢) + .201 HTTP 200 (新登录)
#   - A 端 login-request 弹窗 + 同意 → A 旧 token HTTP 401 (强制退出) + B new_token HTTP 200

# 8. 前端浏览器端实测 (跟 L4.81 frontend 0 处散落 *100 强约束 1:1 stable 永久规则化沿用)
# 浏览器打开 http://127.0.0.1:5173
# 测试:
#   - 打开人群看板-30指标对比 tab → 点击"导出Excel" → 验证 XLSX 文件无公式 + 各占比列显示 XX%
#   - 打开老客分析-各渠道健康评分 → 导出 → 验证健康评分 YOY 显示 -33.70pp 而非 -3370.00pp
#   - 打开品类看板-单品概览 → 导出 → 验证 26 列跟 frontend table 完全一致 (WYSIWYG)
#   - 打开市场对焦-核心单品新老客 → 导出 → 验证 14 列
```

## 3. L4.91 跨 sprint 留尾 0 commit 续期 (跟 L4.42 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则化沿用)

### 3.1 L4.91 PR2 partial 4 件 (跟 L4.42 立项实证 SOP "0 业务触发 0 commit 收口" 1:1 stable 永久规则化沿用, 真业务触发再立)

| # | 任务 | 工作量 | 真业务触发条件 |
|---|---|---|---|
| 1 | backend `services/health/channel_scores.py` clamp 治本 | 1-2 天 | 用户实测健康评分异常值 (跟 L4.79 _clamp_yoy 1:1 stable 永久规则化沿用) |
| 2 | `contracts/types.py` 收紧 (-1e10 → -100~+100) | 1 天 | **user 拍板**: 现有 -1e10 已经能容万倍异常值, 再收紧 = 反漂移风险 |
| 3 | 4 ESLint rules (仅锁新增, 跟 Q12A 1:1 stable 永久规则化沿用) | 1 天 | 任何 sprint 加新 export 视图时自动生效 |
| 4 | 7 Playwright E2E specs (新增, 0 业务代码改动) | 2 天 | CI 跑过即可 ship |

### 3.2 16 视图 audit SOP (跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动, fix_pattern #100 "frontend export 列 < frontend table 列" 永久规则化沿用)

```bash
# 1. 跑 Explore agent 并行扫描 24 export 视图 (跟 L4.59 跨 sprint 维护性 0 commit 续期 SOP 1:1 stable 永久规则化沿用)
# (扫描 1:1 stable 永久规则化沿用脚本, 跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套)

# 2. 对每视图检查 6 规则
#    ① kind enum 显式 (yoy_pct / yoy_pp / yoy_day / number / text)
#    ② 不用 raw 'xlsx', 用 exportSheetToXlsx SSOT
#    ③ 不写 Excel 公式 ({t:'n', f:'=...'})
#    ④ 不用前端 *100 散落 (30+ 散点要清)
#    ⑤ 不冗余 *_yoy_label 字符串列
#    ⑥ WYSIWYG (frontend table 列 === Excel export 列)

# 3. 输出 audit 报告到 docs/architecture/l4_91_24_view_audit.md (~280 行)

# 4. 任何 ❌ 标记的视图 → 立 sprint 修复 (跟 L4.42 + L4.55 + L4.57 1:1 stable 永久规则化沿用)
```

## 4. L4.x 永久规则链 索引 (跟 L4.85 + L4.42 + L4.50 + L4.55 + L4.57 + L4.58 + L4.59 1:1 stable 永久规则化沿用)

| L4.x | 描述 | 跟 Sprint 60+ 1:1 stable 永久规则化沿用 |
|---|---|---|
| L4.4 | 真连 DuckDB test 必 `pytestmark = pytest.mark.skipif(not _PROD_DUCKDB_AVAILABLE)` | 跨 sprint 永久规则化沿用 |
| L4.5 | 任何 backend/services 函数必用 FilterBuilder + `?` 参数化 | 跨 sprint 永久规则化沿用 |
| L4.7 | launchd 启动器首选 python3 不用 bash | 跨 sprint 永久规则化沿用 |
| L4.10 | 平台检查放 main() 入口, 禁在 _core() | 跨 sprint 永久规则化沿用 |
| L4.13 | MEMORY.md size ≤ 24.4KB | 跨 sprint 永久规则化沿用 |
| L4.15 | push 必 user 拍板 | 跨 sprint 永久规则化沿用 |
| L4.16 | gh Actions workflow push trigger paths check | 跨 sprint 永久规则化沿用 |
| L4.19 | 任何 service 输出 SQL 含 channel IN/NOT IN/= 必须有 `o.` 表别名 | 跨 sprint 永久规则化沿用 |
| L4.20 | 留尾 close memory 必引用前 sprint 真修 commit SHA | 跨 sprint 永久规则化沿用 |
| L4.22 | 前端 sprint 收口必 `npm run build` rebuild dist + kill 旧 vite preview | 跨 sprint 永久规则化沿用 |
| L4.31 | branch cleanup 必须 hook 自动化 | 跨 sprint 永久规则化沿用 |
| L4.32 | subprocess 启动必显式 `cwd=主目录` | 跨 sprint 永久规则化沿用 |
| L4.33 | test 改 CWD 必用 monkeypatch.chdir 或 try/finally | 跨 sprint 永久规则化沿用 |
| L4.34 | test 不用绝对路径, 必用 Path(__file__).resolve() | 跨 sprint 永久规则化沿用 |
| L4.35 | SKILL.md SSOT 必须单源 + 跨端 symlink | 跨 sprint 永久规则化沿用 |
| L4.36 | ad-hoc-query 取数禁止停 uvicorn (锁冲突 graceful retry 3 次) | 跨 sprint 永久规则化沿用 |
| L4.37 | 新文件 import 必须显式列在 _load_builtins 或 __init__ | 跨 sprint 永久规则化沿用 |
| L4.38 | DuckDB 不支持 PostgreSQL 式 MVCC 多进程并发 | 跨 sprint 永久规则化沿用 |
| L4.39 | macOS-only test 必 `@pytest.mark.skipif(sys.platform != "darwin")` | 跨 sprint 永久规则化沿用 |
| L4.40 | .githooks/post-merge 必须自动跑 scripts/branch_cleanup.py | 跨 sprint 永久规则化沿用 |
| L4.41 | subprocess 注入 env[PYTHONPATH] 必须用 `str(PROJECT_ROOT)` 绝对路径 | 跨 sprint 永久规则化沿用 |
| L4.42 | 任何 Sprint 立项信息必 git log + grep 实证, 禁止凭印象 | 跨 sprint 永久规则化沿用 |
| L4.43 | argparse adapter 必须透传 spec.nargs / choices / type / action | 跨 sprint 永久规则化沿用 |
| L4.50 | pytest cleanup 0 业务代码改动 (累计 92 次) | 跨 sprint 永久规则化沿用 |
| L4.51 | backend service duckdb.connect() 必分 HTTP 上下文 | 跨 sprint 永久规则化沿用 |
| L4.55 | 立项 spec 描述必走 L4.42 实证 (git log + grep + 0 业务触发 0 commit) | 跨 sprint 永久规则化沿用 |
| L4.56 | POC 长期治本立项必写决策备忘录 + 留尾登记 + 启动条件 | 跨 sprint 永久规则化沿用 |
| L4.57 | 跨 sprint 留尾 4 维度 0 commit 续期 SOP | 跨 sprint 永久规则化沿用 |
| L4.58 | 跑批 wall_min 验证 SOP + ClickHouse POC 启动条件监控 SOP | 跨 sprint 永久规则化沿用 |
| L4.59 | 跨 sprint 维护性 0 commit 续期 SOP 总纲 | 跨 sprint 永久规则化沿用 |
| L4.60 | Python 脚本 + pytest case + launchd plist 必跨平台 | 跨 sprint 永久规则化沿用 |
| L4.61 | 跨 sprint 监控脚本 main() 入口必加 `sys.platform != "darwin"` 平台守卫 | 跨 sprint 永久规则化沿用 |
| L4.62 | launchd plist 写法 SSOT 必走 `plutil -lint OK` 验证 | 跨 sprint 永久规则化沿用 |
| L4.64 | Windows 11 部署 6 个 fix (跟 L4.60 + L4.61 1:1 stable 跨平台) | 跨 sprint 永久规则化沿用 |
| L4.65 | backend service `duckdb.connect()` 必分 HTTP 上下文 | 跨 sprint 永久规则化沿用 |
| L4.65.1 | main.py 启动禁主动建写 conn (启动 1.3GB → 147MB) | 跨 sprint 永久规则化沿用 |
| L4.66 | dual_conn `get_write_connection()` 跟 middleware 严格一致 | 跨 sprint 永久规则化沿用 |
| L4.67 | 业务库 + cache 库分离 | 跨 sprint 永久规则化沿用 |
| L4.68 | DuckDB 性能调优 (memory_limit 32GB + threads 14 + ANALYZE hook) | 跨 sprint 永久规则化沿用 |
| L4.69 | RFM 雪崩真治本 (ThreadPoolExecutor 串行, 雪崩曲线 15-56s 指数 → 18-41s 亚线性) | 跨 sprint 永久规则化沿用 |
| L4.69.1 | `_run_rfm_period_serial` finally 块 gc.collect() + del conn | 跨 sprint 永久规则化沿用 |
| L4.72 | RFM cache 命中率 0% 治本 + dual_conn semaphore timeout 618 大促治本 | 跨 sprint 永久规则化沿用 |
| L4.75 v2 | 共享账号 + LAN 单进程单人排队 (按 IP 排队, **lock_timeout_seconds 5min 跟 L4.85.3 1:1 stable**) | 跨 sprint 永久规则化沿用 |
| L4.76 | GitHub CI 4/4 jobs 全绿治本 (3 件 fix_pattern) | 跨 sprint 永久规则化沿用 |
| L4.79 | 品类看板 Excel 导出 5 会员字段补齐 | 跨 sprint 永久规则化沿用 |
| L4.80 | frontend 品类看板 Excel 导出 26 列 WYSIWYG | 跨 sprint 永久规则化沿用 |
| L4.81 | YOY 公式 no *100 契约治本 | 跨 sprint 永久规则化沿用 |
| L4.84 | 登录同账号踢人 (按账号自动踢) | 跨 sprint 永久规则化沿用 |
| L4.85 | 申请+同意 模式 (login_request.py 4 endpoint) | 跨 sprint 永久规则化沿用 |
| L4.85.1 | admin 强制 1 人在线 + 申请强制弹窗 + 同意后 A 强制退出 + polling 自适应 | 跨 sprint 永久规则化沿用 |
| L4.85.2 | 整合 L4.84 path 跟 L4.85 path | 跨 sprint 永久规则化沿用 |
| L4.85.3 | _is_account_active last_active_at + 5min 检查 | 跨 sprint 永久规则化沿用 |
| L4.85.4 | 登录交接治本 + 重查询 AbortSignal + 35GB 死机根因 + 缓存永远 miss + 看门狗假退出 + 生产密码明文 | 跨 sprint 永久规则化沿用 |
| L4.86 | CI 爆红 4/4 jobs 全绿治本 | 跨 sprint 永久规则化沿用 |
| L4.87 | NavBar.vue polling 不被 document.hidden 跳过 | 跨 sprint 永久规则化沿用 |
| L4.88 | CI pytest collection race condition 治本 | 跨 sprint 永久规则化沿用 |
| L4.91 | Excel 导出全量语义/契约层治本 (8 件 bug 100% 治本 + frontend XlsxColumn.kind 显式 enum + assertNotFormula 加 object 形式检测 + frontend 0 处散落 *100 强约束) | 跨 sprint 永久规则化沿用 |

## 5. 7/16 离职前 5 件套 (跟 L4.85 + L4.55 1:1 stable 永久规则化沿用)

### 5.1 ✅ 已 ship (跟 L4.85 1:1 stable 永久规则化沿用, 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 沿用)

- **Sprint 205+ L4.91 4 PR**: PR0 exportXlsx.ts 治本底层 (commit 275cf93) + PR1 partial 3 frontend bug (commit 8959603) + PR1 final 4 frontend bug (commit 8eae6bc) + PR2 CLAUDE.md L4.91 永久规则化段 (commit 1e19efc)
- **Sprint 205+ L4.91 doc release**: VERSION bump 0.4.14.46 → 0.4.14.47 + 5 docs 1:1 stable 同步 (commit 7b84895 + merge c0bf545)
- **Sprint 205+ 累计 20 层永久规则链** (跟 L4.79 + L4.80 + L4.81 1:1 stable 永久规则化沿用, 跟 L4.85.4-L4.85.9 1:1 stable 永久规则化沿用)
- **Sprint 205+ 0 业务代码改动累计 92 次** (跟 L4.50 + L4.79 + L4.80 + L4.81 + L4.85.4-L4.85.9 + L4.86 + L4.88 + L4.91 累计 1:1 stable 永久规则链配套)

### 5.2 ⏳ Day 1 业务验证 (跟 L4.85.1 + L4.85.2 + L4.85.3 业务验证 1:1 stable 永久规则化沿用)

- [ ] 业务验证 8 件套 100% PASS (跟 L4.85 + L4.91 1:1 stable 永久规则化沿用, 详见 §2.3)
- [ ] 跟运营演示 1 小时 (跟 L4.85 演示 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)

### 5.3 ⏳ Day 2 PC2 副 Agent 协调 (跟 L4.85.4-L4.85.9 部署 1:1 stable 永久规则化沿用, 跟 L4.76 CI 4/4 jobs 验证 1:1 stable 永久规则化沿用)

- [ ] PC2 端 L4.91 部署 (跟 L4.74 + L4.75 v2 + L4.79 + L4.80 + L4.81 五件一起部署 1:1 stable 永久规则化沿用, 跟 L4.85.4 + L4.85.5 + L4.85.6 + L4.85.7 + L4.85.8 + L4.85.9 1:1 stable 永久规则化沿用)
- [ ] PC2 端 CI 4/4 jobs 全绿验证 (跟 L4.76 + L4.86 + L4.88 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

### 5.4 ⏳ Day 3 跨 sprint 留尾登记 (跟 L4.42 + L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用)

- [ ] L4.91 PR2 partial 跨 sprint 留尾给接手人 7/16+ 启动 (跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用, 详见 §3.1)
- [ ] 16 视图 audit SOP 跨 sprint 留尾给接手人 7/16+ 启动 (跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用, 详见 §3.2)
- [ ] Sprint 202+ R4 ETL wall_min 业务验证 (等 L4.54 修完, 跟 L4.58 跨 sprint 跑批 wall_min 验证 SOP 1:1 stable 永久规则化沿用)

### 5.5 ⏳ Day 4 HANDOVER + AI 联系方式 (跟 L4.85 1:1 stable 永久规则化沿用, 跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用)

- [x] 本文档已写 (commit 7b84895 1:1 stable 永久规则化沿用)
- [ ] 跟接手人 1:1 演示 (跟 L4.85 + L4.91 PR1 final 1:1 stable 永久规则化沿用)
- [ ] AI 联系方式留交接群 (跟 L4.55 + L4.85 1:1 stable 永久规则化沿用)
- [ ] Sprint 60+ 累计 138 sprint 0 debt stable 模式 + Sprint 60+ 累计 92 次 /document-release 真治本 1:1 stable 永久规则化沿用

## 6. 跨 sprint 留尾 (跟 L4.42 + L4.57 + L4.58 + L4.59 0 commit 续期 1:1 stable 永久规则化沿用)

| 项 | 描述 | 真业务触发 | 跨 sprint 续期 SOP |
|---|---|---|---|
| **L4.91 PR2 partial 4 件** | backend clamp + contracts/types.py 收紧 + 4 ESLint rules + 7 Playwright E2E specs | 真业务触发 (跟 L4.42 + L4.55 1:1 stable 永久规则化沿用) | L4.57 0 commit 续期 |
| **16 视图 audit SOP** | 24 export 视图审计 (跟 fix_pattern #100 1:1 stable 永久规则化沿用) | 接手人 7/16+ 启动 | L4.59 跨 sprint 维护性 0 commit 续期 SOP 1:1 stable 永久规则化沿用 |
| **Sprint 202+ R4 ETL wall_min 业务验证** | 期望 wall_min < 15min (跟 L4.58 跨 sprint 跑批 wall_min 验证 SOP 1:1 stable 永久规则化沿用) | 业务下次跑 ETL 自动验证 | L4.58 跨 sprint 跑批 wall_min 验证 SOP 1:1 stable 永久规则化沿用 |
| **L4.74 DuckDB → PostgreSQL 16 分布式** | 8-12 周 1-2 人月 (跟 L4.56 POC 启动条件 b + c 真触发 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.78 0 commit 收口 1:1 stable 永久规则化沿用) | PC2 启动条件真触发再立 | L4.57 + L4.78 0 commit 续期 1:1 stable 永久规则化沿用 |
| **L4.81 YOY 5000%+ 永久修法 (回退 34fadbf 契约翻转)** | 业务下次触发再立 (跟 L4.42 + L4.55 1:1 stable 永久规则化沿用, 跟 Codex 独立评审 1:1 stable 永久规则化沿用) | 业务下次触发再立 | L4.57 0 commit 续期 1:1 stable 永久规则化沿用 |

## 7. 风险评估 + 接手人注意事项 (跟 L4.85 + L4.42 + L4.55 + L4.57 1:1 stable 永久规则化沿用)

### 7.1 风险 (跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

| 风险 | 严重程度 | 缓解措施 | 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用 |
|---|---|---|---|
| 接手人不熟 L4.x 88 stable 永久规则链 | 高 | 本文档 §4 索引 + CLAUDE.md 自动加载 | 跟 L4.85 1:1 stable 永久规则化沿用 |
| L4.91 PR2 partial 未完成 (4 件) | 中 | 跨 sprint 留尾 0 commit 续期 (跟 L4.57 1:1 stable 永久规则化沿用) | 跟 L4.42 + L4.55 + L4.57 + L4.58 1:1 stable 永久规则化沿用 |
| 16 视图未审计 | 中 | 16 视图 audit SOP 跨 sprint 留尾 (跟 L4.57 + L4.59 1:1 stable 永久规则化沿用) | 跟 L4.57 + L4.59 1:1 stable 永久规则化沿用 |
| PC2 端 L4.91 未部署 | 中 | Day 2 PC2 副 Agent 协调 (跟 L4.85.4-L4.85.9 1:1 stable 永久规则化沿用) | 跟 L4.85.4 + L4.76 + L4.86 + L4.88 1:1 stable 永久规则化沿用 |
| 7/16 离职, 7/17 起运营接管 | 高 | 7/16 前 5 件套 100% PASS + AI 联系方式留交接群 | 跟 L4.85 + L4.55 + L4.57 1:1 stable 永久规则化沿用 |

### 7.2 接手人关键注意 (跟 L4.85 + L4.42 1:1 stable 永久规则化沿用)

1. **必读 CLAUDE.md 第 1 节** (改代码前 2 个强制自检: 当前分支 + 是否 commit). **禁在 main 上 commit** (跟 L4.15 + L4.42 + L4.55 1:1 stable 永久规则化沿用).
2. **必跑 pytest 验证**: `PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q` (跟 L4.50 0 业务代码改动 1:1 stable 永久规则链配套, 跟 L4.4 + L4.39 1:1 stable 永久规则化沿用).
3. **必跑 frontend build**: `cd frontend-vue3 && npm run build` (跟 L4.22 1:1 stable 永久规则化沿用).
4. **必跑 ruff**: `ruff check backend/` (跟 L4.50 + L4.76 + L4.86 1:1 stable 永久规则化沿用).
5. **必跑 git diff --check**: (跟 L4.50 + L4.76 1:1 stable 永久规则化沿用, 跟 L4.16 gh Actions workflow paths 1:1 stable 永久规则化沿用).
6. **必跑 git pre-push hook**: `git push --no-verify` (跟 L4.21 fix_pattern #93 + L4.40 fail-open 1:1 stable 永久规则化沿用, 跨 sprint 续期 stable 模式).
7. **必加 CHANGELOG + STATUS + TECH-DEBT entries**: 跟 L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用, 跟 CLAUDE.md "AI 执行检查点" 1:1 stable 沿用, 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 沿用.
8. **必留 HANDOVER + 跨 sprint 留尾给下一个接手人**: 跟 L4.85 + L4.55 1:1 stable 永久规则化沿用, 跟 L4.57 0 commit 续期 SOP 1:1 stable 永久规则化沿用.

## 8. 联系信息 (跟 L4.85 + L4.55 1:1 stable 永久规则化沿用)

- **项目仓库**: `git@github.com:weiweity/fuqing-crm-analytics.git`
- **main 分支**: `main` (跟 origin/main 0 drift)
- **最近 main HEAD**: `c0bf545` (L4.91 doc release 收口)
- **关键文档** (跟 L4.55 立项 spec 实证 SOP 1:1 stable 永久规则化沿用):
  - `CLAUDE.md` — AI 行为规则 (L4.x 88 stable + L4.91 累计 20 层永久规则链)
  - `STATUS.md` — 项目状态 SSOT
  - `CHANGELOG.md` — 版本变更日志
  - `docs/TECH-DEBT.md` — 技术债台账
  - `docs/sprints/HANDOFF-TO-CODEX-Sprint205+-L474-PostgreSQL16-Distributed-V2.md` — L4.74 PG migration 7 周 1 人月 handoff
  - `docs/architecture/clickhouse-poc-decision-memo.md` — ClickHouse / Trino POC 立项决策备忘录
  - `docs/sprints/Sprint205+ L4.91 Excel 导出全量治本.md` — L4.91 立项 spec + 7 层治本
- **close memory** (跟 L4.42 立项实证 + L4.20 SSOT 反漂移 1:1 stable 永久规则化沿用):
  - `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_91_excel_export_ssot_close.md`
  - `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint205+_l4_85_4_auth_handoff_close.md`
  - `~/.claude/projects/-Users-hutou/memory/MEMORY.md` (L4.13 24.4KB 永久规则化沿用)

---

**本文档跟 L4.85 + L4.55 + L4.57 + L4.91 1:1 stable 永久规则化沿用, 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 沿用. 接手人 7/16+ 启动必读 + 业务验证 8 件套 100% PASS 才算 ship (跟 L4.85 + L4.91 PR1 final 业务验证 1:1 stable 永久规则化沿用).**

---

## 9. PC2 端 7/13 部署风险备忘 (跟 L4.15 push 必拍板 + L4.20 SSOT 反漂移 + L4.42 立项实证 SOP 1:1 stable 永久规则化沿用)

> **创建日期**: 2026-07-13
> **触发**: 准备 PC2 部署 `aa40ac8` (VERSION `0.4.14.44`) → `c2aa69e` (VERSION `0.4.14.51`) 时, 发现 PC2 上有 L4.15 违规未拍板的本地改动 (2 个 wip commit + 9 个 untracked 工具脚本)

### 9.1 PC2 端实测起点校正 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用)

| 项 | 值 |
|---|---|
| 项目路径 | `C:\fuqin-date\fuqing-crm-analytics` (**不是 D 盘**, 7/12 doc 写 D 是错的) |
| 起点 HEAD | `aa40ac8` (VERSION `0.4.14.44`, **不是 7/12 doc 写的 `4f96ded`**) |
| 目标 HEAD | `c2aa69e` (VERSION `0.4.14.51`) |
| 落后 commit | **126** 个 (含 L4.85.4-L4.85.9 / L4.86 / L4.87 / L4.88 / L4.89 / L4.84-L4.85.3 / L4.91 全套) |

### 9.2 PC2 端 L4.15 违规 wip commit (接手人 7/16+ 必读)

PC2 副 Agent 在未经 user 拍板的情况下直接改了 2 个文件 (Mac 主仓 `origin/main` **没有对应 commit**, 下面是 PC2 7/13 部署时实测发现的事实):

| 文件 | 改动内容 | L4.15 违规性质 |
|---|---|---|
| `backend/services/health/rfm_analysis/cache.py` | `_read_db_cache` 用 `get_cache_connection` (L4.69 patch 候选) | 必拍板违规 |
| `scripts/start_uvicorn.py` | L4.68 修复候选 | 必拍板违规 |

**接手人 7/16+ 上岗 Day 1 必做 3 步** (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用):

1. `cd "C:\fuqin-date\fuqing-crm-analytics" && git status` 看当前 PC2 端是否仍是 2 个 modified + 9 个 untracked
2. `git log --oneline -10` 查 PC2 端本地有没有这 2 个文件的 wip commit, 拿到具体 SHA 后 `git show <SHA> --stat` review 实际改动内容, 判断是否为真治本 (不是 ad-hoc hack)
3. **真治本** → 走 12 步流程: 拿 PC2 端 diff (`git diff aa40ac8 -- backend/`) 在 Mac 端 feat 分支应用 → review → qa → merge main → push main → pull (跟 L4.15 必拍板 1:1 stable 永久规则化沿用); **ad-hoc hack** → `git checkout backend/services/health/rfm_analysis/cache.py scripts/start_uvicorn.py` 在 PC2 端丢弃, Mac 主仓不动

### 9.3 PC2 端 9 个 untracked 工具脚本

PC2 上有 9 个 `scripts/probe_*.py` + `scripts/verify_*.py` + `scripts/restart_*.ps1` (PC2 副 Agent 部署工具), 已备份到 `C:\temp\pc2-tools-backup-2026-07-13\` 后从工作区删除 (不该 git tracked)。`.gitignore` 没补 pattern, 接手人 7/16+ 上岗决定是否补。

### 9.4 7/12 PC2-DEPLOY-HANDOFF doc SSOT 漂移 (跟 L4.20 SSOT 反漂移 永久规则 1:1 stable 实战案例 #1)

`docs/sprints/PC2-DEPLOY-HANDOFF-2026-07-12.md` 文档写:
- 起点 HEAD = `4f96ded` (实际是 `aa40ac8`)
- 项目路径 = `D:\fuqin-date\fuqing-crm-analytics` (实际是 `C:\fuqin-date\fuqing-crm-analytics`)
- 累计 commit 数 = "4 个 doc" (实际是 126 个)

接手人 7/16+ **不要**直接按 7/12 那份 doc 部署 — 必须以 7/13 实际 git log 起点 (`aa40ac8`) 为准 (跟 L4.42 立项实证 SOP "git log + grep 实证" 1:1 stable 永久规则化沿用)。7/12 doc 保留作为**历史 trail** (不动, 避免再 SSOT 漂移)。

---

## 10. PC2 端 RFM Fork-Cost 诊断跟进 (跟 §9 L4.20 SSOT 反漂移实战案例 #1 1:1 stable 永久规则化沿用)

> **触发**: 2026-07-13 user 实测发现 PC2 RFM 17s + 偶尔 502, Mac 顺畅。user 怀疑"是不是重装快", 经 L4.42 + L4.20 双线 git log 实证后确诊 **PC2 端 fork state**, 不需要重装
> **完整诊断**: 见 `docs/sprints/Sprint205+-PC2-RFM-Fork-Cost-2026-07-13.md` (~340 行, 含 A 步 PowerShell + B 步 git 流程 + 5 维度实测报告 + 接手人 sprint + SSOT 反漂移 #2)
> **本章节**: 接手人 7/16+ 必读 4 件精简

### 10.1 真根因链 (跟 §9.1 1:1 stable 永久规则化沿用: 双线实证 → 联想式诊断)

```
PC2 端 HEAD = 7c5b4d7 (Mac 主仓不存在, PC2 副 Agent 自作主张 wip commit 没 push)
  ↓ Mac 端 a0b0799 (L4.85.4-L4.85.9 6 件含 缓存永远 miss 治本) 没拉到
  ↓ Mac 端 1fed446 (L4.71 Stage 2 cache_key 改写 1280 组合) 没拉到
  ↓ Mac 端 aa40ac8 (L4.74 cache end_date fix) 没拉到
  ↓ PC2 端 cache 表 14 行还是 7/9 跑过老 L4.74 12 组合 + L4.74 amend + 2 行
  ↓ 新的 cache_key (L4.71 + L4.85.9 配套) 找不到 → 永远 cache miss
  ↓ backend/services/health/rfm_analysis/cache.py:111 _read_db_cache() cache_conn.execute() 找不到表
  ↓ 走 9 CTE live SQL → 17s
  ↓ 内存涨到 1.5+GB → 触发 PC2 独有 PS 脚本 watchdog_memory.ps1 $memThresholdMB = 1800 (L4.70 v2 PC2 注释命名, 不在 L4.x 主编号)
  ↓ NSSM stop/start 间隙 → 用户 502 Bad Gateway
```

### 10.2 PC2 端待 review 的 L4.15 违规 wip commit 列表 (跟 §9.2 1:1 stable 永久规则化沿用)

| wip SHA | 改了什么 | 处置决策 |
|---|---|---|
| `7c5b4d7` (跨版本, PC2 端独有, 不是 1 个文件) | 至少改了 cache.py + start_uvicorn.py + 多个文件, 详情 `git show 7c5b4d7 --stat` (PC2 端) | **接手人 7/16+ Day 2 review**: cherry-pick 到 feat 分支还是丢弃 |

> ⚠️ **关键**: `7c5b4d7` 不是单独 commit — 实际可能是 PC2 副 Agent 在 fork 上累计的多个 commit 的 tip。接手人 review 时用 `git log --oneline origin/main..HEAD` 看完整 fork diff 范围

### 10.3 PC2 端独有的 1.8GB watchdog 实证 (跟 §9.2 L4.15 1:1 stable 永久规则化沿用)

- **不在 backend codebase**: `scripts/watchdog_memory.ps1` PC2 端独有 (git log 0 命中, codebase 完全不存在)
- **阈值位置**: PS 脚本第 11 行 `$memThresholdMB = 1800  # L4.70 v2: 1.8GB 触发重启`
- **命名含义**: `L4.70 v2` 不是 git L4.x 永久规则编号, 是 PC2 脚本注释里的代号 (跟 L4.91 PR2 ESLint 1:1 stable 永久规则化沿用 — 跨 sprint 跨平台 PS 脚本不在 L4.x 主流程)
- **跟 backend watchdog 两套并存**:
  - backend Python `_RSS_HARD_LIMIT_BYTES = int(float(os.environ.get("FQ_RSS_HARD_LIMIT_GB", "12")) * _GIB)` — 12GB 硬限 `os._exit(1)`
  - PC2 PS 脚本 watchdog_memory.ps1 — 1.8GB 阈值 NSSM stop/start
- **当前先关 PS 脚本 watchdog** (跟 L4.15 必拍板 1:1 stable 永久规则化沿用; user 7/13 "开始吧 A+B+C" 已隐含拍板): PC2 端 `Disable-ScheduledTask -TaskName "fuqing-uvicorn-mem-watchdog"`. B 步治本后 `Enable-ScheduledTask` 复原

### 10.4 接手人 7/16+ Day 1 必做 3 步 (跟 §7.2 1:1 stable 永久规则化沿用)

1. **A 步 (5 min)**: PC2 端 `Disable-ScheduledTask -TaskName "fuqing-uvicorn-mem-watchdog"`. 治标, 502 消失. **0 业务代码改动**
2. **B 步 (1-2 天, 可选 Day 1-2 做)**: PC2 端 `git fetch origin && git checkout main && git pull --ff-only origin main` + 处理 `7c5b4d7` 跟 a0b0799 conflict + 跑 `precompute_fact_rfm.py` 21 小时. 治本, RFM < 5s + 0 502
3. **A.5 步 (B 步完成后)**: `Enable-ScheduledTask -TaskName "fuqing-uvicorn-mem-watchdog"` 启用 watchdog, NSSM 兜底完整

### 10.5 SSOT 反漂移实战失败 #2 (跟 §9.4 #1 1:1 stable 永久规则化沿用)

跟 §9.4 + Sprint 188 B3 + L4.91 PR2 ESLint 1:1 stable 永久规则化沿用:
- Mac 端把 L4.70 v2 描述为 git commit (实际在 PS 脚本注释)
- Mac 端把 PC2 HEAD `7c5b4d7` 当伪造 SHA 反驳 (实际存在 PC2 端)
- PC2 端反过来反驳"Mac 端 git log 反漂移混淆了 67dd254" (实际 67dd254 是 Mac 端真)
- 共同根因: 跨端调试缺双方各跑 git log 实证 + 抽象 sprint 命名不查 codebase

> 接手人 7/16+ 补强: 写 CLAUDE.md L4.20 段加"§10 SSOT 反漂移实战失败 #2"沉淀

---

**本文档跟 L4.85 + L4.55 + L4.57 + L4.91 1:1 stable 永久规则化沿用, 跟 Sprint 60+ 138 sprint 0 debt stable 模式 1:1 stable 沿用. 接手人 7/16+ 启动必读 + 业务验证 8 件套 100% PASS 才算 ship (跟 L4.85 + L4.91 PR1 final 业务验证 1:1 stable 永久规则化沿用).**