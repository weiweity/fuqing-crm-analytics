# A9 T01–T17 G4 独立验收矩阵

作者：A9。`copied_from_a1_a2=false`。<br>
`contract_hash=97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`。<br>
`base_sha=71a65f06f87cb3a5cbd888372487b6b36faaf2a6`。<br>
`plan_snapshot_hash=53f472f11c0ddfdf2106dd71fabe3c22c475a639a93962e95795931be8fb2937`。

SUT（只读）：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-integration`（HEAD 同 base，工作区含 G2/G3 未提交集成）。<br>
本批用 `PYTHONPATH=SUT` + `--import-mode=importlib` 把第一批失败闭合骨架接到真实入口：`competition_compute`、`routers.audience`、`analytics_competition_app`、`competition_assets`、`competition_audience`、`competition-board` UI。<br>
数字仍是 A9 手算夹具，不是 A1/A2/A8 表。未实现或口径不符保持 FAIL。未跑层保持 NOT_RUN。

禁止项已遵守：未占用用户 4327/8000/5173；未跑 T16 容量；未假跑 T13 真实模型；无独立 DSH，T17 NOT_RUN。

## 用例级收口

| ID | 收口 | 契约 | 计算 | HTTP | DOM | 浏览器 | 模型 | 容量 |
|---|---|---|---|---|---|---|---|---|
| T01 | FAIL | PASS | FAIL | FAIL | — | — | — | — |
| T02 | FAIL | — | FAIL | NOT_RUN | — | — | — | — |
| T03 | FAIL | — | FAIL | PASS | — | — | — | — |
| T04 | FAIL | PASS | FAIL | PASS | PASS | — | — | — |
| T05 | FAIL | — | PASS | FAIL | — | — | — | — |
| T06 | PASS | PASS | — | PASS | — | NOT_RUN | — | — |
| T07 | PASS | PASS | — | PASS | — | — | — | — |
| T08 | FAIL | — | — | FAIL | — | — | — | — |
| T09 | FAIL | PASS | — | PASS | FAIL | NOT_RUN | — | — |
| T10 | FAIL | — | — | PASS | FAIL | NOT_RUN | — | — |
| T11 | FAIL | — | — | PASS | FAIL | NOT_RUN | — | — |
| T12 | PASS | — | PASS | PASS | PASS | — | — | — |
| T13 | NOT_RUN | — | — | — | — | — | NOT_RUN | — |
| T14 | FAIL | — | FAIL | NOT_RUN | — | — | — | — |
| T15 | NOT_RUN | — | — | — | — | NOT_RUN | NOT_RUN | — |
| T16 | NOT_RUN | — | — | — | — | — | — | NOT_RUN |
| T17 | NOT_RUN | — | — | — | NOT_RUN | NOT_RUN | NOT_RUN | — |

用例收口：PASS 3 / FAIL 10 / NOT_RUN 4。<br>
分层单元格：PASS 16 / FAIL 12 / NOT_RUN 12。

pytest：32 passed, 11 failed（金标准/HTTP）。node：11 passed, 1 failed（缺编译后 `lib/views/cockpit-view.js`）。

## 接到真实入口后的证据

### T01 日期

- PASS：`shift_year_clamped` / `PeriodBuilder.yoy` 闰日钳到 2023-02-28；7 日窗同比 6 天；上周同星期减 7；跨年同比/cutoff=`start-1`；`end<start` 计算 ValueError、HTTP 422 `INVALID_REQUEST`/`end_date`；默认无 `period` 的 9/1 T+1 走 `empty_mtd_summary` → HTTP EMPTY，不是 8 月。
- FAIL：`PeriodBuilder.mtd(2026-09-01)` 仍回 8/1–8/31。HTTP `period=MTD` 回显 8 月。`compute_competition_metrics(start=09-01,end=09-30,as_of=08-31)` completeness=EMPTY，但 `executed.current_period` 仍是 **09-01..09-30**（A9 禁止未来完整月）。

### T02 / T03 身份与小样

- PASS：`compute_rfm_as_of` 对 O-TRI **F=1**、同日两单 **F=2**；全额退排除购买集；只剔本期 vs 历史重算时 **U-SAMPLE OLD/F=3 vs NEW/F=1**，且 `sample_history_recomputed` 分叉；销售 `CH_RETAIL` 不改历史身份。HTTP `sample_mode` 不得静默丢弃（422）。
- FAIL：本期买家集合不含 GSV=0 的 U-SEP5，A9 要求仍为老客。部分退款按行额 **90** 而非净额 **63**，默认/剔除路径 GSV 变成 **402** 而非 378/375。无独立 T02 HTTP 订单绑定（未对 audience SQL 注入 A9 订单）。

### T04 单位

- PASS：显式 GMV 被计算/HTTP 拒绝；UNKNOWN 会员三桶保留；DOM 源码无 `* 100`。
- FAIL：`safe_ratio(0,0)` 默认 **0**，A9 要求 null。

### T05 cohort

- PASS：向 `CompetitionAudienceService` **注入 A9 C01–C10** 后，原渠道未回 **6 ≠** 全店未回 **4**，C11 不入组，零候选/AND/OR/文案不过期/改规则过期/禁止 auto_send 成立。
- FAIL：HTTP `/candidates/preview` 默认 `FixtureFeatureSource` 返回 A8 `t05u*`，不是 A9 C01–C10。不能把 A8 人数当作 A9 独立验证。

### T06–T12

- T06 PASS：audience 未登录 401 `UNAUTHENTICATED`；跨 actor 403；撤权后 catalog 401/403；无口令泄漏。浏览器层 NOT_RUN。
- T07 PASS：超 `MAX_BODY_BYTES` 非 COMPLETE；坏 JSON ≠ 空成功；失效 result 403/404。
- T08 FAIL：只读 POST 准入与读池 503 retryable 成立；`analytics_competition_app` **无取消/迟到 attempt 发布守卫**。
- T09 HTTP PASS：认可幂等、同键不同 payload 409、批量 PARTIAL。DOM 源码有认可/部分成功。编译后 DOM FAIL（无 `lib/views/cockpit-view.js`）。浏览器 NOT_RUN。
- T10/T11 HTTP PASS：在途 block 不随点选切换（409）、样式预览、放弃≠撤销、If-Match 409。源码选择器/非法 script 拒绝 PASS。编译后 DOM FAIL。浏览器 NOT_RUN。
- T12 PASS：零候选空名单、6/4 集合、文案不过期、规则变更过期、auto_send 拒绝。

### T13–T17

- T13 NOT_RUN：无真实模型配置，未跑 stub。
- T14 计算：无新单 R+1 且 F/M 不变 PASS；无 dated refund 路径 FAIL。
- T15/T16 NOT_RUN。
- T17 NOT_RUN：未启动独立 DSH（不碰用户 4327，也未起 14327）。

## 归属（只建议，不改业务）

| 问题 | Owner |
|---|---|
| MTD 9/1 回 8 月；空窗仍回显 09-01..09-30 | A2 |
| HTTP `period=MTD` 走 PeriodBuilder.mtd | A3 |
| 部分退净额、U-SEP5 零本期 GSV 身份 | A2 |
| `safe_ratio` 零分母=0 | A2 |
| HTTP 人群默认 A8 fixture，不接 A9 订单/特征 | A8 / G2 |
| 比赛 HTTP 无 cancel/late attempt | A3 / G2 |
| 编译后 cockpit-view.js 不在集成树 | A6 / G3 |

## 验证命令

```bash
cd /Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-a9
env -u FQ_TEST_ARCHIVE_DB \
  A9_SUT_ROOT=/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-integration \
  PYTHONPATH=/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-integration \
  python3 -m pytest backend/tests/test_competition_acceptance.py \
    backend/tests/test_competition_acceptance_golden.py \
    --import-mode=importlib -p no:cacheprovider -q
# 32 passed, 11 failed

A9_SUT_ROOT=.../competition-integration \
  node --test dsh-plugins/analytics-workbench/tests/competition-acceptance/*.test.mjs
# 11 passed, 1 failed
```

日志：`validation/pytest-g4.log`、`validation/node-g4.log`、`validation/ruff-g4.log`。
