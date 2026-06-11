# ETL-CACHE-INVALIDATION — W5 cache invalidation ETL 末尾调

> Sprint 19 P2-4 任务: 加 `etl_post_run_hook()` 到 `backend/services/rfm/cache.py`, 在
> `scripts/etl/cli.py main()` 末尾调, 不依赖 uvicorn 重启也能 invalidate.
> 落地日期: 2026-06-11. 拍板人: subagent C3.

---

## 1. 拍板

| 维度 | 拍板 |
|---|---|
| **hook 名称** | `etl_post_run_hook()` (跟任务描述一致) |
| **集成位置** | `scripts/etl/cli.py main()` 末尾, 跑批成功 (PerfTimer 块跑完) 之后调 |
| **依赖** | 复用现有 `check_manifest_version_and_invalidate()` 启动 hook 逻辑, 不重复实现 |
| **state_path** | 复用 `FQ_W5KV_STATE_PATH` env 覆盖 (跟启动 hook 同一份 `w5kv_manifest_state.json`) |
| **失败处理** | best-effort, 异常被吞 + log warning + 返 False, 不阻塞 ETL 跑批结果 |
| **测试** | 加 `TestEtlPostRunHook` 4 个 case (manifest 变化 / 一致 / 缺失 / 异常) |

---

## 2. 跟启动 hook 互补

### 2.1 启动 hook (Sprint 18 #123)

**时机**: `main.py` lifespan startup 调.
**痛点解决**: 改 ratio/契约 → 重启 uvicorn → 启动 hook 自动对齐 manifest version → 12 keys 失效.
**局限**: uvicorn 未必在 ETL 跑完后立刻重启, 用户访问仍可能拿旧值.

### 2.2 post-run hook (Sprint 19 P2-4)

**时机**: `scripts/etl/cli.py main()` 末尾调.
**痛点解决**: ETL 跑完 → 主动调 hook → 不等 uvicorn 重启就 invalidate → 下次访问 miss 重算.
**跟启动 hook 关系**: 互补, 不互斥. 走同一份 state_path + 同一份 invalidate 逻辑.

### 2.3 时序图

```
[ETL 跑批前]
  manifest v=1, state=0
  cache 表有 12 keys (跟 v=1 数据对齐)
  uvicorn 跑着 (未重启), 用户访问拿 cache 命中值

[ETL 跑批中]
  写新数据到 parquet, manifest v=1 -> v=2, 写 data/processed/manifest.json

[post-run hook 触发]  ← Sprint 19 P2-4
  scripts/etl/cli.py main() 末尾调 etl_post_run_hook()
  → check_manifest_version_and_invalidate()
  → 读 manifest v=2 vs state v=0 → 不一致
  → DELETE FROM rfm_query_cache (12 rows 没了)
  → 写 state v=2

[用户访问 (uvicorn 还没重启)]
  cache.get('r-flow', ...) → miss
  → 触发重算 (新 v=2 数据) → 写 cache v=2
  → 返新值 (跟 manifest v=2 一致)

[uvicorn 重启 (后续运维)]
  启动 hook 跑 → manifest v=2 vs state v=2 → 一致 → no-op
  (不重复 invalidate, post-run hook 已做过)
```

---

## 3. 代码改动

### 文件 1: `backend/services/rfm/cache.py`

**新增 20 行** (跟任务描述一致):

```python
def etl_post_run_hook() -> bool:
    """ETL 跑批末尾调, 不依赖 uvicorn 重启也能 invalidate W5 cache.
    跟 check_manifest_version_and_invalidate 共享同一份 state_path,
    调用后状态文件同步 (跟启动 hook 行为一致). 失败被吞 + log warning,
    不阻塞 ETL 跑批结果 (best-effort, ETL 跑完是更重要的结果).
    """
    try:
        return check_manifest_version_and_invalidate()
    except Exception as e:  # noqa: BLE001
        logger.warning("W5 cache ETL post-run hook 失败 (不阻塞 ETL 收口): %s", e)
        return False
```

**设计要点**:
1. **复用启动 hook**: 单一源真值, 改 manifest 跟踪逻辑只改 1 处.
2. **异常兜底**: `try/except` 在 hook 内部 (跟启动 hook 同 best-effort 契约).
3. **return bool**: 跟启动 hook 契约一致, 返 True/False 给调用方做埋点/告警.

### 文件 2: `scripts/etl/cli.py`

**main() 末尾追加 8 行**:

