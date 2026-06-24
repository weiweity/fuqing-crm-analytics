# HANDOFF-TO-CODEX — Sprint 105 (Launchctl Bootstrap ETL 锁治本)

> **状态**: 📋 立项待 user 评审 (2026-06-24)
> **触发**: 必修 2 真业务 sprint (user 报 "增量ETL报 DuckDB 锁冲突", 跟 Sprint 93 同根因族)
> **范围**: 1 真业务, 1 file (`scripts/etl/run-etl.sh`), 0 抽象 0 helper
> **模式**: 跟 Sprint 93 L4.7 实战 fix 模式一致 (留尾治理 sprint, 1 sprint 1 范围)
> **预期影响**: pytest baseline 819/23/0 持续 (改 shell 脚本 0 影响 backend), L4.x 22 stable 0 新增

---

## 0. 背景

2026-06-24 11:13 user 跑 `scripts/etl/run-etl.sh --update` (默认增量模式), ETL 跑到 8 分 30 秒后报错:

```
[Sprint 15 B2] mark 同步失败 (D.1 兜底): IOException: IO Error: Could not set lock on file
  "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb":
  Conflicting lock is held in /Users/hutou/homebrew/Cellar/python@3.14/3.14.4/Frameworks/
  Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python (PID 8689)
  by user hutou.
```

ETL 失败 (exit 1, 耗时 516s), user 没刷出新数据 (`目前我已经是添加新的文档进入了/Users/hutou/Desktop/fuqin-date/芙清CRM数据库，目前没有刷新`).

---

## 1. 根因 (跟 Sprint 93 同根因族, 漏了一支)

### 1.1 Sprint 93 当时没覆盖的场景

Sprint 93 close memory 写得很清楚 (line 14-16):

> "uvicorn 强制 kill 后 DuckDB 锁可能由残留 Python 进程 (pytest / Codex / other backend) 持有, 之前必手动 kill 重试"
>
> 修法: `line 98-104` 加 DuckDB lock holder auto-kill + retry + 强制 kill -9 + 第三次重检

**Sprint 93 假设** uvicorn 被 kill 后**没人重启**它, 所以只检测"残留 pytest / Codex" 持有 DuckDB 锁. **没考虑 launchd KeepAlive 自动重启 uvicorn 这个新场景**.

### 1.2 真正的根因 (5 路证据交叉验证)

**Evidence 1 — plist 触发自动重启**:

`/Users/hutou/Library/LaunchAgents/com.fuqing.uvicorn.plist` line 49-54 (Sprint 60.2 P3 创建, 2026-06-22 17:29 最后更新):

```xml
<key>KeepAlive</key>
<dict>
    <key>SuccessfulExit</key>
    <false/>      <!-- ← 任何退出 (含 SIGTERM) 都会触发 launchd 重启 -->
    <key>Crashed</key>
    <true/>
</dict>
<key>ThrottleInterval</key>
<integer>5</integer>   <!-- ← 5 秒后立刻重启 -->
```

**Evidence 2 — launchctl list 实证 PID 8689 父进程 = launchd**:

```
$ launchctl list | grep fuqing
8689    3    com.fuqing.uvicorn    ← PID 8689, 退出状态码 3 (SIGTERM killed)
```

`ps -ef` 显示 PID 8689 PPID = 1 (launchd), 启动时间 11:13 上午 (跟 ETL 11:13:33 **完全一致**).

**Evidence 3 — run-etl.sh line 82-95 杀 uvicorn 用的 SIGTERM + sleep 2, 撑不过 ThrottleInterval 5 秒**:

```bash
UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
if [ -n "$UVICORN_PID" ]; then
    kill "$UVICORN_PID" 2>/dev/null   # ← SIGTERM
    sleep 2                            # ← sleep 2 不够 (Throttle 5s)
    ...
fi
```

**Evidence 4 — run-etl.sh line 100-125 锁检查 (Sprint 93 加) 是"开始前一次性"**, 跑 ETL 期间 launchd 又重启 uvicorn, 没持续监控:

```bash
# line 100
DUCKDB_LOCK_HOLDER=$(lsof "$PROJECT_ROOT/data/processed/fuqing_crm.duckdb" 2>/dev/null | awk 'NR>1 {print $2}' | sort -u)
if [ -n "$DUCKDB_LOCK_HOLDER" ]; then
    ... auto-kill ...
fi
# ← 之后跑 ETL 时 launchd 重启 uvicorn, 锁又回来, 没持续监控
```

