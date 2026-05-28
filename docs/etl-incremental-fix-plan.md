# ETL 增量架构改进计划

## 1. 现状与问题诊断

### 1.1 已确认的根因

2026-05-28 诊断发现：**增量 ETL 的 `processed_files` 记录与 DuckDB 数据写入非原子化**，导致数据丢失。

- 文件 `任务21320_003730469.xlsx`（52,806 行，05-26 ~ 05-27 数据）
- 已被标记在 `processed_files_shop.json` 中（mtime: 05-27 16:37）
- 但 DuckDB orders 表中 05-26、05-27 均为 0 行
- 结论：ETL 在处理该文件时中断，processed_files 已更新但数据未写入

### 1.2 影响范围

| 场景 | 频率 | 后果 |
|------|------|------|
| DuckDB 文件锁未释放 | 偶发 | ETL 中断，数据丢失，需手动修复 processed_files |
| SIGTERM 中断后台进程 | 常见（命令超时） | 同上，且 user_rfm 预计算也会断 |
| 文件内容变更但 mtime 未变 | 偶发 | 增量跳过，数据 stale |
| 增量漂移累积 | 长期 | 数据不一致，必须定期全量重跑修正 |

### 1.3 当前性能瓶颈

- 全量 ETL：~2-3 小时（10M+ 行，openpyxl 解析 xlsx）
- RFM 预计算：~1 小时（600/600 slices，多进程）
- 增量 ETL：理论分钟级，实际因上述问题常 fallback 到全量

---

## 2. 改进目标

1. **可靠性**：消除 processed_files 与 DuckDB 写入的非原子性
2. **正确性**：文件内容变更必被检测，不依赖 mtime
3. **性能**：xlsx 解析不再是瓶颈，增量 ETL < 5 分钟
4. **可恢复性**：中断后可安全续跑，无需手动清理状态文件

---

## 3. 方案选项

### 方案 A：事务化 processed_files（最小改动）

**思路**：将 processed_files 的更新延迟到 DuckDB 写入成功后。

```
读取文件 → 解析 → 写入 DuckDB → COMMIT → 更新 processed_files
                      ↑
                   失败则 rollback，processed_files 不更新
```

**改动点**：
- `ingest.py`：`_save_processed_files` 移到 `upsert_to_duckdb` 成功之后
- `pipeline.py`：全量/增量模式的文件处理循环中，确保"写入成功"才标记

**优点**：改动最小，风险低
**缺点**：仍依赖 mtime，不解决"文件内容变了但 mtime 没变"问题

---

### 方案 B：校验和替代 mtime（推荐）

**思路**：用文件内容 hash（xxhash/blake3）替代 mtime 作为"是否已处理"的判断依据。

```python
# 当前：mtime 判断
if key not in processed or mtime > processed[key]:
    process_file(f)

# 改进：hash 判断
file_hash = xxhash.xxh64_file(f).hexdigest()
if key not in processed or processed[key]['hash'] != file_hash:
    process_file(f)
    processed[key] = {'hash': file_hash, 'mtime': mtime, 'rows': len(df)}
```

**改动点**：
- `config.py`：新增 xxhash 依赖
- `ingest.py`：`_load_processed_files` / `_save_processed_files` 改结构
- 向后兼容：旧格式 mtime-only 的记录自动迁移

**优点**：内容变更必被检测，不受 mtime 干扰
**缺点**：需要计算 hash，大文件（~8MB）额外开销 ~10ms，可忽略

---

### 方案 C：Parquet 缓存层

**思路**：原始 xlsx 只读一次，转换为 Parquet 后增量只读 Parquet。

```
店铺数据库/xxx.xlsx  ──→  Parquet 缓存/xxx.parquet  ──→  DuckDB
      ↑                        ↑
   新增/变更时                  增量时只读新增 Parquet
   自动转换（后台）              历史 Parquet 不复读
```

**改动点**：
- `ingest.py`：`load_data_files` 新增 Parquet 转换逻辑
- `config.py`：`PARQUET_DATA_DIR` 已存在，复用
- 增量模式：只转换新增/变更的 xlsx，已有 Parquet 直接读

**优点**：
- Parquet 读速度比 openpyxl 快 10-50x
- 历史数据不复读 xlsx，全量 ETL 也能大幅加速
- 磁盘占用：Parquet 比 xlsx 小 30-50%

**缺点**：需要额外存储 Parquet 文件，首次全量转换耗时

---

### 方案 D：DuckDB 原生读 xlsx

**思路**：直接用 DuckDB 的 `read_excel()` 函数读 xlsx，不经过 pandas/openpyxl。

```sql
INSERT INTO orders
SELECT * FROM read_excel('path/to/file.xlsx')
```

**改动点**：
- `ingest.py`：替换 `pd.read_excel` 为 `duckdb.read_excel`
- 列名映射：在 SQL 层处理，不在 Python 层

