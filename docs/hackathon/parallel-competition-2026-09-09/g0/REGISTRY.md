# G0 总控登记（2026-09-09）

状态：`BATCH1_DISPATCHED / C0_PENDING`。总控：Grok。不开第二总控。子 Agent 不得再分派。

## 仓库基线（实测，不沿用历史 SHA）

| 项 | 值 |
|---|---|
| 主仓 cwd | `/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics` |
| 分支 | `main`（dirty，未 stash/reset/commit） |
| HEAD / base_sha | `71a65f06f87cb3a5cbd888372487b6b36faaf2a6` |
| 规划快照 hash | `53f472f11c0ddfdf2106dd71fabe3c22c475a639a93962e95795931be8fb2937` |
| C0 contract_hash | `PENDING_C0`（A1 冻结后由总控验收填入） |
| 快照文件清单 | `g0/PLAN-SNAPSHOT-FILES.sha256`（17 个白名单文件） |

未纳入快照的未跟踪文件（与本轮交付无关）：`ARCHIVE.md`、`docs/hackathon/GOAL-PARALLEL-GSTACK-2026-09-08.md`、`docs/hackathon/GOAL-PARALLEL-GSTACK-START-2026-09-08.md`、`docs/hackathon/GOAL-PARALLEL-TRACK-TEMPLATE-2026-09-08.md`。

规划白名单已覆盖到各工作树的规范路径；工作树 tracked 代码来自 HEAD，不是整份 dirty 工作区拷贝。未复制 `.context`、node_modules、真实 DuckDB、上游依赖树。LFS smudge 已跳过。

## 用户已有进程（禁止停止/复用/改配置）

| PID | 端口 | cwd / 说明 | owner |
|---|---|---|---|
| 81058 | 127.0.0.1:4327 | 主仓 `.context/dsh-dev/runtime/workspace`，DSH `--profile web` | 用户演示 |
| 36717 | 127.0.0.1:8000 | `.worktrees/hackathon-mission-mvp` uvicorn `backend.main:app` | 用户已有（2026-09-05） |
| 36727 | 127.0.0.1:5173 | 同上 Vite | 用户已有（2026-09-05） |

## 第一批工作树

| Agent | 模式 | 分支 | 绝对 cwd | 预留端口 | 重型测试 |
|---|---|---|---|---|---|
| A1 | 实施 C0 合同 | `codex/competition-a1` | `/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-a1` | 18080 仅离线/临时 OpenAPI，默认不要占用 | 禁止 |
| A2 | 只读口径核验 + 手算夹具设计 | `codex/competition-a2` | `/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-a2` | 无 | 禁止 |
| A4 | 基座/品牌壳/主题导出 | `codex/competition-a4` | `/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-a4` | DSH 14327 / Vite 15173；默认本批不启动 | 禁止 |
| A9 | 独立反例与验收表 | `codex/competition-a9` | `/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/.worktrees/competition-a9` | 无 | 禁止 |

第一批 subagent_id：A1 `01a08565-a67b-7251-b4ff-7445541cf22b`；A2 `01a08565-a67d-70e0-b708-c102dd94137a`；A4 `01a08565-a67d-70e0-b708-c1156e8f0820`；A9 `01a08565-a67d-70e0-b708-c12a34d56028`。详见 [DISPATCH-BATCH1.json](./DISPATCH-BATCH1.json)。

第二批 A3/A5/A8 与第三批 A6/A7 尚未建树、未派发。

## 只读复用

- 固定上游：主仓 `.context/dsh-b0/upstream`（SHA 以仓库记录为准）。禁止 `--prepare`、禁止并发安装/重建。
- 插件 `node_modules`：只读复用主仓 `dsh-plugins/analytics-workbench/node_modules`。禁止在子工作树 `pnpm install`。
- CodeGraph：主仓有 `.codegraph/`（gitignore）。子树不必复制；MCP `codegraph_explore` 的 `projectPath` 用主仓路径。不可用则 `rg`/`read_file`。禁止 `codegraph init`。
- Python：本机 `python3` = 3.14.4。B0 检查需要时用绝对解释器，不升级。

## 公共文件 owner（提醒）

`backend/main.py`、`backend/analytics*_app.py`、jobs/runtime/access/worker/catalog/queries、插件 `src/index.ts` / `client/index.tsx` / bridge runtime / asset-http transport / pack-skills / 依赖锁 / CI / 主计划文档：**Grok 总控**。各轨只交精确接线 diff，不得直接改。
