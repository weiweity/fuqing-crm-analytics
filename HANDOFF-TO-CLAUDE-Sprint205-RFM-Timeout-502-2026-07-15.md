# Sprint 205+ PC2 RFM 30s Timeout / 502 / 401 交接给 Claude Code

> 状态：CODE_DONE_DEPLOYMENT_BLOCKED
>
> 代码已实现并通过独立审查；尚未 stage、commit、push、merge 或部署。
> PC2 首次 ETL + RFM 完整预热需要用户批准的停服维护窗口，这是实际部署 blocker。

## 1. 工作区与边界

- Worktree：/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics-codex-rfm-timeout
- Branch：fix/sprint205-rfm-timeout-502-2026-07-15
- Base：origin/main@af50345
- 主仓 main 的用户未提交内容已原样保留，本轮未触碰。
- 不得把旧文件 PROMPT-TO-MAC-Sprint205+-RFM-30s-Timeout-502-Handoff.md
  当成新验收 SSOT。其 416/544 组合、access_token、period/metric 路由参数、
  调高 timeout/retry/watchdog 和自动 Task Scheduler 建议已被实证推翻。

## 2. 根因结论

1. 前端真实 RFM 请求只发 start_date、end_date、metric_type、channel、
   exclude_channels 和 compare dates，不发 period。旧 fuzzy 路径却依赖 period
   metadata，导致预热行与 HTTP 形态无法命中。
2. 旧 fuzzy 没有完整重建 cache key，可能忽略 compare、exclude 和新鲜度维度；
   last90days、昨日、WTD、Q1-Q4 等前端周期也未完整进入预热计划。
3. 旧预热 compare 模式与前端不一致；真实交互是默认 YOY 和 auto_mom 紧邻等长前期。
4. cache miss 后 HTTP worker 同步执行三段 live RFM，会扫描约 122 GB DuckDB。
   首次请求超过 Axios 30s，同时 RSS 上涨；PC2 外部 1.8 GB watchdog 重启 NSSM，
   所以紧接着出现 502。
5. auth token 只存在 uvicorn 内存。进程重启后旧 token 失效，pending、refresh、
   session 随后变成 401，用户看起来像“被踢出登录”。
6. PC2 现场业务库 MAX(pay_time)=2026-07-05 23:59:58、COUNT(*)=10,829,767，
   数据本身已经滞后。只修 cache 会稳定、快速地返回陈旧数据，因此 ETL 新鲜度是
   部署前硬门槛。

## 3. 实现摘要

### HTTP 雪崩隔离

- router 内部写死 allow_live_compute=False；它不是 query 参数，客户端不能绕过。
- 普通 miss 快速返回 503 + Retry-After: 60；cache 基建故障返回 503 +
  Retry-After: 30。两者都不允许 HTTP 回退 live SQL。
- 非 HTTP 维护/测试调用保留 allow_live_compute=True 的默认兼容性。
- 保留全局 Axios 30s 且不增 retry；拉长超时只会掩盖后端雪崩。

### 缓存匹配安全

- fuzzy 容差为 ±2 天：0/1/2 命中，3 天拒绝。
- 每个候选都用真实 date-based key 重建，并严格核对 data-version、channel、
  metric、exclude 和 compare。
- auto_mom 会随候选日期同步平移比较期；custom compare 不会被误命中。
- 完整代超过 ±2 天后，仅对“请求日期精确等于今日前端热周期”的请求按 period
  取 last-known-good。custom、custom compare、exclude、非预热 channel 仍拒绝。
- 损坏或元数据不一致的 active row 按 generation_id + cache_key + 读取快照精确删除，
  并在同一请求回退当前 on-demand cache，避免 TOCTOU 误删。

### 预热发布模型

- 热周期：11 个固定周期 + 8 个 range alias。
- 维度：2 metric × 5 channel（全店/货架/达播/直播/淘客）× 2 compare
  （default YOY / auto_mom）。