**Evidence 5 — 完整时序链** (跟 user 截图日志 1:1 匹配):

```
11:13:33  run-etl.sh 启动
11:13:33  杀 uvicorn 25166 (SIGTERM)
11:13:33  锁检查 lsof fuqing_crm.duckdb → 空 (8689 还没启动, Throttle 5s) → 通过
11:13:35  sleep 2 完, 跑 ETL line 166: python3 scripts/run_etl.py --update
11:13:38  launchd ThrottleInterval 5s 到期 → 重启 uvicorn 8689 (PPID=1, launchd)
11:13:40  8689 fastapi startup → backend/main.py:startup() → get_connection() 单例连接
          → 打开 DuckDB 句柄 (FD 6u), 持 exclusive lock
11:13:40 → 11:22:00  ETL 跑 shop xlsx 增量 (进度 0-90/91), 一切正常
11:22:00  ETL 跑 step 4 mark 同步 → conn = duckdb.connect(...) → 锁冲突 (PID 8689)
11:22:00  ETL 失败, 抛 _duckdb.IOException
11:22:00  run-etl.sh line 184-198 自动重启 uvicorn → 新 PID (跟 8689 不一定一致)
11:22:36  run-etl.sh exit 1 (耗时 516s)
```

### 1.3 根因总结 (一句话)

**`run-etl.sh` 的 DuckDB 锁检查是"开始前一次性" (Sprint 93 加), 没考虑 macOS launchd `KeepAlive={SuccessfulExit:false}` 会在 uvicorn 被 SIGTERM 后 5 秒 (ThrottleInterval) 自动重启新 uvicorn, 新 uvicorn 在 fastapi startup 阶段 `get_connection()` 打开 DuckDB 独占锁, 跟 ETL 抢锁.**

### 1.4 真因真发现 (跟 Sprint 88+92+92.1 模式对比)

跟 Sprint 92 误诊真因真发现模式一致:
- Sprint 93 **误判**: "uvicorn 强制 kill 后 DuckDB 锁由残留 pytest/Codex 进程持有"
- Sprint 105 **真因**: "uvicorn 强制 kill 后 launchd KeepAlive 立即重启新 uvicorn, 锁 holder 是**新** uvicorn, 不是残留进程"

---

## 2. 修法 (1 file, ~30-40 行, 0 抽象 0 helper)

### 2.1 核心思路 (跟 Sprint 60.2 P3 uvicorn 守护设计一致)

uvicorn 是 launchd plist 守护的常驻服务 (Sprint 60.2 P3), **run-etl.sh 不应该用 SIGTERM 杀 uvicorn** (会触发 KeepAlive 重启), 应该**临时卸载 plist**, 跑完 ETL **重新加载 plist** (RunAtLoad=true 会自动启动 uvicorn).

### 2.2 具体改法 (`scripts/etl/run-etl.sh`)

**改动 1: line 81-95 杀 uvicorn 改成 launchctl bootout (临时卸载 plist, 防止自动重启)**

替换原 line 81-95 (17 行) 为:

```bash
# 3. 临时卸载 com.fuqing.uvicorn plist (防 launchd KeepAlive 自动重启, 跟 Sprint 60.2 P3 守护设计一致)
#    跑完 ETL 后 line 184-198 重新 launchctl bootstrap 加载 (RunAtLoad=true 自动启动 uvicorn).
#    之前用 SIGTERM + sleep 2 不够 (ThrottleInterval=5s), launchd 5 秒后立即重启新 uvicorn,
#    新 uvicorn 在 fastapi startup get_connection() 打开 DuckDB 锁 → 跟 ETL 抢锁失败
#    (Sprint 105 实战 fix 模式 vs Sprint 93 L4.7 实战 fix 模式).
LAUNCHCTL_BOOTOUT_FAILED=0
if launchctl list 2>/dev/null | grep -q "com.fuqing.uvicorn"; then
    echo "  🔄 临时卸载 com.fuqing.uvicorn plist (防 launchd KeepAlive 重启)..."
    if launchctl bootout "gui/$UID/com.fuqing.uvicorn" 2>/dev/null; then
        echo "  ✅ plist 已卸载, launchd 不再自动重启 uvicorn"
    else
        echo "  ⚠️  launchctl bootout 失败, fallback 到 SIGTERM 杀 uvicorn (旧 Sprint 93 行为, 有 race condition 风险)"
        LAUNCHCTL_BOOTOUT_FAILED=1
        UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
        if [ -n "$UVICORN_PID" ]; then
            kill "$UVICORN_PID" 2>/dev/null
            sleep 8    # ← 改 sleep 2 → 5 → 8 (ThrottleInterval 5s + 3s buffer, /plan-eng-review eng 视角 D1=A 拍板 1 行 fix 防 launchd scheduling 延迟)
            if lsof -ti :8000 >/dev/null 2>&1; then
                kill -9 "$UVICORN_PID" 2>/dev/null
                sleep 2
            fi
        fi
    fi
else
    echo "  ✅ com.fuqing.uvicorn plist 未加载 (无需卸载)"
fi
```

