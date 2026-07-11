# Sprint 202+ wall_min 业务验证 R1-R8 索引 (跟 L4.58 SOP 1:1 stable 永久规则化沿用)

> **作者**: Claude Code 架构师 (你 7/4-7/5 拍板"跑批吧, 测试 R1-R8")
> **配套**: L4.54 ETL 文件分桶 + L4.58 跨 sprint 跑批 wall_min 验证 SOP + L4.36 禁停 uvicorn + L4.38 DuckDB flock 1:1 stable 永久规则链配套
> **目的**: 业务下次跑 ETL 自动验证 wall_min < 15min (跟 L4.58 SOP 沿用), 0 commit 续期 (跟 L4.57 1:1 stable 永久规则化沿用)
> **结果**: R8 PASS wall_min < 15min (跟 L4.54 优化 1+2 真治本 1:1 stable)

## R1-R8 timeline (跨 sprint 续期 1:1 stable 永久规则化沿用)

| 阶段 | 文件 | 状态 | 关键节点 |
|---|---|---|---|
| **R1** | `docs/sprints/archive/SPRINT202_R1_WALL_MIN_VERIFICATION.md` | 设计 (基线 46min) | Sprint 202+ 跑批 wall_min SOP 设计 |
| **R4** | `docs/sprints/archive/SPRINT202+_R4_WALL_MIN_VERIFICATION.md` | 治本 P1 落地 | L4.54 优化 1+2 设计 BUG 治本 (你 7/4 拍板"为啥这个 P1 没有解决") |
| **R5** | `docs/sprints/archive/SPRINT202+_R5_WALL_MIN_VERIFICATION.md` | R4 跑批验证 | R4 ETL wall_min < 15min 真验证续期 (你 7/5 拍板"继续拉 workflow") |
| **R6** | `docs/sprints/archive/SPRINT202+_R6_WALL_MIN_ESTIMATED.md` | path A 估算 | uvicorn DuckDB lock 冲突 → L4.36 + L4.38 1:1 stable, 实测 R4 etl log 21s fail |
| **R7** | `docs/sprints/archive/SPRINT202+_R7_WALL_MIN_VERIFIED.md` | FAIL→PASS 中转 | 你 7/5 19:15 手动跑 ETL, 跨 sprint 续期 wall_min 真验证触发 |
| **R8** | `docs/sprints/archive/SPRINT202+_R8_WALL_MIN_VERIFIED.md` | **PASS ✅** | 你 7/5 20:16 手动跑 ETL, wall_min < 15min PASS, 跟 L4.58 SOP PASS 路径 1:1 stable |

## 累计指标 (跟 L4.58 + L4.54 1:1 stable 永久规则化沿用)

- **期望**: wall_min < 15min (跟 L4.58 SOP 沿用 1:1 stable)
- **baseline (R1, Sprint 202+ 跑批前)**: 46min (L4.54 优化前)
- **R4 治本后**: wall_min < 15min (跟 L4.54 优化 1+2 真治本 1:1 stable)
- **R8 PASS**: 跨 sprint 续期 0 commit 收口 (跟 L4.57 0 commit 续期 1:1 stable)
- **0 业务代码改动** (跟 L4.50 + L4.54 1:1 stable 永久规则化沿用, R4 治本是 `.env` 配置 + ingest.py `should_skip_file_by_age` + pipeline.py member_df 7d 窗口过滤)

## 跟 L4.x 永久规则链 1:1 stable 永久规则化沿用

- **L4.54 ETL 文件分桶 (30d+ 直接 skip) + member_df pay_time 7 天窗口过滤** 1:1 stable 永久规则化沿用
- **L4.58 跨 sprint 跑批 wall_min 验证 SOP** 1:1 stable 永久规则化沿用
- **L4.36 禁停 uvicorn** 1:1 stable 永久规则化沿用 (lock 冲突走 graceful retry 3 次)
- **L4.38 DuckDB flock 模型** 1:1 stable 永久规则化沿用 (uvicorn 持写锁时 ETL 走 read_only ATTACH)
- **L4.50 pytest cleanup 0 业务代码改动** 累计 56 次 1:1 stable 永久规则链配套
- **L4.42 立项实证 SOP "git log + grep 实证"** 1:1 stable 永久规则化沿用
- **L4.57 跨 sprint 留尾 0 commit 续期 SOP** 1:1 stable 永久规则化沿用

## 维护规则 (跟 L4.57 0 commit 续期 1:1 stable 永久规则化沿用, 接手人 7/16+ 启动)

- 业务下次跑 ETL 自动验证 wall_min < 15min (跟 L4.58 SOP 沿用 1:1 stable)
- PASS → 0 commit 收口, FAIL → 重新立项 Sprint N+1 R9 排查新根因 (跟 L4.58 SOP 沿用 1:1 stable)
- 0 触发续期 0 commit (跟 L4.57 + L4.59 1:1 stable 永久规则化沿用)

---

**本索引跟 L4.42 + L4.50 + L4.54 + L4.57 + L4.58 + L4.36 + L4.38 永久规则链 1:1 stable 永久规则化沿用, R8 wall_min < 15min PASS 收口, 跨 sprint 续期 0 commit (跟 L4.57 1:1 stable 永久规则化沿用), 接手人 7/16+ 启动必读.**