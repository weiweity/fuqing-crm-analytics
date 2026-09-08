# 8 小时 Goal 交接（G5）

**当时提交前快照（2026-09-07）。** 收口（2026-09-08）：G4b 及后续查询资产已合入 `origin/main`（#100 等）；开放 PR 0。下文「待 Codex / 无 merge」只描述当时窗口，不是现在的 Git 状态。

窗口：`2026-09-06T17:18:01Z` → `2026-09-07T01:18:01Z`（`.context/goal-8h/state.json`）。时间盒，不是产品完成。工作树当时 `.worktrees/hackathon-mission-mvp`，分支 `codex/channel-followup-native-ui`，当时 HEAD `0665976c`（G4a / PR #75）。G4b 源码当时仍为未提交 dirty。

## 单元状态

| 单元 | 状态 | 口径 |
|---|---|---|
| G0 | PASSED | 规划与账本；当时未跑业务测试 |
| G1 | PASSED | 原生四态 `runtime-SNWYss`；第一次 `hkeo4K` F3 失败保留 |
| G2 | PASSED | `analytics-channel-followup/v1` 手算金标准；合成候选，非正式业务批准 |
| G3 | PASSED | 离线 SQL、受信 store、共享 worker。各层用例数不相加 |
| G4a | PASSED（无浏览器） | ASGI / 真实 worker / 真实 Cordis loader |
| G4b | 核心 native **PASS** | 接线 + 修复后 fresh driver `runtime-zPbEKI`。Git / 正常 full pre-push / 最终 CI **待 Codex** |
| G5 | 本文快照 | 最终 Git/进程以 Codex 交付为准 |

收缩：新 query 原生 cancel / 畸形 producer UI **DEFERRED**。历史三次 supervisor 退出 **UNKNOWN**。仅第一查询族。保存/触达/驾驶舱/真实数据/另两查询族未做。无真实业务、无付费模型。

## Git / CI（state.json 已核；无 merge）

| PR | 内容 | head | CI |
|---|---|---|---|
| [#68](https://github.com/weiweity/fuqing-crm-analytics/pull/68) | 规划 | `26960bb3cd7edddc125d05e00a23d22511768620` | 候选绿（docs path；业务 job SKIPPED） |
| [#69](https://github.com/weiweity/fuqing-crm-analytics/pull/69) | T09 | `bd6d8fe9f3444144f7ed7d8768c232459ea7e75d` | 34049400372 / 34049400375 |
| [#70](https://github.com/weiweity/fuqing-crm-analytics/pull/70) | G1 | `857d2cee7096027b87dc6ca1f2dfd0720fb1a7fd` | 34052132760 / 34052132799 |
| [#71](https://github.com/weiweity/fuqing-crm-analytics/pull/71) | G2a | `ae02f873cfdbfc5a53e3fe8e5ae137872f1203a1` | 34054988588 / 34054988701 |
| [#72](https://github.com/weiweity/fuqing-crm-analytics/pull/72) | G3a | `754dbd8982a5911cb369bba0d6ecb11b7da66a81` | 34060784432 / 34060784439 |
| [#73](https://github.com/weiweity/fuqing-crm-analytics/pull/73) | G3b1 | `15585855582cad2600be13f0335c07bb332fefde` | 34063926629 / 34063926688 |
| [#74](https://github.com/weiweity/fuqing-crm-analytics/pull/74) | G3b2 | `305f0ede2b6df7e1dc426a49ab86da881c3bae5e` | 34065301972 / 34065302035 |
| [#75](https://github.com/weiweity/fuqing-crm-analytics/pull/75) | G4a | `0665976c5b7d5e364b12e7c58f599924556881cf` | **34067738860 / 34067738867 SUCCESS** |

#68–#75 候选均已核绿。G4b 尚未形成新 PR。

## G4b 原生分层（synthetic / finite mock）

| 层 | 结果 | 证据 |
|---|---|---|
| 初始 driver | **FAIL** 切 B 按 sessionId 找标题 | `G4b-native-initial.log`；`runtime-cGwjYz/native-query-evidence-1788740616084.json` |
| 手工双问 + `--verify-existing` | **PASS**（只读，不重发） | `G4b-native-existing.log`；`native-query-evidence-1788740880542.json`；`G4b-initial-a.png` / `G4b-initial-b.png` |
| 修复后 fresh driver | **PASS**（空库 UI 实发两问，不是 verify-existing） | `runtime-zPbEKI/native-query-evidence-1788741825934.json`；`G4b-final-native-driver.log` |
| 独立 Node 93 + typecheck/build | **PASS** | `G4b-final-independent-tests.log`；`G4b-final-independent-build-corrected.log` |
| 正常 full pre-push / 最终 CI | **未验** | 待 Codex |
| cancel / 畸形 producer | **DEFERRED** | — |

fresh：A `run_39e2eddd75dd46079ed0c73d23b703b4` / `step_a9cfb889b8e14b57a62a52ce1c1a9efd`，N30、5/9、净 1100 元；B `run_e80b11b830ed4694ad04d9a3bb9a61f4` / `step_558848f5ef0c44dabe68667109e38b0d`，N60、6/9、净 1150 元。两独立 run/request/call/step；`requestForTool` 一致；2 worker EXITED 0、`active_slot=null`、物理 lease 释放。刷新回 A，再 B 再 A：0 新 runs/steps/workers/native calls。SQLite 只读对齐：`G4b-final-sqlite-readonly.json`。负测 `G4b-final-access-negative.json`：A 自有 200、A 读 B 404、第三 session 403。视口 `G4b-final-desktop-a.png` / `-desktop-b.png` / `-tablet.png` / `-mobile.png` / `-mobile-reference.png`（1440/768/390；16px/24px line-height；390 无横向溢出）。console 有意 403（inventory/inspect/credentials 等 allowlist）及 reload 重连，**不是零错误**；无 query 卡异常。

29 保护哈希未变。Native 服务由 Codex 停止（supervisor 57288 等）；owned tab 3 已关。原 demo 36717/36727 保留；最终进程 live 以 Codex 报告为准。

## 下一步

本次 PR / 正常 pre-push / CI 交付之后，优先新 query 原生 cancel / fault。历史三次 supervisor **UNKNOWN**。整体产品未完；第一查询族仅为合成候选，无真实模型与业务数据。
