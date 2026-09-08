# 渠道后续购买双会话原生查询（G4b）

日期：2026-09-07。任务分支当时 `codex/channel-followup-native-ui`。基线 G4a `0665976c5b7d5e364b12e7c58f599924556881cf`（[PR #75](https://github.com/weiweity/fuqing-crm-analytics/pull/75)）。当时状态：**核心 native PASS**；Git / full pre-push / 最终 CI **待 Codex**。收口（2026-09-08）：相关代码已在 `main`（经后续 PR 合入），不是仍待提交。

本文件记录 G4b：DSH 原生 UI、gateway 两 session allowlist 和 finite mock 接到恰好两个登记会话。结果由真实 worker SQL 计算。synthetic / finite mock，不是真实业务或付费模型。

## 1. 范围

| 层 | 本单元 |
|---|---|
| serve | `--native-query`；4315–4319；`family=channel_followup`；恰好两登记 session |
| fixture / rpc | 受控 fixture create；恰好两登记 session；browser 无 create/delete |
| mock | 两轮 tool + 两轮文字：A N30、B N60；FIXED `2026-06-01`–`2026-09-01` |
| gateway | 静态两 session allowlist；follow 绑定；第三 session 拒绝 |
| UI | session header 精确选择；query 卡只读 receipt；切换清旧 view |

未做：native cancel / 畸形 producer（**DEFERRED**）。旧 B0 单会话与 25% 卡保持。

## 2. 入口

```text
/Users/hutou/homebrew/opt/node@24/bin/node scripts/dsh-b0/serve.mjs --python /Users/hutou/homebrew/bin/python3.14 --native-query
```

随后：`rpc.mjs bootstrap` → `gateway.mjs` → `http://127.0.0.1:4318/` → `native-query-smoke.mjs`。

## 3. 验证

| 项 | 结果 |
|---|---|
| 独立 93 Node + host/client typecheck/build | **PASS**（`G4b-final-independent-tests.log`、`G4b-final-independent-build-corrected.log`）。不是本卡声称的完整 pipeline clean-copy |
| 保护哈希 29 项 | 未变 |
| 初始 driver | **FAIL** `runtime-cGwjYz`：切 B 按 sessionId 找标题。`G4b-native-initial.log`；`native-query-evidence-1788740616084.json` |
| 手工双问 + `--verify-existing` | **PASS**（只读不重发）。`G4b-native-existing.log`；**`native-query-evidence-1788740880542.json` 是此层 PASS，不是 initial FAIL** |
| 修复后 fresh driver | **PASS** 空库 UI 实发两问，不是 verify-existing。`runtime-zPbEKI/native-query-evidence-1788741825934.json`；`G4b-final-native-driver.log` |
| 正常 full pre-push / 最终 CI | **未验**（Codex） |
| cancel / 畸形 producer | **DEFERRED** |
| 真实业务 / 付费模型 | **NOT RUN** |

fresh 核心：A N30 5/9 净 1100 元，`run_39e2eddd75dd46079ed0c73d23b703b4` / `step_a9cfb889b8e14b57a62a52ce1c1a9efd`；B N60 6/9 净 1150 元，`run_e80b11b830ed4694ad04d9a3bb9a61f4` / `step_558848f5ef0c44dabe68667109e38b0d`。独立 run/request/call/step；`requestForTool` 一致；2 worker EXITED 0、`active_slot=null`、lease 释放。刷新回 A，再 B 再 A，0 新增。SQLite：`G4b-final-sqlite-readonly.json`。负测：`G4b-final-access-negative.json`（A 200 / A 读 B 404 / 第三 403）。视口 1440/768/390：`G4b-final-desktop-a.png` 等；16px / 24px line-height；390 无横向溢出。console 有意 allowlist 403 与 reload 重连，不是零错误。