**优点**：
- DuckDB C++ 引擎读 xlsx 比 openpyxl 快 5-10x
- 内存占用更低（流式处理）
- 代码更简洁

**缺点**：
- DuckDB 的 xlsx 支持不如 openpyxl 成熟（复杂格式可能报错）
- 需要测试兼容性

---

### 方案 E：WAL + Checkpoint 机制

**思路**：引入 Write-Ahead Log，ETL 操作先写日志，成功后再应用到主库。

```
xlsx 读取 → 解析 → 写 WAL → 写入 DuckDB → Checkpoint → 清理 WAL
                           ↑
                        失败时从 WAL 恢复
```

**改动点**：
- 新增 `wal.py`：WAL 记录管理
- `pipeline.py`：每个文件处理前写 WAL，成功后 checkpoint

**优点**：最强一致性，可精确恢复
**缺点**：过度设计，当前规模不需要

---

## 4. 推荐组合

**Phase 1（立即做）**：方案 A + 方案 B
- 事务化 processed_files（修复当前 bug）
- 校验和替代 mtime（防止未来漂移）
- 改动量：~50 行代码，1 个新依赖（xxhash）

**Phase 2（有空做）**：方案 C
- Parquet 缓存层，解决性能瓶颈
- 改动量：~100 行代码，复用现有 PARQUET_DATA_DIR

**Phase 3（可选）**：方案 D
- DuckDB 原生读 xlsx，进一步加速
- 需要充分测试兼容性后再上线

**不采纳方案 E**：WAL 对当前规模过度设计，引入复杂度不值得。

---

## 5. 实施步骤

### Phase 1：事务化 + 校验和（预计 2 小时）

1. **新增依赖**：`pip install xxhash`
2. **修改 `config.py`**：
   - `_get_processed_files_path` 保持兼容
   - `_load_processed_files` 支持旧格式（mtime float）和新格式（dict with hash）
   - `_save_processed_files` 统一写新格式
3. **修改 `ingest.py`**：
   - `load_data_files` 中，hash 判断替代 mtime 判断
   - `_save_processed_files` 调用点移到 `upsert_to_duckdb` 成功之后
4. **修改 `pipeline.py`**：
   - 全量/增量模式的循环中，确保"写入成功"才标记
5. **测试**：
   - 模拟中断：处理文件时抛异常，确认 processed_files 不更新
   - 模拟文件变更：改内容不改 mtime，确认被检测

### Phase 2：Parquet 缓存（预计 4 小时）

1. **修改 `ingest.py`**：
   - 全量模式：xlsx → Parquet 转换（首次）
   - 增量模式：新增 xlsx 转 Parquet，已有 Parquet 直接读
2. **修改 `pipeline.py`**：
   - 全量 ETL 时先批量转换新增 xlsx 为 Parquet
3. **测试**：
   - 对比 xlsx vs Parquet 读取速度
   - 验证数据一致性（行数、列值）

---

## 6. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| hash 计算增加开销 | 低 | 极小（~10ms/文件） | 用 xxhash（最快） |
| Parquet 转换失败 | 中 | 中 | fallback 到 xlsx，不阻塞 |
| DuckDB xlsx 兼容性 | 中 | 中 | Phase 3 充分测试后再上线 |
| processed_files 格式迁移 | 低 | 中 | 向后兼容，自动迁移旧格式 |
| 代码 review 时间 | 高 | 中 | 拆分 PR：Phase 1 单独提 |

---

## 7. 验收标准

- [ ] 模拟 ETL 中断，processed_files 不更新，续跑能正确处理同一文件
- [ ] 修改 xlsx 内容（不改 mtime），增量 ETL 能检测并重新处理
- [ ] 增量 ETL 运行时间 < 5 分钟（当前瓶颈是 xlsx 解析）
- [ ] 全量 ETL 运行时间 < 30 分钟（当前 2-3 小时）
- [ ] 连续 7 天增量 ETL 无数据丢失

---

## 8. 待确认问题

1. **P2-4 `is_member` 列**：是否在本次改进中一并处理？（建议单独 PR，避免范围膨胀）
2. **DuckDB 版本**：当前版本是否支持 `read_excel()`？（需要测试）
3. **Parquet 磁盘空间**：预计增加 10-15GB，data/ 目录空间是否足够？

---

## GSTACK REVIEW REPORT

