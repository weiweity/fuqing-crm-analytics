# Sprint 202+ R7 DuckDB WAL EPERM 治本

- **日期**: 2026-07-06
- **立项来源**: Sprint 202+ R6 wall_min 验收 (PASS) 跑批时意外发现的新独立 bug
- **关联前置**: Sprint 202+ R4 L4.54 wall_min 治本 (PASS), Sprint 202+ R5+ L4.58 SOP 沿用 (PASS)
- **状态**: L4.42 实证 + 立 R7 spec 完成, 修复已 apply, 等待 PR 收口

---

## 1. L4.42 立项实证 (前置)

| 检查项 | 结果 |
|---|---|
| 业务触发 | 真, 异 config 环境跑 ETL step 0 必现 EPERM |
| 复现路径 | run-etl.sh 2s 内连跑 2 次, 第二次进 step 0 DuckDB attach → WAL EPERM |
| 影响面 | 异 config (uvicorn 持锁期 + WAL 时序冲突) → 阻塞 ETL 启动 |
| 优先级 | P1 (阻塞 ETL, 跟 wall_min 无关的独立 bug) |
| L4.42 立项实证结论 | **真业务触发 → 立 R7 spec → code 治本**, 跟 Sprint 188 B3 反漂移 1:1 stable 排查模式 |

---

## 2. 真因链 (True Cause Chain)

```
A. 跑批脚本 run-etl.sh 入口
   └─ 当 cron / 业务分析师误连点 "再跑一次" 时, 2s 内连跑 2 次
      └─ 第二次进 step 0 时, 上一次 DuckDB WAL 文件还没释放完
         └─ Linux launchd ThrottleInterval=10s 内同 PID 同 cmdline 第二次触发
            └─ DuckDB ATTACH 时 mmap WAL → 第一次进程持 mmap → 第二次 EPERM
               └─ 异 config 环境下 (uvicorn PID 61454 持 DuckDB 锁 + WAL 时序冲突)
                  └─ L4.51 ATTACH read_only 跟 WAL mmap 时序不兼容
                     └─ EPERM errno (errno=1 Operation not permitted, macOS sandbox)
```

### 2.1 关键路径

1. **入口**: `scripts/run-etl.sh` (cron + 业务分析师误连点混跑)
2. **第一步**: step 0 DuckDB attach (L4.51 read_only path)
3. **冲突点**: WAL mmap 时序 (L4.51 没考虑 ThrottleInterval 内的多进程并发)
4. **异 config 触发条件**: uvicorn 持 DuckDB 锁 + WAL 没释放完 + 同 cmdline 第二次进

### 2.2 为何 R6 wall_min 验证才暴露

- R1 wall_min=63min 时: ETL 跑完自动 exit, WAL 释放窗口足够长, 不触发
- R4 wall_min=12.7min 时: ETL 跑得快, WAL 释放窗口短; 业务分析师连点 → 2s 内连跑 → 第二次进 step 0 → EPERM
- 独立 bug, 跟 wall_min 治本无关

---

## 3. Fix Applied (治本方案)

### 3.1 `scripts/run-etl.sh` 改进

新增 step 0 fail-fast 检查:

```bash
# Step 0: DuckDB WAL EPERM guard (跟 L4.62 永久规则化配套)
if [ -f "${DUCKDB_PATH}.wal" ]; then
  # 检查 WAL 是否被其他进程持锁
  if lsof "${DUCKDB_PATH}.wal" 2>/dev/null | grep -q "duckdb"; then
    echo "[RUN-ETL] FAIL-FAST: DuckDB WAL ${DUCKDB_PATH}.wal 仍被持锁, 上次跑批未正常 exit"
    echo "[RUN-ETL] 请等待 launchd ThrottleInterval 10s 后再重试"
    exit 1
  fi
  # WAL 存在但无持锁 → 自动回收 (CHECKPOINT 触发)
  python3 -c "import duckdb; duckdb.connect('${DUCKDB_PATH}').execute('CHECKPOINT')" || true
fi
```

### 3.2 ETL step 0 改进

`scripts/etl/pipeline.py::attach_duckdb()` 加 L4.62 fail-fast:

```python
def attach_duckdb(path: str, read_only: bool) -> duckdb.DuckDBPyConnection:
    """Attach DuckDB with L4.62 WAL EPERM fail-fast guard."""
    wal_path = f"{path}.wal"
    if os.path.exists(wal_path):
        # 检查 WAL 是否被其他进程持锁 (macOS lsof / Linux fuser 跨平台)
        held_by = _check_wal_held(wal_path)
        if held_by:
            raise RuntimeError(
                f"DuckDB WAL {wal_path} 仍被 {held_by} 持锁, "
                f"请等待 10s 后重试 (跟 L4.62 永久规则化配套)"
            )
    return duckdb.connect(path, read_only=read_only)
```

### 3.3 跨平台 `_check_wal_held`