```python
try:
    from backend.services.rfm.cache import etl_post_run_hook
    invalidated = etl_post_run_hook()
    print(f"W5 cache invalidation: {'invalidate 触发' if invalidated else 'no-op (manifest version 一致)'}")
except Exception as e:  # noqa: BLE001
    print(f"WARN: W5 cache etl_post_run_hook 失败 (不阻塞收口): {e}")
```

**设计要点**:
1. **放在 PerfTimer 块外**: PerfTimer 块跑完才调, 不污染跑批耗时统计.
2. **local import**: 跟 cli.py 其他 lazy import 风格一致, 避免 import time 副作用.
3. **print 提示**: 让 ops 看得到 invalidate 触发情况, 不只 log.

### 文件 3: `backend/tests/test_cache_invalidation.py`

**新增 `TestEtlPostRunHook` 类, 4 个 test case**:

1. `test_post_run_hook_manifest_changed_invalidates` — manifest 变化时触发 invalidate
2. `test_post_run_hook_manifest_unchanged_noop` — manifest 一致时 no-op
3. `test_post_run_hook_no_manifest_noop` — manifest 缺失时不报错
4. `test_post_run_hook_exception_does_not_propagate` — 异常被吞, 不抛

---

## 4. 验证

### 4.1 单测

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/test_cache_invalidation.py::TestEtlPostRunHook -v
```

预期: 4/4 passed.

### 4.2 真跑批验证 (生产 staging)

```bash
# 跑批前看 cache
PYTHONPATH="$(pwd)" python -c "
from backend.services.rfm.cache import RfmQueryCache
c = RfmQueryCache()
print('跑批前 cache:', c.stats())
"

# 跑批
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update

# 跑批后看 cache (应被 invalidate 清空)
PYTHONPATH="$(pwd)" python -c "
from backend.services.rfm.cache import RfmQueryCache
c = RfmQueryCache()
print('跑批后 cache:', c.stats())
"
```

预期: 跑批前 `total=12 valid=12`, 跑批后 `total=0`. 跑批日志最后 1 行 `W5 cache invalidation: invalidate 触发`.

### 4.3 跟启动 hook 联合验证

```bash
# 跑批后状态: state=v=N, manifest v=N, cache empty
# 重启 uvicorn: 启动 hook 跑 → manifest v=N vs state v=N → 一致 → no-op (正常)
# 后续访问: cache miss → 重算 → 写新 cache → 用户拿新值
```

预期: 启动 hook 跟 post-run hook 协同工作, 不重复 invalidate.

---

## 5. 故障排查

| 症状 | 原因 | 修法 |
|---|---|---|
| 跑批日志无 "W5 cache invalidation" 行 | post-run hook 没集成 (本地 import 失败) | 检查 cli.py main() 末尾 8 行是否到位 |
| 跑批日志 "W5 cache etl_post_run_hook 失败" | DuckDB connection 故障 / state 文件权限 | 看完整 traceback, 多数情况 best-effort 兜底不阻塞 ETL |
| 跑批后 cache 没清空 | post-run hook 调了但 manifest 没升 (etl 写 parquet 失败) | 修 ETL 跑批, post-run hook 只能 invalidate, 不能重算 |
| 跑批后 cache 清空但用户访问仍拿旧值 | uvicorn 进程内 `_ManifestTracker` 仍 hold 旧 `_last_seen_version` | 已知, 需 uvicorn 重启 (post-run hook 解决 90%, 启动 hook 兜底 10%) |

---

## 6. 后续 (Sprint 20+ 待办)

| # | 任务 | 备注 |
|---|---|---|
| 1 | post-run hook 加埋点 (Prometheus metric) | 监控 invalidate 触发频次 |
| 2 | post-run hook 跑批前/后打印 cache 统计对比 | 走 ops dashboard |
| 3 | 评估"uvicorn 进程内 _ManifestTracker 仍 hold 旧 version"问题 | 可能需要 inotify / file watcher 主动同步 |
| 4 | `etl_post_run_hook` 加 `force=False` 参数 | 给 ops 手动跑批 (skip manifest 检查) 用 |

---

**相关文档**:
- `backend/services/rfm/cache.py` (本 P2-4 改的文件)
- `scripts/etl/cli.py` (本 P2-4 改的文件)
- `backend/tests/test_cache_invalidation.py` (本 P2-4 加 test)
- Sprint 18 #123 — 启动 hook 原版
- Sprint 14.5 P1.4 — W5 cache key 12 keys 失效痛点
- `docs/SPRINT-18-PRE-COMMIT.md` — 跨进程持久化状态文件设计

**Sprint 19 P2-4 完成**: W5 cache invalidation ETL 末尾调, 跟启动 hook 互补, 4 test case 覆盖.
