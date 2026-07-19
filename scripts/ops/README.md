# scripts/ops — 跨 sprint 运维监控

Monitor scripts for launchd (local = production).

| Script | Plist label |
|---|---|
| `pre_existing_fail_monitor.py` | `com.fuqing.pre-existing-fail-monitor.weekly` |
| `memory_size_monitor.py` | `com.fuqing.memory-size-monitor.weekly` |
| `adhoc_query_hitrate_monitor.py` | `com.fuqing.adhoc-hitrate-monitor.weekly` |
| `clickhouse_poc_monitor.py` | `com.fuqing.clickhouse-poc-monitor.weekly` |
| `check_db_size.py` | `com.fuqing.db-size-alert.daily` |

**REPO_ROOT** = `Path(__file__).resolve().parents[2]`（文件在 `scripts/ops/`）。

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

### 改路径后

任何把 monitor 移出 `scripts/ops/` 的改动，**同一 commit** 必须：

1. 更新 `scripts/launchd/*.plist`
2. 更新本 README + L4 规则中的路径
3. 跑 `bash scripts/ops/install_launchagents.sh`（本机）
4. 更新 `backend/tests/test_*_monitor.py` 路径