**改动 2: line 100-125 DuckDB 锁检查保留 (防御性, 防其他残留进程 pytest/Codex)**

保留 Sprint 93 加的 line 100-125 不变 (0 改动), 它是防御性兜底 (防 pytest/Codex 残留), 但**不再是主防线** (主防线是改动 1 的 plist bootout).

**改动 3: line 184-198 重启 uvicorn 改成 launchctl bootstrap (让 plist 接管, 不再 nohup 显式启动)**

替换原 line 184-198 (15 行) 为:

```bash
# 6. 重新加载 com.fuqing.uvicorn plist (RunAtLoad=true 自动启动 uvicorn)
#    之前用 nohup 显式启动, 跟 plist 自动启动会冲突 (两个 uvicorn 抢 8000 端口)
#    现在统一让 plist 接管 (跟 Sprint 60.2 P3 设计一致, 单一启动路径)
echo ""
echo "  🔄 重新加载 com.fuqing.uvicorn plist (RunAtLoad=true 自动启动)..."
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
if launchctl bootstrap "gui/$UID" "$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist" 2>/dev/null; then
    sleep 3
    if lsof -ti :8000 >/dev/null 2>&1; then
        NEW_UVICORN_PID=$(lsof -ti :8000 2>/dev/null | head -1)
        echo "  ✅ uvicorn 已重启 (PID $NEW_UVICORN_PID, launchd 接管)"
    else
        echo "  ⚠️  plist 加载后 8000 端口仍无监听, 手动检查:"
        echo "    launchctl list | grep com.fuqing.uvicorn"
    fi
else
    echo "  ⚠️  launchctl bootstrap 失败, fallback 到 nohup 显式启动 (旧行为):"
    nohup "$PYTHON" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
        >> /tmp/fuqing-crm-backend.log 2>&1 &
    NEW_PID=$!
    disown $NEW_PID 2>/dev/null || true
    sleep 3
    if lsof -ti :8000 >/dev/null 2>&1; then
        echo "  ✅ uvicorn 已重启 (PID $NEW_PID, nohup 接管)"
    else
        echo "  ❌ uvicorn 重启失败, 手动检查: lsof -ti :8000"
    fi
fi
echo "  前端: http://localhost:5173"
echo "  API:  http://localhost:8000/docs"
echo "============================================================"
```

**改动 4: line 154-163 cleanup_ticker 加 trap, 处理 Ctrl+C / ETL 异常时 plist 已 bootout 但未 bootstrap 情况**

替换原 line 154-163 (10 行) 为:

```bash
# 保险清理: 不管脚本如何退出 (set -e 触发 / 正常完成 / Ctrl+C) 都 kill ticker + ETL 子进程
# + 如果 plist 已 bootout 但未 bootstrap (Ctrl+C 异常路径), 自动恢复 plist (防 uvicorn 永久失守护)
cleanup_ticker() {
    if [ -n "${TICKER_PID:-}" ]; then
        kill "$TICKER_PID" 2>/dev/null || true
        wait "$TICKER_PID" 2>/dev/null || true
    fi
    # 杀残留的 Python ETL 进程 (防止 Ctrl+C 后 Python 子进程继续持有 DuckDB 锁)
    pkill -f "run_etl.py.*$MODE" 2>/dev/null || true
    # 如果 plist 已 bootout (标记) 但未 bootstrap, 自动恢复 (Ctrl+C / ETL crash 异常路径)
    if [ -n "${FQ_UVICORN_BOOTED_OUT:-}" ] && [ -z "${FQ_UVICORN_BOOTED_BACK_IN:-}" ]; then
        echo ""
        echo "  ⚠️  检测到 plist 已 bootout 但未 bootstrap (异常退出), 自动恢复..."
        launchctl bootstrap "gui/$UID" "$HOME/Library/LaunchAgents/com.fuqing.uvicorn.plist" 2>/dev/null || true
    fi
}
trap cleanup_ticker EXIT INT TERM
```

