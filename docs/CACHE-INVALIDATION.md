# W5 Cache Invalidation 启动 Hook (Sprint 18 #123)

> **TL;DR**: 改 ratio/契约后必须手动 invalidate W5 DuckDB-KV cache (12 keys) 的痛点
> 已闭环。Sprint 18 #123 加了启动 hook, uvicorn 重启时自动对齐 manifest version,
> 不一致 → 整表清空 12 orphan keys. **不再需要手动跑 SQL**。

| 字段 | 值 |
| --- | --- |
| 任务来源 | Sprint 14.5 留 (Sprint 17 retrospective Section 4 #4) |
| 优先级 | 🟡 P1 |
| 改动文件 | `backend/services/rfm/cache.py` (新函数) + `backend/main.py` (lifespan) + `backend/services/rfm/_shared.py` (`FLOW_ALGO_VERSION` bump) |
| 新增文件 | `backend/tests/test_cache_invalidation.py` (10 tests) + 本文档 |
| CHANGELOG | v0.4.14.47 |
| 行为变化 | `FLOW_ALGO_VERSION` `v0.4.14.35` → `v0.4.14.47` (cache key 全 miss 一次, 后续重算) |

---

## 1. 背景 (Why)

### 1.1 痛点 (Sprint 14.5 留)

`backend/services/rfm/cache.py` W5 DuckDB-KV 缓存 (v0.4.13) 设计要点:
- 进程内 `_ManifestTracker` 跟踪 manifest version
- `cache.get()` 每次都检测 manifest 变化, 不一致 → 整表清空

**问题**: `_ManifestTracker._last_seen_version` 是**进程内**状态, uvicorn 重启时:
- 第一次 `ensure_table()` 调时, `_last_seen_version` 从 None → 设为当前 manifest version
- **不**触发 invalidate (现有设计: 避免空表清空浪费)
- 但**实际**表里**可能有** 12 orphan keys (来自上次部署 / DuckDB 备份 / etcd 同步)
- 这些 orphan keys 24h TTL 过期前**永远占空间**且**永不被命中** (新 algo_version key 不同)

**场景**: 改 ratio/契约后, 开发者:
1. 改完代码
2. 跑 ETL (manifest version 升)
3. 重启 uvicorn
4. 启动时**不** invalidate, 12 keys 留在表里
5. 跑 4 端点 → 因 `FLOW_ALGO_VERSION` 已 bump, key 变 → miss → 重算 → 写新行
6. 旧 12 keys 还在表里 (永不被命中, 24h 后被 TTL 清理)

**结论**: 不会**返旧值** (key 变 → miss), 但**浪费磁盘**且**误导调试** (`list_keys()` 看到 12 死键).

### 1.2 治理决策

Sprint 18 #123 决定: **启动时显式对齐 manifest version**, 跨进程持久化 last_seen 到磁盘文件.
进程内 `_ManifestTracker` 检测**本进程内**变化 (跟原来一样), 启动 hook 检测**跨进程**变化
(uvicorn 重启 / ETL 跑批后 / DuckDB 备份恢复).

**两个 tracker 互补**:
- 进程内 `_ManifestTracker`: 实时 (cache.get() 时), 检测本进程内的 manifest 变化
- 启动 hook `check_manifest_version_and_invalidate()`: 一次性, 检测跨进程的 manifest 变化

---

## 2. 设计 (How)

### 2.1 跨进程持久化

启动 hook 用磁盘文件记录"上次见过的 manifest version":
- 路径: `data/cache/w5kv_manifest_state.json` (默认)
- 环境变量覆盖: `FQ_W5KV_STATE_PATH` (test 用 tmp_path)
- Schema: `{"last_seen_manifest_version": int, "ts": ISO8601}`

不依赖 DuckDB 表 (避免循环: 启动 hook 不能依赖 W5 cache 自身的表).
不依赖 git hash / mtime (etcd / container / Windows FS mtime 不稳).

### 2.2 函数签名

```python
def check_manifest_version_and_invalidate(
    state_path: Optional[Path] = None,
    cache: Optional[RfmQueryCache] = None,
) -> bool:
    """启动 hook: 对齐 manifest version, 不一致时自动 invalidate W5 cache.

    Args:
        state_path: 状态文件路径, 默认 data/cache/w5kv_manifest_state.json
                    (FQ_W5KV_STATE_PATH 环境变量可覆盖)
        cache: RfmQueryCache 实例, 默认新建

    Returns:
        bool: True = 触发了 invalidate, False = no-op
    """
```

### 2.3 调用流程

```
main.py lifespan startup
  ↓
check_manifest_version_and_invalidate()
  ↓
读 manifest current version (_manifest_tracker_singleton.current_version())
  ↓ 缺失?
  └─→ return False (no-op, 等 ETL 首次写 manifest)
  ↓
读 state 文件 last_seen_manifest_version
  ↓ 缺失?
  └─→ last_seen = None
  ↓
last_seen == current?
  ├─→ True: return False (no-op, cache 保留)
  └─→ False: cache.invalidate() + _write_state_file() + return True
```

### 2.4 失败处理 (best-effort)

任何异常被吞掉 + log warning, **不阻塞** uvicorn 启动. 设计理由:
- 启动 hook 失败不应让 4 端点全部 503
- 缓存状态是 best-effort (跟原 `_ManifestTracker` 一样容忍异常)

---

## 3. 触发条件 (When)

| 场景 | 行为 | 说明 |
| --- | --- | --- |
| **首次启动** (state 缺失) | invalidate + 写 state | ETL 跑过, manifest v=1, 全新部署 |
| **state 一致** (manifest 没动) | no-op | 24h 内重启 uvicorn, cache 保留 (r-flow 1180× 加速) |
| **manifest 升 v** (ETL 跑完) | invalidate + 更新 state | 改 ratio/契约后, ETL → manifest v+1 → 重启 |
| **manifest 降 v** (罕见, ETL 回滚) | invalidate + 更新 state | 防御性: 任何不一致都清空 |
| **manifest 缺失** (没跑过 ETL) | no-op, return False | 等 ETL 跑批后由进程内 `_ManifestTracker` 接管 |
| **state 文件损坏** (JSON 错) | 当作 None 处理 → invalidate | 防御性, 重新对齐 |
| **state 写失败** (磁盘满) | return False, log warning | best-effort, 不阻塞启动 |

---

## 4. 跟 Sprint 14.5/17 的关系 (历史)

### 4.1 Sprint 14.5 (留的痛点)

Sprint 14.5 P1.4 (Codex audit): W5 flow cache 加 `FLOW_ALGO_VERSION`, 防 24h 内返旧值.
**留的痛点**: "改 ratio/契约后必须手动 invalidate W5 DuckDB-KV cache (12 keys)".
本次 Sprint 18 #123 闭环.

### 4.2 Sprint 16.5 (不冲突)

Sprint 16.5 P2.7 (Codex audit): `_flow_cache_key` MD5 full + namespace prefix `flow_`.
W5 DuckDB-KV cache key 仍用 `w5kv_` namespace + SHA-256 + `FLOW_ALGO_VERSION`.
**两套 cache 命名空间隔离, 启动 hook 只 invalidate W5 DuckDB-KV, 不动 file cache**.

### 4.3 Sprint 17 (retrospective Section 4 #4)

Sprint 17 retrospective 治理债务 #4 写明:
> W5 cache invalidation hook — 改 ratio/契约后必须手动 invalidate. Sprint 14.5 留, 跟 manifest 同步.

本次 Sprint 18 #123 实现 + 测试 + 文档, 闭环.

---

## 5. 跟跑批关系 (ETL 集成)

### 5.1 ETL 跑批流程 (不变)

```
scripts/etl/run_etl.py --update
  ↓
[增量 ETL 步骤] 写 orders / users / rfm_fact
  ↓
manifest.py:write_active("rfm_view_vN+1")  # manifest version 升
  ↓
[启动] uvicorn 重启 (launchd / k8s)
  ↓
main.py lifespan startup
  ↓
check_manifest_version_and_invalidate()  ← Sprint 18 #123
  ↓
读 manifest v=N+1 vs state last_seen=N → 不一致 → invalidate
  ↓
W5 cache 表 12 orphan keys 清空, 写 state=N+1
  ↓
[生产] 4 端点接收请求, cache miss → 重算 → 写新行
```

### 5.2 不会清空 file cache

`backend/services/rfm/_shared.py:_flow_cache_key` 生成的 file cache (`data/cache/rfm_flow/flow_*.json`)
**不**受启动 hook 影响. file cache 自己带 `data_version` + `algo_version` 校验:
```python
if cached.get("data_version") != data_version:
    return None
if cached.get("algo_version") != FLOW_ALGO_VERSION:
    return None
```
**两层独立失效机制**:
- W5 DuckDB-KV cache: 启动 hook 主动清 (本文档)
- W5 file cache: 读时校验 data_version + algo_version, 不一致 → miss

### 5.3 跟 `_ManifestTracker` 不冲突

`_ManifestTracker` 检测**本进程内** manifest 变化 (cache.get() 时实时检测),
启动 hook 检测**跨进程** 变化 (uvicorn 重启 / ETL 跑批后). 两 tracker 独立工作:
- 进程内: 跑批中途 API 读 → tracker 检测 v=N → v=N+1 → invalidate
- 跨进程: 重启 uvicorn → 启动 hook 检测 state=N vs current=N+1 → invalidate

---

## 6. 手动触发 (Troubleshooting)

### 6.1 正常情况 (auto)

不用手动. 启动 hook 自动跑.

### 6.2 强制清空 (紧急)

如果怀疑 cache 仍有 orphan / stale 行, 两种方式:

**方式 1: 删 state 文件** (推荐)
```bash
rm data/cache/w5kv_manifest_state.json
# 下次 uvicorn 启动, hook 检测到 state 缺失 → 整表清空 + 写新 state
```

**方式 2: 跑 SQL 手动清** (历史方式, Sprint 18 前)
```sql
-- 在 DuckDB CLI 或 python:
DELETE FROM rfm_query_cache;
```
不推荐: 跟手动 `git checkout` 一样, 容易忘. **优先用方式 1**.

### 6.3 调试: 看 cache 状态

```python
from backend.services.rfm.cache import RfmQueryCache, _read_state_file, _default_state_path
cache = RfmQueryCache()
print(cache.stats())  # {'total': N, 'valid': M, 'expired': K}
print(cache.list_keys(endpoint='r-flow', limit=20))  # 看具体 keys
print('state:', _read_state_file(_default_state_path()))  # 持久化 state
```

### 6.4 CI / 跑批脚本触发

如果想在 ETL 跑批**末尾**也主动调一次 (不依赖 uvicorn 重启):
```python
# scripts/etl/run_etl.py 末尾 (可选, Sprint 18 #123 不强制)
from backend.services.rfm.cache import check_manifest_version_and_invalidate
check_manifest_version_and_invalidate()
```
**注意**: ETL 进程跟 uvicorn 进程**不同**进程, 但**访问同一 DuckDB 文件** (W5 cache 表共享).
直接 `cache.invalidate()` 会删表所有行 → 下次 uvicorn 请求全部 miss → 重算一次.
**性能开销**: 4 端点首次查询各 miss 一次 (e.g. r-flow 6.45s, Sprint 16.5 P2.7 测速基线).
**是否值得**: 看场景. Sprint 18 #123 **不强制** ETL 调, 默认**只** uvicorn 启动时调.

---

## 7. 监控 (Ops)

### 7.1 启动日志

uvicorn 启动时, 看 `[INFO] W5 startup hook: manifest version 变化 ... invalidated N cache rows`:
- N > 0: 正常, 清理了 orphan keys
- N = 0 但 log 出现: 正常, 首次启动 (空表清空)
- 多次出现: 可能 state 文件被删 / manifest 频繁升, 检查 ETL 跑批频率

### 7.2 异常日志

`[WARNING] W5 startup hook 启动失败 (不阻塞服务): <error>`:
- 启动 hook 失败, **不阻塞** uvicorn 启动
- 缓存可能含 orphan, 但**不会**返旧值 (`FLOW_ALGO_VERSION` 兜底)
- 排查: 看 `data/cache/w5kv_manifest_state.json` 是否可写, 磁盘是否满

### 7.3 性能影响

启动 hook 是 O(1) (一次 `read_text()` + 一次 `JSON.parse()` + 一次 `DELETE FROM rfm_query_cache`):
- 无 manifest: < 1ms (只 `os.path.exists()`)
- 有 manifest + state 一致: < 5ms (一次 JSON 解析 + 比较)
- 有 manifest + state 不一致: < 100ms (DELETE 12 行 + JSON 写)
- 不影响 uvicorn 启动速度 (启动是 lifespan 异步, 不阻塞 accept)

---

## 8. 验证 (Test)

10 个 pytest 覆盖 (`backend/tests/test_cache_invalidation.py`):

1. `test_no_manifest_hook_silent` — 没 manifest → hook 不报错 + 不写 state
2. `test_manifest_first_run_invalidate` — 首次跑 (state 缺失) → invalidate + 写 state
3. `test_manifest_first_run_empty_cache_safe` — 首次跑 + 空 cache → 安全 no-op
4. `test_manifest_unchanged_no_invalidate` — 第二次跑 (state 一致) → 不 invalidate
5. `test_manifest_unchanged_5_runs` — 5 次连续跑 → 5 次 no-op
6. `test_manifest_changed_invalidate` — manifest v=3 → v=4 → invalidate + 更新 state
7. `test_manifest_first_run_then_changed` — 完整周期: 首次 → 第二次 (一致) → 第三次 (变化)
8. `test_hook_state_path_unwritable_does_not_raise` — state 写失败 → best-effort
9. `test_hook_invalid_manifest_json_does_not_raise` — manifest 损坏 → best-effort
10. `test_hook_then_get_works` — hook 跑过后, cache.get() 仍正常工作

跑测试:
```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="$(pwd)" pytest backend/tests/test_cache_invalidation.py -v
# 10 passed in <5s
```

---

## 9. FAQ

**Q: 改 ratio/契约后, 还需要手动 invalidate 吗?**
A: **不需要**. 改完 → ETL 跑批 (manifest v+1) → 重启 uvicorn → 启动 hook 自动清空 12 orphan keys.
只要 ETL 跑批 + uvicorn 重启, 闭环.

**Q: 不跑 ETL 直接改代码重启 uvicorn, 会怎样?**
A: 启动 hook 检测 manifest 没变 (state 一致) → no-op. 但 `FLOW_ALGO_VERSION` 已 bump,
后续 cache.get() key 变 → miss → 重算 → 写新行. 旧 12 keys 永不被命中, 24h 后被 TTL 清理.
**不会**返旧值.

**Q: 启动 hook 失败, 会不会阻塞 uvicorn?**
A: **不会**. 异常被 `except Exception` 吞 + log warning, 4 端点照常服务. 缓存可能含 orphan,
但 `FLOW_ALGO_VERSION` 兜底防返旧值.

**Q: 跟 `_ManifestTracker` 啥区别?**
A: `_ManifestTracker` 检测**本进程内** manifest 变化 (cache.get() 时), 启动 hook 检测
**跨进程** 变化 (uvicorn 重启 / ETL 跑批后). 互补, 不冲突.

**Q: 能不能 ETL 末尾也调一次?**
A: 可以, 见 §6.4. Sprint 18 #123 不强制, 默认只 uvicorn 启动时调.

**Q: state 文件能删吗?**
A: 可以. 删了下次 uvicorn 启动 → hook 检测 state 缺失 → 整表清空 + 写新 state. 一次性能开销.

**Q: 多进程 (gunicorn workers) 会不会重复 invalidate?**
A: 不会. 启动 hook 整表清空 + 写 state 是幂等的. 多 worker 同时启动, 第一个写完 state 后
后续 worker 看到 state 一致 → no-op. 但**有微小竞态**: 多 worker 同时清空 + 写 state,
最终 state = 最后一个 worker 写的值. 不影响正确性, 只是可能有 worker 重复跑 DELETE.

---

## 10. 变更日志 (Version)

| 版本 | 日期 | 改动 |
| --- | --- | --- |
| v0.4.14.47 | 2026-06-11 | Sprint 18 #123: 加 `check_manifest_version_and_invalidate()` 启动 hook, 跨进程持久化 last_seen_manifest_version, `FLOW_ALGO_VERSION` bump `v0.4.14.35` → `v0.4.14.47` |
| v0.4.14.35 | 2026-06-10 | Sprint 14.5 P1.4: 加 `FLOW_ALGO_VERSION`, 防 24h 内返旧值 (留治理债务 #4) |
| v0.4.13 | 2026-06-07 | Sprint 1: W5 DuckDB-KV cache 初版 + `_ManifestTracker` 进程内 manifest 跟踪 |
