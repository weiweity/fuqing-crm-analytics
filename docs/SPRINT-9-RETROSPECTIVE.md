# Sprint 9 Retro — 维修 4 件根因: watchdog / cache key / W3 valid_sql / W4 memory (2026-06-07)

> Sprint 9 = 维修 sprint, watchdog 阈值/cache key/W3 valid_sql/W4 memory 4 件根因一次性治根, 跟 Sprint 10/11 ETL 性能/Phase 4 架构重构联动

## 1. Sprint 结果

Sprint 9 是维修 sprint, 一次性治根 4 件 ETL 痛点: watchdog 阈值 (ETL 跑批 hang 死时 watchdog 不报警), cache key (W5 DuckDB-KV cache key 不含 algo_version 跨 sprint 漂移), W3 valid_sql (W3 跑批 SQL 错未拦截), W4 memory (W4 跑批 OOM). 期间跟 Sprint 10 B1 preflight (staging NOT EXISTS / W4 8GB / RSS 12GB 硬限) 联动, Sprint 9 治根, Sprint 10 加硬限. 同步修 DMP 6/8 Sprint 1 修复全文档同步.

**主要交付** (4 件治根 + 1 文档同步):
- 维修 1: watchdog 阈值 (修 hang 死无报警)
- 维修 2: W5 cache key (含 algo_version 跨 sprint 漂移)
- 维修 3: W3 valid_sql (跑批 SQL 错拦截)
- 维修 4: W4 memory (OOM 修)
- DMP 6/8 Sprint 1 修复全文档同步 (`9bae100`)

## 2. 关键 commit

| SHA | 主题 | 任务 |
|-----|------|------|
| `35d109a` | merge: Sprint 9 维修 — watchdog/cache key/W3 valid_sql/W4 memory | 收口 merge |
| `cedcbbb` | fix(etl): Sprint 9 维修 — watchdog 阈值/cache key/W3 valid_sql/W4 memory | 4 件治根 |
| `9bae100` | docs(scraper): 6/8 Sprint 1 修复全文档同步 | DMP doc |
| `741b35c` | feat(scraper): T_OFFSET 动态 + launchd 调度文档 | 衍生 |
| `21b44cd` | fix(scraper): T+1 → T+2 保护 (达摩盘单品数据最少 T+2 滞后) | 衍生 |
| `9ea6ab5` | fix(scraper): T+1 保护 — get_missing_dates_item 跳过今天和昨天 | 衍生 |
| `bcdf71a` | fix(frontend): YOY 显示精度 toFixed(1) → toFixed(2) | 衍生 |
| `199d328` | docs(changelog): v0.4.14.18 MetricCard YOY 0.1% → 7.5% 修复 | 衍生 |
| `9ae1941` | Merge pull request #23 from weiweity/fix/metriccard-yoy-decimal | 衍生 |
| `0c576c8` | fix(audience): MetricCard unit='%' 卡片 change 值改用 *Pct 包装器补 * 100 | 衍生 |
| `dd61f8d` | docs(changelog): v0.4.14.17 R 桶分桶修复 + 缓存清理说明 | 衍生 |
| `30dc8e0` | Merge pull request #22 from weiweity/fix/r-bucket-recency-preperiod | 衍生 |
| `0243735` | fix(rfm): R 桶分桶改回 cutoff_dt (= start_dt - 1) 截止 | Sprint 8 P0 衍生 |
| `6faef99` | fix(scraper): 删除 Gate 1+Gate 2 数值跳过逻辑 | 衍生 |
| `5fbeffb` | fix(backend): RFM 8象限 R/F/M 评分改为 start_dt 前行为 + 回购口径 ≥1 单 | 衍生 |
| `f94d3cf` | fix(frontend): 人群看板 YOYBadge 模式修正 — 占比/率用pp, 绝对值用% | Sprint 8 P0 衍生 |

## 3. 教训

1. **"维修 sprint" 模式**: Sprint 9 立下"维修 sprint"工作流 (4 件治根一次性), 跟 Sprint 6 (4 件并行) / Sprint 18 (4 件并行) 不同, Sprint 9 是同主题 (ETL 痛点) 多件并行, 后续 Sprint 10 B1 preflight 沿用.
2. **Sprint 8 P0 衍生**: Sprint 9 期间修了 Sprint 8 P0 的衍生 (R 桶改回 cutoff_dt, YOYBadge 模式修正), 说明 Sprint 8 P0 没一次治根. Sprint 16 又有 Sprint 11+ 衍生 (YOY/pp 5 层修法), 治理债务会跨 sprint 反弹.
3. **Sprint 9 → Sprint 10 联动**: Sprint 9 治根 + Sprint 10 B1 preflight 硬限 = 两层防护, 后续 Sprint 14-18 都沿用 "治根 + 硬限" 模式.

## 4. 关键指标

- **commits**: 16+ main commits (1 merge + 1 fix 主体 + 1 doc + 13 衍生)
- **主要文件**: `scripts/etl/watchdog.py` (阈值修) + `backend/services/rfm/w5_cache.py` (cache key 加 algo_version) + `scripts/etl/w3_valid_sql.py` (新) + `scripts/etl/w4_memory.py` (新) + `docs/scraper/*.md` (6/8 同步) + `docs/SPRINT-9-RETROSPECTIVE.md` (补齐)
- **version**: v0.4.14.16/17/18 (Sprint 9 衍生)
- **tests**: 沿用 141+ root test passed + 459+ 既有
- **main commit**: `35d109a`
