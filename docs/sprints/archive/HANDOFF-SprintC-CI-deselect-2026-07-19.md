# HANDOFF — Sprint C CI deselect cleanup (2026-07-19)

> **角色**: Grok (Codex 实施者位) → Claude Code (架构师 / Stage 3 review + Stage 4 ship)
> **分支**: `fix/sprint-ci-deselect-cleanup-2026-07-19` (from `main @ fc18077`)
> **状态**: 本地实施完成，**未 push / 未 merge**（等 user 拍板 L4.15）
> **Verdict**: `PARTIAL_FIXED_PENDING_B_C` → A+B 已闭环；C 7 条留 deselect + TECH-DEBT 登记

---

## 1. 背景（已完成的 Sprint A+B）

| Commit | 说明 |
|---|---|
| `fc18077` | `ci(nightly): sync L4.86 env var + 22 deselect 跟 lint.yml test job 1:1 stable` |

Sprint C 目标：评估并收敛 21 条 `--deselect`（YAML 实际 21，历史口误写 22）。

---

## 2. 分类与本分支动作

| 类 | 数量 | 动作 | 状态 |
|---|---|---|---|
| **A1** | 9 | rfm_cache×7 + w7 + startup 已绿 → 去掉 deselect | ✅ |
| **A2** | 2 | w2 RFM version endpoint 加 `isolated_read_db` → 去掉 deselect | ✅ |
| **B** | 3 | period_distribution 死 nodeid（`79e5d33` 已删 body）→ 清 deselect | ✅ |
| **C** | 7 | sampling 3 + W4 4 → **保留 deselect** | 📋 留尾 |

### C 类仍 deselect 的 7 条

```
test_etl_sample_received_at.py::TestSampleReceivedAtPhase1::test_sampling_service_falls_back_to_pay_time
test_sampling_roi_yoy.py::test_roi_mom_compare_tuple
test_sampling_roi_yoy.py::test_roi_yoy_pct_pp_contract_types
test_w4_t7_integration.py::TestW4T7ActualRun::test_a_w4_t7_actual_run
test_w4_t7_integration.py::TestW4Idempotency::test_b_w4_idempotency
test_w4_t7_integration.py::TestW4VersionIncrement::test_c_w4_version_increment
test_w4_t7_integration.py::TestW4DataQuality::test_d_w4_data_quality
```

---

## 3. 改动文件（仅这些，勿带 main dirty 20 文件）

| 文件 | 改动 |
|---|---|
| `backend/tests/test_w2_manifest.py` | `TestRfmVersionEndpoint.isolated_read_db` fixture |
| `.github/workflows/lint.yml` | 21→7 C-class deselect + 注释更新 |
| `.github/workflows/nightly.yml` | 同上 1:1 |
| `docs/TECH-DEBT.md` | Sprint C 节（A/B/C IDs + 真业务触发再立） |
| `docs/sprints/HANDOFF-SprintC-CI-deselect-2026-07-19.md` | 本文件 |

**未碰**: Sprint 205+ Admin Upload WITHDRAWN、生产 DuckDB、uvicorn、main 无关 dirty 路径。

---

## 4. W2 真因（A2）

- 注释说「需 prod db」过时。
- 真因：`/api/v1/rfm/*` → `QueryRouterMiddleware` read → `dual_conn.get_read_connection()` 打开 `DUCKDB_PATH`。
- endpoint 只读 manifest JSON，不查 orders。
- 修法：tmp 空 DuckDB + `FQ_DB_MODE=schema_test` + patch `dual_conn.DUCKDB_PATH` + 清 `_read_pool`。

---

## 5. 本地验证（已跑）

```bash
# A1 + A2 11 case — 11 passed
PYTHONPATH=. pytest \
  backend/tests/test_rfm_cache_drop_recreate.py::TestClearRfmCacheDropRecreate::test_drop_recreate_clears_all_rows \
  backend/tests/test_rfm_cache_drop_recreate.py::TestClearRfmCacheDropRecreate::test_drop_recreate_preserves_schema \
  backend/tests/test_rfm_cache_drop_recreate.py::TestClearRfmCacheIdempotent::test_multiple_clears_idempotent \
  backend/tests/test_rfm_cache_drop_recreate.py::TestClearRfmCacheIndexStateCorruption::test_clear_succeeds_after_index_corruption \
  backend/tests/test_rfm_cache_write_conn.py::TestOpenWriteConnRealConnectionNoError::test_get_cache_conn_succeeds \
  backend/tests/test_rfm_cache_write_conn.py::TestOpenWriteConnRealConnectionNoError::test_sibling_connection_pattern_works \
  backend/tests/test_rfm_cache_write_conn.py::TestClearRfmCacheEndToEnd::test_clear_rfm_cache_no_longer_fails \
  backend/tests/test_w7_memory_limit.py::TestW7MemoryLimitOverride::test_backward_compat_default_8gb \
  backend/tests/test_startup_validation.py::test_production_rejects_stale_data \
  backend/tests/test_w2_manifest.py::TestRfmVersionEndpoint::test_endpoint_returns_manifest_info \
  backend/tests/test_w2_manifest.py::TestRfmVersionEndpoint::test_endpoint_returns_empty_when_no_manifest \
  -q

# CI 模拟 — 11 passed
DUCKDB_PATH=/tmp/missing_ci.duckdb FQ_DB_MODE=schema_test \
FQ_CRM_PASSWORDS=admin:123456 FQ_CRM_ADMINS=admin \
PYTHONPATH=. pytest <同上 11> -q

# deselect 计数
rg '\-\-deselect' .github/workflows/lint.yml   # 期望 7 行
rg '\-\-deselect' .github/workflows/nightly.yml  # 期望 7 行（name 字段可能多 1 次字面匹配）

ruff check backend/tests/test_w2_manifest.py
```

---

## 6. Claude Code 下一步（12 步后半）

```
① 已在 feature 分支 — 确认: git branch --show-current
② review skill — 看 diff 仅 5 文件
③ 可选 qa skill
④ 拍 push 后: git push origin fix/sprint-ci-deselect-cleanup-2026-07-19
⑤ 拍 merge 后: merge --no-ff → main → push main
⑥ git pull --ff-only；**不必** restart uvicorn（0 业务 runtime 改动）
⑦ L4.8 删本地+远程 feature 分支
⑧ 勿 stage main 上无关 dirty 20 文件
```

### 推荐 commit 信息（若 re-commit / 已有则核对）

```
test(w2): isolate RFM version endpoint from prod DuckDB for CI

ci: drop 14 deselects (A1+A2+B), keep 7 C-class sampling/W4

docs: Sprint C 21 deselect evaluation + TECH-DEBT C-class leave-behind
```

---

## 7. 给用户的一句话

Sprint C 本地闭环：14 条 deselect 摘掉（9 已绿 + 2 w2 修 + 3 死节点），7 条真连 prod 留尾；等你 **拍 push / 拍 merge** 后由 Claude 收口 12 步。

---

## 8. 复制给 Claude Code 的提示词

见用户会话最终回复中的 **「Claude Code 提示词」** 块（与本节内容一致的可执行指令）。