- gate = 19 × 2 × 5 × 2 = 380 个 logical combination。
- 多个 period alias 可映射为同一日期 key，所以物理行数随日期变化。不得用
  208/320/340/416/544 等固定物理行数验收。
- 每次 run 使用唯一 generation，物理行主键是 generation_id + cache_key。
  仅 380/380 全部成功才原子切换 rfm_cache_generation marker。
- 失败或被杀的半批不激活、不 prune；HTTP 始终读取上一完整代。
- active generation 是 last-known-good，在下一次成功切代前不按墙钟硬过期；
  inactive 行才按 48h 回收。这是 availability-over-freshness，不是新鲜度保证。

### 时间口径

- 新增 last90days、昨日、WTD、Q1-Q4 resolver。
- 修复闰日跨年平移；修复元旦 YTD 和每季首日的反向区间，回退上一完整年/季度。
- 2024–2028 逐日枚举的前后端 11 个固定周期已验证零漂移。

## 4. 明确未改的内容

- 未改 PC2 外部 1.8 GB PowerShell watchdog；该文件不在本仓库。
- 未修改仓库 8 GB / 12 GB memory monitor。
- 未拉长 Axios timeout，未加 RFM retry。
- 未修改或启用以下 scheduler 文件，它们的 diff 必须保持 0：
  - scripts/etl/scheduler/README.md
  - scripts/etl/scheduler/etl_daily_taskscheduler.xml
  - scripts/etl/scheduler/install_windows.ps1
- 未覆盖前端所有筛选组合。预热仅覆盖全店/货架/达播/直播/淘客；微博、四个低价
  渠道、纯派样、剔除低价和 custom compare 会快速 503，而不是回退 live SQL。

## 5. 验证证据

- Focused backend：63 passed in 44.54s
- 扩大 RFM/时间/路由相关集：182 passed in 140.18s
- 后端全量主调用：1385 passed, 13 skipped in 1642.58s；该调用主动 ignore
  backend/tests/test_w4_t7_integration.py。
- 上述隔离文件随后单独复验：4 passed in 18.91s。因此两次调用合计覆盖全部
  backend tests：1389 passed, 13 skipped。
- Frontend Vitest date.test.ts：12 passed。
- Frontend production build：vue-tsc -b && vite build 通过（4945 modules，
  仅既有 chunk-size warning）。
- 真实 router miss 属性验证：1056 个 HTTP miss 全部 503，live SQL spy = 0。
- 10 天前 active generation 属性验证：380/380 热组合命中；custom、
  custom compare、exclude 负例全部拒绝。
- scoped Ruff、channel-alias lint、py_compile、git diff --check 全部通过。
- ruff check backend/ 仍报 3 个基线错误，全部在本分支未修改的
  backend/scripts/check_l4_91_excel_export_ssot.py（unused field + 两个无占位 f-string）；
  不应在本修复中夹带改动。
- 两名独立 reviewer 最终均 PASS，未发现 P0/P1/P2 代码问题。

## 6. Claude Code 审查清单

1. 先运行：

       git branch --show-current
       git status --short
       git diff --check
       git diff --stat
       git diff -- scripts/etl/scheduler/

2. 重点审查：
   - HTTP 是否存在任何 miss → live SQL 绕过路径。
   - fuzzy / period fallback 是否完整核对 compare/exclude/channel/metric/version。
   - 半批 generation 是否可能在 380/380 前污染 active marker。
   - stale/corrupt row 是否删对 generation，同请求回退是否保持 cache-only。
   - 前后端 YTD/季度首日/闰日是否继续同口径。
3. 本轮不允许夹带 scheduler 安装、watchdog 改阈值或 Axios retry。
4. 用户尚未授权 push/部署；按项目 gate 完成 review 后再等用户拍板。

## 7. PC2 部署硬门槛

### 不得做

- 不得在 uvicorn 常驻时从第二个进程跑完整 ETL / RFM precompute。
- 不得启用现有 FuqingETLDaily / scheduler XML / install script。
- 不得由自动任务停启生产 uvicorn；L4.36 明确禁止。
- 不得在 ETL 仍停留在 2026-07-05 时宣称部署成功。