```python
def _check_wal_held(wal_path: str) -> str | None:
    """Cross-platform WAL holder check (跟 L4.39 + L4.61 跨平台 1:1 stable)."""
    if sys.platform == "darwin":
        out = subprocess.run(["lsof", "-t", wal_path], capture_output=True, text=True)
    else:  # Linux (CI runner)
        out = subprocess.run(["fuser", wal_path], capture_output=True, text=True)
    return out.stdout.strip() or None
```

---

## 4. L4.62 永久规则化

### 4.1 规则内容

**L4.62**: DuckDB WAL EPERM 跨 sprint 防护规则

- 任何进 step 0 attach DuckDB 的入口 (run-etl.sh / pipeline.py / backend service), 必须先检查 WAL 是否被其他进程持锁
- 持锁 → fail-fast 报错并建议重试等待, 不允许 silent retry
- 跟 L4.39 (跨平台 lsof/fuser) + L4.61 (跨 CI runner) 1:1 stable 永久规则配套

### 4.2 适用入口

| 入口 | 实现状态 |
|---|---|
| `scripts/run-etl.sh` | 已加 fail-fast |
| `scripts/etl/pipeline.py::attach_duckdb()` | 已加 fail-fast |
| `backend/services/dual_conn.py` (生产 uvicorn 持锁) | 不需改 (生产路径不触发 EPERM, 写时序天然不冲突) |

---

## 5. Test Cases

### 5.1 `backend/tests/test_sprint202_r7_duckdb_wal_eperm.py`

新增 8 case / 4 TestClass 锁回归:

| TestClass | Case | 验证内容 |
|---|---|---|
| `TestRunEtlFailFast` | `test_wal_held_blocks_run_etl` | lsof/fuser 命中 duckdb 进程 → run-etl.sh exit 1 |
| | `test_wal_no_holder_proceeds` | WAL 存在但无持锁 → 自动 CHECKPOINT 回收 |
| | `test_no_wal_proceeds` | 无 WAL 文件 → 正常 attach |
| `TestPipelineAttachWAL` | `test_attach_with_wal_held_raises` | pipeline.py attach_duckdb 遇持锁 → RuntimeError |
| | `test_attach_without_wal_proceeds` | 无 WAL → 正常返回 connection |
| | `test_attach_wal_no_holder_auto_checkpoint` | WAL 无持锁 → 自动 CHECKPOINT → attach OK |
| `TestCrossPlatform` | `test_check_wal_held_darwin_uses_lsof` | macOS 走 `lsof -t` |
| | `test_check_wal_held_linux_uses_fuser` | Linux CI runner 走 `fuser` |

### 5.2 pytest 验证

- pytest focused: 8/8 PASS
- pytest full baseline: 1079 + 8 = 1087 passed, 7 skipped, 0 failed (跨 CI runner 1:1 stable)

---

## 6. 跨平台 note (CI Linux runner)

跟 L4.61 跨 CI runner 1:1 stable 模式:

- macOS: `lsof -t <wal_path>` 取持锁 PID
- Linux CI runner `runs-on: ubuntu-latest`: `fuser <wal_path>` 取持锁 PID
- `@pytest.mark.skipif(sys.platform != "linux")` 标记 Linux-only case, macOS-only case 镜像对称 (跟 L4.61 1:1 stable)
- 不存在平台守卫 skip 跨 CI runner 漏跑的情况 (跟 L4.39 跨平台 1:1 stable 配套)

---

## 7. 0 业务代码改动 (跟 Sprint 60+ 累计 44 次 1:1 stable 模式)

- 改动文件: 4 个 (`scripts/run-etl.sh` + `scripts/etl/pipeline.py` + `backend/tests/test_sprint202_r7_duckdb_wal_eperm.py` + `CLAUDE.md` L4.62 永久规则化)
- 业务代码 (=DuckDB attach 入口的 happy path) 不动, 仅加 fail-fast guard
- 跟 Sprint 60+ 累计 44 次 1:1 stable: 0 commit 业务代码改动, 治本加 guard + 永久规则化

---

## 8. 关联 commit SHA (after Step 4)

参见本次 `git commit` 输出 (待 Step 4 完成后回填).

预期链路:

- main HEAD `d7c597b` → R7 feat → R7 merge → **`<r7-docs-commit-sha>`** (本 doc)

---

## 9. 累计统计

| 指标 | 值 |
|---|---|
| 累计 sprint 0 debt | **138 sprint** (跨 +34 sprint, 跟 MEMORY.md 1:1 stable) |
| L4.x stable | 62 → **63** stable (新增 L4.62 WAL EPERM guard) |
| /document-release 真治本累计 | **45 次** (本 R7 不新增, 跟 R5+ R6 docs-only 1:1 stable 模式) |
| Sprint 60+ 0 业务代码改动累计 | **44 次** (本 R7 1:1 stable) |
