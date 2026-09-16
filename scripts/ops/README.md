# scripts/ops — 跨 sprint 运维监控

Monitor scripts for launchd (local = production).

| Script | Plist label |
|---|---|
| `pre_existing_fail_monitor.py` | `com.fuqing.pre-existing-fail-monitor.weekly` |
| `memory_size_monitor.py` | `com.fuqing.memory-size-monitor.weekly` |
| `adhoc_query_hitrate_monitor.py` | `com.fuqing.adhoc-hitrate-monitor.weekly` |
| `clickhouse_poc_monitor.py` | `com.fuqing.clickhouse-poc-monitor.weekly` |
| `check_db_size.py` | `com.fuqing.db-size-alert.daily` |
| `fill_2026_q3_overlay.py` | 手工；不进 launchd。不复制/改写归档库 |

**REPO_ROOT** = `Path(__file__).resolve().parents[2]`（文件在 `scripts/ops/`）。

`fill_2026_q3_overlay.py` 只 ATTACH 只读归档，不改写归档文件。必填 `FQ_ARCHIVE_DUCKDB` 与 `FQ_DUCKDB_WRAPPER`，且必须是两条不同绝对路径。wrapper 若已存在会先 `unlink` 再重建，不是追加。脚本把 2023-07-06～2023-09-15 订单平移到 2026-07-06～2026-09-15（`SYN26-U-` 用户前缀），访客用 2025-07-06～2025-09-15 +1 年；不是覆盖整个「7 月后」。wrapper 仍保留归档原表视图，不是纯合成演示库。启动 API 必须同时设 `DUCKDB_PATH=<wrapper>` 和 `FQ_ARCHIVE_DUCKDB=<archive>`，否则 `src.*` 视图无法解析。未授权不要对 131GB 归档执行 SQL。

归档 `src.user_rfm` 若没有源窗口末日及更早的 GMV/90 as-of，脚本改为用 `src.orders` 按 `semantic.segments` 阈值现算 GMV/90（as-of `2023-09-15`，回看 90 天，不含购尽进/交易关闭），再 +3 年写到 `SYN26-U-*`。健康页 RFM 走 `user_rfm_precompute`（lookback 3650）。归档没有 `as_of <= 2023-07-06` 的 3650 快照，最近一档是 `2023-07-09`；脚本把该快照里的 fill 用户映射到 `2026-07-01`（Q3 起点）和 `2026-07-06`（合成窗口起点），last_pay +3 年。不要把 2026 RFM 抄给合成用户。`rfm_dashboard_full` 的 2026 Q3 分区本身不存在，健康页 Q3 会落到 precompute UNION。

`FQ_AUTH_IDLE_SECONDS`：后端回收无请求 token 的秒数。默认 `28800`（8 小时）。非法值回退默认。`0` 会被钳成 `1` 秒，不是关闭回收。前端 3 分钟踢人已关掉。

## 安装 / 重载（必做，否则 ~/Library/LaunchAgents 会指到已删路径）

```bash
cd /path/to/fuqing-crm-analytics
bash scripts/ops/install_launchagents.sh
```

该脚本会：

1. 校验 `scripts/launchd/*.plist` 含 `scripts/ops/`
2. `cp` → `~/Library/LaunchAgents/`
3. `launchctl bootout` + `bootstrap`（失败则 fallback load）

### 手工校验

```bash
# 每条 ProgramArguments[1] 必须存在且含 scripts/ops/
for f in ~/Library/LaunchAgents/com.fuqing.*monitor*.plist \
         ~/Library/LaunchAgents/com.fuqing.db-size-alert.daily.plist; do
  [ -f "$f" ] || continue
  script=$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:1' "$f")
  test -f "$script" && echo "OK $script" || echo "MISSING $script"
done

# dry-run（应打印 PASS/OK）
python3 scripts/ops/clickhouse_poc_monitor.py
```

`clickhouse_poc_monitor.py` 的 b/c 检查访问管理员端点，必须在部署机 `.env` 中：

1. 将独立 `monitor` 用户同时加入 `FQ_CRM_ADMINS` 与 `FQ_CRM_PASSWORDS`
2. 设置 `FQ_POC_MONITOR_ADMIN_USERNAME=monitor`
3. 确认该账号不供任何人登录后，设置
   `FQ_POC_MONITOR_DEDICATED_ACCOUNT=monitor`（值必须与第 2 步用户名相同）
4. 若 `FQ_CRM_PASSWORDS` 保存的是 bcrypt hash，再从安全部署环境注入
   `FQ_POC_MONITOR_ADMIN_PASSWORD` 明文；不得提交真实值

监控不得复用人工管理员账号，否则登录的单会话策略会踢出人工会话。配置缺失、
歧义或被管理员端点拒绝时脚本返回 2，不会把未执行的 b/c 检查误报成 PASS。

### 改路径后

任何把 monitor 移出 `scripts/ops/` 的改动，**同一 commit** 必须：

1. 更新 `scripts/launchd/*.plist`
2. 更新本 README + L4 规则中的路径
3. 跑 `bash scripts/ops/install_launchagents.sh`（本机）
4. 更新 `backend/tests/test_*_monitor.py` 路径