### 用户批准的维护窗口内，人工执行

1. 获得用户对停服窗口和 PC2 操作的明确批准。
2. 部署已 review/merge 的 main：

       git pull origin main --ff-only

3. 记录 uvicorn PID/RSS、当前 active marker、业务库 MAX(pay_time) / COUNT(*)。
4. 人工执行 nssm stop fuqing-uvicorn，并确认进程退出。
5. 使用真实 ETL 入口恢复数据：

       .\.venv\Scripts\python.exe scripts\run_etl.py --update

   该入口 Step 6 会运行 RFM precompute，必须返回 380/380 logical combinations。
   如果 ETL 数据已经另行验证为新鲜，才可单独运行：

       .\.venv\Scripts\python.exe -c "from backend.services.health.rfm_analysis.cache import precompute_rfm_cache; r=precompute_rfm_cache(); print(r); assert r == 380"

6. 成功后核对 marker 与业务库快照：
   - active_data_version == orders.MAX(pay_time)
   - active_orders_count == orders.COUNT(*)
   - active_generation_id 在 rfm_analysis_cache_generation_rows 有完整物理 key set
   - precompute log 是 logical 380/380，不以固定物理行数作 gate
   - MAX(pay_time) 满足业务新鲜度 SLA；若上游文件本身无新数据，显式报阻塞
7. 无论预热成功还是失败，都要在维护处置结束后人工恢复 nssm start fuqing-uvicorn。
   失败时不会切换 active generation，可保留上一完整代。

## 8. PC2 验收

认证和路由契约修正：

- POST /api/v1/auth/login 返回字段是 token，不是 access_token。
- RFM 端点必须传 start_date/end_date/metric_type；它不接受旧示例的
  period=last180days&metric=GSV 形态。

PowerShell 示例（密码请用现场安全方式提供，不要写入仓库）：

    $login = curl.exe -sS -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"<PASSWORD>"}' | ConvertFrom-Json
    $token = $login.token
    $end = (Get-Date).Date.AddDays(-1)
    $cases = @(
      @("last90",  $end.AddDays(-89),  $end),
      @("last180", $end.AddDays(-179), $end),
      @("last365", $end.AddDays(-364), $end),
      @("Q1", [datetime]::new($end.Year, 1, 1), [datetime]::new($end.Year, 3, 31))
    )
    foreach ($case in $cases) {
      $startText = $case[1].ToString("yyyy-MM-dd")
      $endText = $case[2].ToString("yyyy-MM-dd")
      $url = "http://127.0.0.1:8000/api/v1/customer-health/rfm-analysis?start_date=$startText&end_date=$endText&metric_type=GSV"
      curl.exe -sS -o NUL -w "$($case[0]) HTTP=%{http_code} time=%{time_total}s" -H "Authorization: Bearer $token" $url
    }

验收标准：

1. last90/180/365/Q1、GSV/GMV、default/auto_mom、五个核心渠道的预热组合
   均返回 200，目标小于 5s。
2. 至少一个 custom date、非核心 channel、exclude/custom compare 返回 503，
   且小于 1s；不得出现 30s timeout 或 502。
3. 连续执行 10 次 last180/365：
   - uvicorn PID 不变
   - RSS 不持续攀升，且不触发 watchdog restart
   - 原 token 调用 GET /api/v1/auth/me 仍为 200
   - NSSM/watchdog 日志无重启记录
4. 记录 marker completed_at/data_version/count。last-known-good 可能陈旧，不得把
   “快速 200”等同于“数据新鲜”。

## 9. 交付状态

- 代码：完成
- 单测/全量/构建：通过
- 独立 review：PASS
- stage / commit / push / merge：未执行
- PC2 部署：未执行，等待用户批准维护窗口
- 长期自动刷新：仍需进程内 job、staging DB 原子切换或迁移支持并发的数据库；
  本轮不使用不安全 scheduler 伪装闭环。