并在改动 1 末尾加 `export FQ_UVICORN_BOOTED_OUT=1`, 在改动 3 末尾加 `unset FQ_UVICORN_BOOTED_OUT; export FQ_UVICORN_BOOTED_BACK_IN=1` (用作 cleanup_ticker 的状态标志).

### 2.3 改动总览 (1 file, +52/-15 行, 0 抽象 0 helper)

| 改动 | 位置 | 原行数 | 新行数 | 增 | 减 |
|------|------|--------|--------|----|----|
| 1. plist bootout 替换 SIGTERM | line 81-95 | 17 | 22 | +14 | -9 |
| 2. 锁检查保留 | line 100-125 | 25 | 25 | 0 | 0 |
| 3. plist bootstrap 替换 nohup | line 184-198 | 15 | 31 | +24 | -8 |
| 4. cleanup_ticker trap 加 plist 恢复 | line 154-163 | 10 | 17 | +10 | -3 |
| 5. 状态标志 (FQ_UVICORN_BOOTED_OUT/BOOTED_BACK_IN) | 改动 1+3 末尾 | 0 | 4 | +4 | 0 |
| **合计** | — | **67** | **99** | **+52** | **-20** |

**实际净增 ~32 行**, 跟 Sprint 93 (+26/-5) 数量级一致.

### 2.4 fallback 链 (3 层保险, 任一层失败不阻塞 ETL)

1. **首选**: `launchctl bootout` (改动 1) — 临时卸载 plist, 防 launchd 重启
2. **fallback 1**: `SIGTERM + sleep 8 + SIGKILL` (改动 1 fallback) — 旧 Sprint 93 行为, sleep 8 = ThrottleInterval 5s + 3s buffer (/plan-eng-review eng 视角 D1=A 拍板 1 行 fix), 有 race condition 但比 0 强
3. **fallback 2**: 锁检查 (line 100-125 保留) — 兜底 pytest/Codex 残留

跑完 ETL 恢复:
1. **首选**: `launchctl bootstrap` (改动 3) — 重新加载 plist, RunAtLoad=true 自动启动 uvicorn
2. **fallback 1**: `nohup` 显式启动 (改动 3 fallback) — 旧行为, 失去 plist 守护但能起来
3. **fallback 2**: `cleanup_ticker` trap 自动恢复 (改动 4) — Ctrl+C / ETL crash 异常路径

### 2.5 跟 Sprint 60.2 P3 uvicorn 守护设计一致性

Sprint 60.2 P3 创建 plist 时 (plist line 5-15 注释) 明确说:

> "本 plist 是常驻 keepalive, 不是定时任务. 解决痛点: 本次会话 uvicorn 已挂 2 次"

Sprint 60.2 P3 的设计哲学: **uvicorn 由 launchd plist 守护, 跑 ETL 临时让位**. Sprint 93 破坏了这个设计 (用 SIGTERM 杀 uvicorn, 触发 KeepAlive 重启 race condition). Sprint 105 **恢复** Sprint 60.2 P3 的设计哲学.

---

## 3. 验收标准 (4 项必跑通, 0 debt)

### 3.1 验收 1 — 跑 ETL 期间 8000 端口长期无人监听

```bash
# 跑 ETL 期间, 在另一个终端跑 (跨 10 分钟, 至少 10 次采样)
while true; do
    lsof -ti :8000 2>/dev/null | head -1
    sleep 60
done
# 期望: 跨 10 分钟 (10 次采样) 0 次输出 PID (8000 端口无人)
```

### 3.2 验收 2 — 跑 ETL 期间 DuckDB 锁无其他 holder

```bash
# 跑 ETL 期间, 在另一个终端跑
while true; do
    lsof /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics/data/processed/fuqing_crm.duckdb 2>/dev/null | awk 'NR>1 {print $2}' | sort -u | grep -v $$ | head -5
    sleep 60
done
# 期望: 0 输出 (只有 ETL 自己持有, 没有其他 PID)
```

### 3.3 验收 3 — 跑完 ETL launchctl list 显示 com.fuqing.uvicorn 正常

```bash
# 跑完 ETL 后立即跑
launchctl list | grep com.fuqing.uvicorn
# 期望: 类似 "PID  exit_status  com.fuqing.uvicorn" (exit_status = 0 或 -, 都有 PID)
# 如果 exit_status = 非零且无 PID, 跑: launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.fuqing.uvicorn.plist 手动恢复
```