> Reviewed by: /autoplan | Date: 2026-05-28 | Mode: Auto-decision

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale |
|---|-------|----------|---------------|-----------|-----------|
| 1 | CEO | 采纳 "事务化 + 校验和" 组合 | Mechanical | P1 完整性 | 覆盖原子性和内容变更检测两个独立问题 |
| 2 | CEO | 不采纳 WAL 方案 | Mechanical | P3 务实 | 当前规模过度设计，复杂度不值得 |
| 3 | CEO | Phase 1/2/3 分阶段实施 | Mechanical | P2 分 lake | 每阶段独立可交付，风险可控 |
| 4 | CEO | P2-4 `is_member` 单独 PR | Mechanical | P2 范围控制 | 避免范围膨胀，Schema 变更是独立问题 |
| 5 | Eng | 校验和用 xxhash 非 blake3 | Mechanical | P3 务实 | 10ms vs 50ms，安全性非需求，速度优先 |
| 6 | Eng | processed_files 旧格式自动迁移 | Mechanical | P1 完整性 | 避免手动清理，向后兼容 |
| 7 | Eng | Parquet 转换失败 fallback xlsx | Mechanical | P1 完整性 | 不阻塞主流程， graceful degradation |
| 8 | Eng | DuckDB `read_excel()` 放 Phase 3 | Taste | P3 务实 | 兼容性风险未知，先解决已知问题 |

### CEO Review — 范围与战略

**问题定义：** ✅ 正确。增量 ETL 数据丢失是已验证的根因，非假设。

**范围评估：** ✅ 合理。Phase 1（事务化+校验和）直击当前 bug，Phase 2（Parquet）解决性能，Phase 3（DuckDB 原生）是优化。

**不采纳项：**
- WAL（方案 E）：正确。10M 行规模不需要 WAL，事务化 processed_files 已足够。
- 全量重跑修复：正确。手动删除 processed_files 条目 + 增量续跑是更务实的修复路径。

**6 个月后悔场景：** 如果只做 Phase 1 不做 Phase 2，大促期间 xlsx 解析仍是瓶颈，ETL 可能超时。建议 Phase 2 在 618 前完成。

### Eng Review — 架构与实现

**架构图：**
```
当前: xlsx → openpyxl → pandas → DuckDB
                 ↓
            processed_files (非原子)

Phase 1: xlsx → openpyxl → pandas → DuckDB → COMMIT → processed_files
                                         ↑
                                    原子化 + hash 校验

Phase 2: xlsx ──→ Parquet (缓存) ──→ DuckDB
            ↓
         首次转换
```

**关键发现：**

1. **原子化缺口：** `ingest.py:196-208` 中 `_save_processed_files` 在 `pd.read_excel` 后立即调用，但 DuckDB 写入在 `pipeline.py` 中。这个时序是 bug 根源。

2. **hash 校验实现细节：** 建议用 `xxhash.xxh64(open(f, 'rb').read()).hexdigest()` 而非文件级 API，避免大文件内存问题。

3. **测试覆盖缺口：** 计划提到"模拟中断"测试，但未明确如何在 CI 中复现 DuckDB 锁场景。建议增加单元测试：`mock.patch` 模拟 `upsert_to_duckdb` 抛异常，验证 processed_files 不更新。

4. **Parquet 并发安全：** 全量 ETL 多进程转换 Parquet 时，需避免多个 worker 同时写同一文件。建议用文件锁或按 worker ID 分区。

**测试计划补充：**

| 测试项 | 类型 | 覆盖路径 |
|--------|------|----------|
| 事务化：DuckDB 失败时 processed_files 不更新 | 单元 | `pipeline.py` 异常路径 |
| hash 检测：内容变更触发重新处理 | 单元 | `ingest.py` hash 判断 |
| 旧格式迁移：mtime-only 记录自动升级 | 单元 | `config.py` 加载逻辑 |
| Parquet 一致性：xlsx vs Parquet 行数一致 | 集成 | `ingest.py` 全量/增量 |
| 7 天增量稳定性 | 集成 | 定时跑 ETL，校验数据完整性 |

### 审查评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 问题定义 | 10/10 | 根因已验证，非假设 |
| 方案完整性 | 9/10 | 覆盖原子性、正确性、性能，缺 CI 测试细节 |
| 实施可行性 | 9/10 | Phase 1 改动量小，风险低 |
| 风险评估 | 8/10 | 缺少 Parquet 并发安全和 CI 测试方案 |
| 验收标准 | 8/10 | 可量化，但"连续 7 天"需要自动化监控 |

### 最终建议

**批准，带一个修改：**

在 Phase 1 实施步骤中增加：
```
6. 新增单元测试 `test_etl_atomicity.py`：
   - test_processed_files_not_updated_on_duckdb_failure
   - test_hash_change_triggers_reprocessing
   - test_legacy_mtime_format_migration
```

**实施优先级：**
1. 立即：手动修复 `任务21320`（删除 processed_files 条目，跑增量 ETL）
2. 本周：Phase 1 PR（事务化 + 校验和）
3. 6月10日前：Phase 2 PR（Parquet 缓存，赶在 618 大促前）
4. 6月后：Phase 3（DuckDB read_excel，非紧急）

### VERDICT: APPROVED with test coverage amendment
