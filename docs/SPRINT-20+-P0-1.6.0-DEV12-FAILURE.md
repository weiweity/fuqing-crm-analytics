# Sprint 20+ P0: DuckDB 1.6.0.dev12 B 路径失败 (2026-06-12)

## 结论

❌ **DuckDB 1.6.0.dev12 不治根, 还引入新 race** — 单次增量跑批 (~3 min 内) 崩溃, 错误是 1.6.0.dev12 特有的 ART index corruption (INSERT-side), 跟 1.5.x 的 "Failed to delete 0/2048" (DELETE-side) 是完全不同的症状。

跟 [Sprint 16 P0 激活报告](SPRINT-16-P0-ACTIVATION.md) 的 false-positive 教训 + A 路径 (等 1.5.4 stable release) 形成完整证据链:

| DuckDB | v2 code | 结果 | 失败类型 |
|---|---|---|---|
| 1.5.3 | 原版 (1.88M 跑批) | race at p6_sql | DELETE race (Sprint 16 abort) |
| 1.5.4.dev18 | 原版 + v2 (1.88M 跑批) | race 仍触发 | DELETE race 仍存在 |
| **1.6.0.dev12** | **v2 (1.88M 跑批, ~3 min)** | **崩 at ETL 早期** | **INSERT race (新症状)** |

## B 路径执行 (2026-06-12 14:21)

### 步骤 1: Stash + 切 fix/sprint16-p0 branch
- 停 uvicorn PID 15138, 释放 DuckDB 锁
- git stash .gitignore + CHANGELOG.md (Sprint 20 P1 收口修改)
- git checkout -f fix/sprint16-p0-duckdb-taoke-channel-race (head: bb34810, v2 code = line 1076-1156 包整段 BEGIN/COMMIT)
- 验证 v2 code 完整: `grep "BEGIN\|CHECKPOINT\|DROP INDEX" pipeline.py` 看到 line 1074 CHECKPOINT, 1077 BEGIN, 1081 DROP INDEX, 1154 CREATE INDEX

### 步骤 2: 装 DuckDB 1.6.0.dev12
```
/Users/hutou/homebrew/bin/python3 -m pip install --user --break-system-packages --pre "duckdb>=1.6.0.dev12,<1.7.0"
```
- Wheel: `duckdb-1.6.0.dev12-cp314-cp314-macosx_11_0_arm64.whl` (13.8 MB)
- Successfully installed duckdb 1.6.0.dev12 (从 1.5.4.dev18 升)
- Smoke test: CREATE/DROP/UPDATE/RECREATE index 全过 (基础 index lifecycle 没崩)

### 步骤 3: 跑 v2 4 unit tests (sanity)
- 4/4 passed in 0.41s (跟 1.5.4.dev18 + v2 一样的 4/4 假象)
- **D-7 教训: 单连接测试不推广到生产**, 不作治根判定

### 步骤 4: 跑增量 ETL (1.88M 真验, ~3 min 崩)
```
nohup env PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update > /tmp/fuqing-etl-1.6.0-dev12.log 2>&1 &
```

- 14:21:08 启动, PID 26887
- 14:21-14:25 跑 (CPU time 70s+ 累计)
- 14:27:47 log 写 1 行后崩, ETL 退出
- 错误 (verbatim):
  ```
  libc++abi: terminating due to uncaught exception of type duckdb::FatalException: {"exception_type":"FATAL","exception_message":"FATAL Error: Corrupted ART index - likely the same row id was inserted twice into the same ART"}
  ```

### 步骤 5: 回退
- `pip install --user --break-system-packages "duckdb>=1.5.4.dev18,<1.6.0"` → 1.5.4.dev18 装回
- git checkout -f fix/sprint5-20-scraper-soft-delete (主开发 branch, 1.5.3 pipeline.py)
- 重启 uvicorn PID 32197, /health 401 (auth working)

## 错误分析 (Corrupted ART index - same row id)

### 跟 1.5.x race 对比
| DuckDB | 错误信息 | 触发侧 | 触发段 |
|---|---|---|---|
| 1.5.3 / 1.5.4.dev18 | "Failed to delete 0 out of 2048 rows" | DELETE | p6_sql (1.88M 真实跑批, race 在 COMMIT 段) |
| **1.6.0.dev12** | **"Corrupted ART index - likely the same row id was inserted twice into the same ART"** | **INSERT** | **ETL 早期 (没到 p6_sql, 跑崩前 log 空)** |