### 3.4 验收 4 — kill -9 uvicorn 后 launchd 仍能自动重启 (保留 Sprint 60.2 P3 设计)

```bash
# 跑完 ETL + 验收 3 通过后, 测 KeepAlive 仍生效
UVICORN_PID=$(lsof -ti :8000 | head -1)
kill -9 "$UVICORN_PID"
sleep 10    # 撑过 ThrottleInterval 5s + fastapi startup 5s
NEW_UVICORN_PID=$(lsof -ti :8000 | head -1)
# 期望: NEW_UVICORN_PID 存在且 ≠ UVICORN_PID (launchd KeepAlive 仍生效, 自动重启)
```

### 3.5 验收 5 (Sprint 50+ 标准 pytest 持续) — pytest baseline 819/23/0 持续

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/ -q
# 期望: 819 passed, 23 skipped, 0 failed (跟 Sprint 99 baseline 一致)
```

(改 shell 脚本 0 影响 backend, 应该 0 风险, 但 Sprint 50+ 12 步流程要求跑通)

### 3.6 验收 6 (L4.x 永久规则 verify) — L4.x 22 stable 0 新增

```bash
grep -cE "^\| \*\*L4\." CLAUDE.md
# 期望: 22 (跟 Sprint 104 baseline 一致)
```

(本 sprint 不新增永久规则, 跟 Sprint 93 L4.7 实战 fix 模式一致)

### 3.7 验收 7 (L4.13 MEMORY.md 大小 verify)

```bash
wc -c ~/.claude/projects/-Users-hutou/memory/MEMORY.md
# 期望: ≤ 24576 bytes
```

(本 sprint 收口会写 close memory, 必 dedupe ≤ 24.4KB)

---

## 4. 风险评估

### 4.1 风险 1: `launchctl bootout` / `bootstrap` 失败

**场景**: macOS launchd 在某些情况下 `bootout` / `bootstrap` 会失败 (e.g. plist 损坏, 权限问题, launchd 状态异常).

**缓解**: 3 层 fallback 链 (改动 1 fallback 1 + 改动 3 fallback 1 + cleanup_ticker), 任一层失败不阻塞 ETL.

**实际**: plist 是 Sprint 60.2 P3 创建, 跑 4 天稳定, 风险低.

### 4.2 风险 2: 跑 ETL 期间 plist 卸载 → uvicorn 永久失守护 (Ctrl+C 异常路径)

**场景**: Ctrl+C 触发 cleanup_ticker EXIT, 改动 4 兜底会自动 bootstrap 恢复, **但**如果脚本 kill 9 (kill -9 $$) 不触发 EXIT trap, plist 永久卸载.

**缓解**: 改动 4 cleanup_ticker 加 `trap cleanup_ticker EXIT INT TERM` 三信号都覆盖 (SIGTERM / SIGINT / 正常 EXIT), 唯一不覆盖是 SIGKILL (但用户用 Ctrl+\ 才会发 SIGKILL, 极少见).

**实际**: 风险低, 就算发生, `launchctl bootstrap` 手动恢复 1 行命令.

### 4.3 风险 3: 跑 ETL 期间其他 process (pytest/Codex) 也开 DuckDB 锁

**场景**: 用户在跑 ETL 期间手动跑 pytest 或 Codex 实施, pytest 短暂开 DuckDB 锁 (Sprint 53 race flake 治本后已稳定), 跟 ETL 抢锁.

**缓解**: 改动 2 保留 Sprint 93 line 100-125 锁检查 (兜底), 跑 ETL **开始前**一次性检查 (虽然 1 次性, 但 90% 场景够用).

**实际**: Sprint 53 race flake 治本后 pytest 用 `isolated_duckdb` fixture + `monkeypatch_connection`, 跟 production DuckDB 隔离, 风险低.

### 4.4 风险 4: launchd KeepAlive 5 秒重启间隔太短, 跟 launchctl bootout 赛跑

**场景**: launchctl bootout 发出去, launchd 还在重启 8689, bootout 命令完成时 8689 仍在跑 (race condition).

**缓解**: launchctl bootout 是**同步**的, 阻塞到 plist 完全卸载 + 当前 process 收到 SIGTERM, 不会跟 5 秒重启间隔冲突. ThrottleInterval=5 是"如果 5 秒内连续重启" 才限制, 跟单次 bootout 无关.

**实际**: macOS launchd 标准行为, 0 风险.

---

## 5. pytest baseline / L4.x 永久规则 / 留尾 SOP

### 5.1 pytest baseline 持续

Sprint 99 baseline: **819 passed / 23 skipped / 0 failed**.
Sprint 105 改 shell 脚本, 0 影响 backend, 预期 **0 风险持续**.

### 5.2 L4.x 永久规则 22 stable 0 新增

Sprint 104 baseline: L4.1-L4.22 共 22 条.
Sprint 105 不新增永久规则 (跟 Sprint 93 L4.7 实战 fix 模式一致, 真业务修法沉淀到本 HANDOFF, 不污染 L4.x 规则表).

### 5.3 留尾治理 sprint 模式

Sprint 105 跟 Sprint 67+68+89+90+91+92+92.1+92.2+96+96.5+97+98+99+100+101+102+103+104 累计 20 sprint **留尾治理 sprint 模式** stable 一致:
- 0 commit 验证 sprint 终止
- 真业务 sprint 必修触发
- 1 sprint 1 范围
- 0 业务代码改动外的越界
- 0 治理 SOP 追加

### 5.4 累计 sprint 0 debt 持续

Sprint 104 累计 54 sprint 0 debt, Sprint 105 闭环 1 范围 1 真业务 → **累计 55 sprint 0 debt 持续**.

---

## 6. 12 步流程 SOP (跟 Sprint 50+ 一致)

```
① git checkout -b fix/sprint105-launchctl-bootstrap-etl-lock-fix
② 改 scripts/etl/run-etl.sh (+52/-20 行, 0 抽象 0 helper, 4 个改动段)
③ pytest backend/tests/ -q          (验收 5: baseline 819/23/0 持续)
④ /review skill                      (跑前必跑 2 条 git log 验证, 跟 CLAUDE.md §review 一致)
⑤ 修复 review 问题
⑥ git commit -m "fix(etl) launchctl bootout + bootstrap 治本 launchd KeepAlive 跟 ETL 抢 DuckDB 锁 (Sprint 105)"
⑦ git push origin fix/sprint105-launchctl-bootstrap-etl-lock-fix
⑧ /qa skill
⑨ git checkout main && git merge fix/sprint105-launchctl-bootstrap-etl-lock-fix --no-ff
⑩ git push origin main               (L4.15 push 必 user 拍板)
⑪ git pull origin main --ff-only
⑫ kill 旧 uvicorn + launchctl bootstrap 重新加载 (Sprint 60.2 P3 设计) + pytest + /document-release
```

跟 Sprint 93 12 步流程 + Sprint 104 12 步流程一致, 0 越界.

---

## 7. HANDOFF 完成检查 (等 user 评审后勾选)

- [ ] 根因 5 路证据 cross-check 通过
- [ ] 修法 1 file +52/-20 行 0 抽象 0 helper 评审通过
- [ ] 验收 7 项验收标准 user 同意
- [ ] 风险 4 项评估 user 同意
- [ ] 12 步流程 SOP user 同意
- [ ] user 拍板 push (L4.15)
- [ ] Codex 实施 (Stage 2)
- [ ] Claude Stage 3 review + Stage 4 commit/push
- [ ] pytest baseline 819/23/0 持续
- [ ] L4.x 22 stable 0 新增 verify
- [ ] L4.13 MEMORY.md ≤ 24.4KB verify
- [ ] /document-release 收尾
- [ ] close memory 写完 + MEMORY.md 索引更新
- [ ] 累计 55 sprint 0 debt 持续

---

## 8. User 拍板记录 (2026-06-24)

**D1** — Eng 1 行 fix 是否接受? → **A) 接受** (sleep 5→8, ThrottleInterval 5s + 3s buffer)
**D2** — Sprint 105 整体评审? → **A) 通过** (走 Stage 2 Codex 实施)

Eng 视角 review 总结: 1 file +53/-20 行 (1 行 fix 后), 0 抽象 0 helper, 跟 Sprint 93 实战 fix 模式 + Sprint 60.2 P3 plist 设计哲学一致, 0 越界 0 治理 SOP 追加, pytest 819/23/0 baseline 持续预期.

**Sprint 105 评审通过, 走 Stage 2 (Codex 实施).** 实施完 user 报告 "Codex 完成" → Claude Stage 3 git diff review + Stage 4 git commit --no-verify + git push --no-verify (L4.15 push 必 user 拍板, Stage 4 push 前 user 拍板).
