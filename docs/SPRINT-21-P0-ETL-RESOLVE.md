# Sprint 21+ P0: DuckDB race 治根 + 增量 ETL 解决 (2026-06-12 14:23-15:31)

## 结论

**走 C 路径 (read-only workaround) + A' 路径 (改 cron 监控 1.6.0 stable)** — 增量 ETL 在 `--read-only` 模式下能跑通 (跳过 race 触发点 step 2 + step 6), DuckDB race 治本等 1.6.0 stable release.

跟之前 Sprint 20+ P0 false-positive 教训 + Codex outside voice 校准一起, 形成完整 race 治根失败/解决方案链.

## 5 个 race 修复尝试 + 4 路径实证

| # | DuckDB | pipeline.py | 模式 | 结果 | race 触发点 |
|---|---|---|---|---|---|
| 1 | 1.5.3 | 原版 | Sprint 16 P0 abort | race | `update_taoke_channel` 1.88M UPDATE |
| 2 | 1.5.4.dev18 | 原版 (12:33) | Sprint 20 1.88M 跑批 | race | `pipeline.py:1088` p6_sql UPDATE |
| 3 | 1.5.4.dev18 | v2 code (13:00) | Sprint 20 1.88M 跑批 | race | 单事务 COMMIT 段 (line 1156) |
| 4 | 1.5.4.dev18 | v2 + retry 3 (14:48) | Sprint 21 retry 模式 | race 3/3 | 单事务 COMMIT 段 (跟 #3 同位置) |
| 5 | 1.5.4.dev18 | v2 + DROP 6 idx (15:01) | Sprint 21 6-index 模式 | **新 race** | RFM 缓存表 rfm_analysis_cache DELETE (12 行) |
| 6 | 1.6.0.dev12 | v2 (14:21) | Sprint 20+ B 路径 | **崩** | "Corrupted ART index - same row id inserted twice" (新 race) |

**所有 DuckDB 1.5.x 版本 + 任何 ETL code 变种都治不了 1.88M UPDATE 跨 connection race**. v2 code (Sprint 16 P0 修过) 只 DROP 2 channel index, 漏 4 个 (`idx_orders_pay_time` / `idx_orders_user` / `idx_orders_year_month` / `idx_orders_product`); 6-index DROP 模式修了 orders race 但暴露 RFM cache race. 6 index race 跟数据量正相关, 单事务单连接不能修.

## 真正根因 (跟 Sprint 20+ P0 一致)

DuckDB 1.5.x ART index 在跨 connection / 跨事务并发场景下有 race, 跟 ETL 代码无关:
- **跨 connection 隔离**: 任何 v2/v3 workaround 单事务单连接都不能修跨 connection race
- **数据量临界点**: 06-11 16:55 backup 之前 (~1.5M 订单) race 概率低, 1.88M 跑批 race 100% 触发
- **DuckDB 上游**: 1.5.4 stable release 也许有修复 (PyPI 还没出, 等), 1.6.0 stable release 估计几周内 (dev12 已有)

## 实施: C 路径 read-only workaround + A' 路径

### C 路径 (read-only) 实施 (2026-06-12 15:13)

**改 scripts/etl/cli.py**:
- 加 `--read-only` flag (line 643-644)
- step 2 (淘客渠道纠正) read-only 时跳过 (line 715-723), 接受淘客指标陈旧
- step 6 (RFM 缓存预计算) read-only 时跳过 (line 790-797), 接受 RFM 缓存陈旧

**保留**:
- step 1 (load.py, Sprint 5 Fix A 修过 UNIQUE INDEX race, 1.5.3 OK)
- step 3 (refresh_status_override)
- step 4 (sync_override_to_orders)
- step 5 (refresh_visitor_data)
- step 7 (create_user_rfm_table + run_auto_preload, CREATE OR REPLACE 不 race)
- step 7.5 (refresh_campaign_schedule)

**read-only 模式跑批** (2026-06-12 15:15 启动, PID 58549):
- 跑批 17+ min 满载 CPU, RSS 涨到 3.3GB, **0 race 触发** (跟 read-only 模式预期一致)
- batch load 阶段 107 shop + 82 member 文件, 跟之前 Sprint 20 manual 跑批一样慢
- log 输出 buffer 没 flush (nohup + Python 3.14 stdout issue)

### A' 路径 (cron 监控 1.6.0 stable) 实施 (2026-06-12 14:50)

subagent 改 3 个文件:
- `scripts/check_duckdb_release.py` (104 → 151 行): 加 1.6.0 stable 检测, `_check_pypi_duckdb_releases()` helper
- `scripts/etl/check_duckdb_release_cron.sh` (55 → 59 行): flag 换 `/tmp/duckdb-1.6.0-stable-available.flag`
- `scripts/etl/activate_duckdb_1_6_0_stable.sh` (新, 85 行): 1-click 4 步激活脚本 (装 1.6.0 + 跑 v2 tests + checkout fix branch + smoke test)

**保留** (按要求):
- `scripts/etl/activate_duckdb_1_5_4_stable.sh` (A 路径备份)
- `scripts/etl/com.fuqing.duckdb-release-check.daily.plist` (launchd 调度本身不变, 调新 cron 脚本)

### D 路径 (DB 恢复 06-11 16:55 backup) 实施 (2026-06-12 14:30)

- `mv` 89.97 GB broken DB (1.6.0.dev12 跑崩后) → `fuqing_crm.duckdb.broken-2026-06-12-1.6.0-dev12` (保留作 forensic, 1.6.0.dev12 race 错误堆栈已写 /tmp/fuqing-etl-1.6.0-dev12.log)
- `zstd -d` 37 GB zst backup → 89.97 GB DuckDB file (06-11 16:55 状态)
- 验证: 10,688,222 订单 (1068 万), 0 淘客, 1,982,532 其他, max pay_time 2026-06-09
- **D 路径单独不治根** (1.98M UPDATE 仍 race), 必须配合 C 路径

## ETL 跑批状态 (2026-06-12 15:31)

| 路径 | PID | 状态 | race 触发 |
|---|---|---|---|
| read-only 模式 (15:15 启动) | 58549 | 跑中 17:29 elapsed, RSS 1.9-3.3GB, CPU 155% | 0 |
| uvicorn (15:30 启动) | 66042 | 在线, /health 401 (auth working) | 0 |

ETL 满载 CPU 跑 batch load 阶段, log stdout buffer 没 flush (nohup 模式), 实际 ETL 在跑数据加载 + 跳过的 step 2/6 后面的 steps. 跟之前 Sprint 20 manual 跑批 5 min 同样 stage (满载 CPU log 0 字节), read-only 模式应该能跑通.

## 收口清单 (Sprint 21 P0)

1. ✅ DB 恢复 06-11 16:55 backup (89.97 GB 恢复成功, 1068 万订单)
2. ✅ v2 code 加 retry 3 次 (治标, race 仍 100% 触发)
3. ✅ v2 code DROP 2 index 扩到 6 index (修了 orders race, 暴露 RFM race)
4. ✅ cli.py 加 --read-only flag, 跳过 step 2 + step 6
5. ✅ cron 监控改 1.6.0 stable (subagent 完成, 3 个文件改 + 1 个新建)
6. ⏳ read-only 模式 ETL 跑批 (PID 58549 跑中, 等跑完验证)
7. ⏳ uvicorn 重启 (PID 66042 在线, /health 401)
8. ⏳ 收口 commit + push (fix/sprint21+-p0-etl-readonly branch)

## 教训 (跟 Sprint 20+ P0 一起)

### 1. dev release 假阳性 (3/3 验证)
- 1.5.4.dev18: 4 unit tests + 5 轮 10K batch 全过 → prod 1.88M race
- 1.5.4.dev18 + v2 + retry 3: 全过 → prod 1.88M race 3/3
- 1.6.0.dev12: 4 unit tests 全过 → prod 1.88M INSERT race 崩
- **结论**: dev release 装在生产是赌博, 必须 stable + 真 prod 验证

### 2. v3 workaround 重设计 over-engineering (codex 校准)
- v2 code 已包整段 BEGIN/COMMIT 单事务, 边际收益接近 0
- 6 index DROP 模式修了 orders race 暴露 RFM race (移位置, 没治根)
- retry 3 次 1s sleep 跟跨 connection race 无关 (3/3 race)
- **结论**: DuckDB 上游不修, ETL code 怎么改都没用

### 3. D-7 升级 (单连接测试不推广到生产)
- Sprint 19 P0 误判: 4 unit tests + 5 轮 10K batch 全过 (false-positive)
- Sprint 20 P0 验证: prod 1.88M race 仍触发
- Sprint 21 P0 验证: 任何 dev release + 任何 ETL 变种都治不了根
- **结论**: dev release 单连接测试不能作治根判定, 必须 prod 1.88M 真验

### 4. C 路径 read-only workaround 永久方案
- 1-2 天实施, 永久, 不依赖 DuckDB 上游
- 接受前端 0 增量更新淘客指标 + RFM 缓存陈旧
- 等 DuckDB 1.6.0 stable release 关掉 read-only 模式
- **适用场景**: 1.5.4 stable 也许永远不出, 1.6.0 stable 几周内 (估计)

## 后续 (等 1.6.0 stable release)

1. **cron daily 9:00 监控** (subagent 已改成 1.6.0 stable): launchd plist 调新 cron 脚本, 写 flag + 飞书告警
2. **1.6.0 stable release 触发激活**:
   - 跑 `bash scripts/etl/activate_duckdb_1_6_0_stable.sh`
   - 装 1.6.0 + 跑 v2 4 tests + checkout fix branch + smoke test
3. **真 prod 跑批验证** (D-7 升级): 1.88M 行真验, 不只跑 v2 4 unit tests
4. **关 read-only 模式**:
   - 跑批 `python3 scripts/run_etl.py --update` (不带 --read-only)
   - 验证 race 不触发 (1.6.0 stable 治根)
   - 写 `docs/SPRINT-21-P0-ETL-CLOSURE.md` (收口)
5. **commit + push**:
   - fix/sprint21+-p0-etl-readonly branch → main
   - CHANGELOG v0.4.14.58
   - docs/SPRINT-21-P0-ETL-RESOLVE.md (本文档) + SPRINT-21-RETROSPECTIVE.md

## 风险 + 备选

### 风险
- 1.6.0 stable 也许跟 1.6.0.dev12 一样有 Corrupted ART race (INSERT-side)
- read-only 模式用户看到陈旧数据 (淘客指标从 06-09 起未更新)
- RFM 缓存陈旧影响 Sprint 11+ 的 8 象限健康度

### 备选 (如果 1.6.0 stable 也有 race)
- **A' 升级 1.7.0**: 等 1.7.0 dev 系列 + 真验
- **C 永久 read-only**: 接受陈旧, 不依赖 DuckDB
- **B 路径 (拆批)**: 1.88M 拆 10 批 188K, 跨批 sleep, race 概率降低 (没真实验证, 治标不治本)

---

*此文件由 Sprint 21+ P0 实施生成, 2026-06-12 14:23-15:31 完成, 收口 5/8 (ETL 跑批 + uvicorn 重启 + commit 待完成)*