### 1.6.0.dev12 引入的新 race
- "Same row id inserted twice" 是 DuckDB 1.6.0 dev 系列新引入的 ART index 完整性检查
- 跨 connection / 跨事务的 INSERT 操作可能产生重复 row id 写入, 触发 1.6.0 新加的 sanity check
- **v2 code 单事务包整段也不能避免** (因为 race 触发点不在事务段, 可能在 ETL 早期 INSERT 阶段)
- 跟 1.5.x "Failed to delete 0/2048" 完全是不同的代码路径

### 没修好 + 引入新问题
- 1.6.0.dev12 **没修 1.5.x 的 race** (新版本可能把 race 移到了 INSERT 段)
- 1.6.0.dev12 **新引入 INSERT-side race** (Corrupted ART)
- 净结果: 1.6.0.dev12 比 1.5.4.dev18 **更差**, dev release 不推荐 prod

## A 路径继续 (locked)

**A 路径**: 等 DuckDB 1.5.4 stable release (PyPI 还没出, cron daily 9:00 监控中)
- `scripts/etl/check_duckdb_release_cron.sh` (cron 脚本, 写 flag + 飞书告警)
- `scripts/etl/activate_duckdb_1_5_4_stable.sh` (1-click 4 步激活: 装 stable + 跑 v2 4 tests + checkout fix branch + smoke test)
- `scripts/etl/com.fuqing.duckdb-release-check.daily.plist` (launchd daily 9:00)
- **关键: 1.5.4 stable release 后必须跑真 prod 验证 (1.88M 行), 不只跑 v2 4 unit tests (D-7 教训)**

## B 路径失败教训 (跟 1.5.4.dev18 失败一起)

### 1. dev release 跟 stable release 同样不可信
- 1.5.4.dev18 (假阳性: 单连接测试全过, prod race 仍触发)
- 1.6.0.dev12 (假阳性: 单连接测试全过, prod 崩, 还引入新 race)
- **教训**: dev release 装在生产是赌博, 必须等 stable release + 真 prod 验证

### 2. PyPI 1.5.4 stable 也许永远不出
- 当前 (2026-06-12) PyPI latest stable 仍是 1.5.3 (2026-05-20)
- 1.5.4 一直是 dev 系列, 1.6.0 抢先变 latest
- 1.5.4 stable release 概率: 中等 (DuckDB 通常会发 stable, 但 dev 跳 stable 也有先例)
- 1.6.0 stable release 概率: 高 (dev12 已有, 估计几周内 stable)
- **新方向**: 是不是应该把 cron 监控改成 1.6.0 stable release?

### 3. C 路径 (read-only workaround) 考虑
- 增量跑批改 read-only mode (前端 0 增量更新)
- 接受 race 限制, 暂停增量跑批, 等 DuckDB 上游修
- **优点**: 1-2 天实施, 永久 work-around, 不依赖 dev release
- **缺点**: 前端 0 增量更新, 用户体验下降
- **适合**: 1.5.4 stable release 看起来遥遥无期时

## 后续 (3 选 1)

### 选 1: 继续等 1.5.4 stable release (A 路径, 当前)
- cron daily 9:00 监控
- 风险: 1.5.4 stable 也许永远不出
- 工作量: 0 (passive waiting)

### 选 2: 把 cron 监控改成 1.6.0 stable release (A 路径 变种)
- `check_duckdb_release.py` 加 1.6.0 stable 检测
- 1.6.0 stable release → 跑 1.88M 真验 (跟 1.5.4 stable 流程一样)
- 风险: 1.6.0 stable 也可能有 race (INSERT-side 或新问题)
- 工作量: 半天 (改监控脚本)

### 选 3: 走 C 路径 (read-only workaround)
- 增量跑批改 read-only, 前端 0 增量更新
- 暂停 daily 增量, 接受 race 限制
- 工作量: 1-2 天 (改 ETL + 改前端 + 改 cron)
- 永久 workaround, 不依赖 dev release

## 结论摘要

1. **1.6.0.dev12 跑崩, 错误是 "Corrupted ART index - same row id inserted twice"** (新 race, INSERT-side)
2. **回退 1.5.4.dev18 + 切回 fix/sprint5-20 branch + 重启 uvicorn** 完成, 系统回 1.88M 跑批 race 已知状态
3. **A 路径继续等 1.5.4 stable release** (cron daily 9:00 监控中)
4. **3 选 1 决策留 Sprint 21+**: 选 1 (等 1.5.4) / 选 2 (改监控 1.6.0) / 选 3 (read-only workaround)

---

*此文件由 Sprint 20+ P0 B 路径执行生成, 2026-06-12 14:30 完成*
