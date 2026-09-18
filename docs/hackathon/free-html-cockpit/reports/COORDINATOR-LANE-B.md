# 主协调审查 · Lane B

- 状态：Lane B **DONE**（T0/T3/T4 owner 范围）。P01 **DONE**。P04 **PARTIAL**（依赖 P02 生成类型未落地；pipeline 未扫 `src/free-page`；无 C 的真实 `data.read`）
- 审查日期：2026-09-18
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-B`
- 分支 / HEAD：`codex/free-html/lane-b` @ `b45a27bb9022057ce37aa9123927e8b4663a2720`（业务代码 **未 commit** / 未 push）
- 报告：`reports/LANE-B.md`
- 本轮未 merge、未 push、未切 6677（PID **8758**）

## 越界核对（通过）

| 路径 | 结果 |
|---|---|
| `html-sandbox.mjs` | 与主仓相同 |
| `library-board-client.mjs` / `library-workspace.tsx` | 与主仓相同 |
| `pipeline.mjs` / `board_documents.py` | 与主仓相同 |
| `src/free-page/` | 仅 `runtime/` `resource/` `preview/` |
| `frozen-contract-v0.json` | 未改语义 |
| `LEAK_RUNTIME_HTML` | 已删除 |
| T0 计数控件 | 不在 `preview-host.mjs`，只在 isolation-probe 夹具 |

## 复跑证据（本轮主协调执行）

cwd = Lane B worktree。Node **v24.19.0**。

完整 12 个测试文件（含 `isolation-probe.test.mjs` 与旧 `html-sandbox.test.mjs`）：**27 pass / exit 0**，duration_ms ≈ 10384。

T0 Chrome 硬断言通过。本轮探针写入的 `reports/lane-b/t0-evidence.json`：

- Chrome/153.0.8010.48 Headless，viewport 1280×800
- ports harness **52081** / proxy **52082** / chromeCdp **52101**；`avoided: 6677`
- `sandbox: allow-scripts`，`allowSameOrigin: false`
- gates：`host_operable` / `close_restart` / `saved_restore` 全 true
- `cpu_isolation: observed-host-operable-during-srcdoc-runaway`（不是 true）
- `egress_proxy_hit_count: 0`
- `recovery_ms: 1112`

截图可见「已保存经营复盘」标题 + SVG；失控时宿主按钮与 tick（137 1）仍在。`preview-host` 无宿主 tick 控件。

LANE-B.md 里旧端口 59711/59712 与 recovery 1113 是更早一次探针；以本轮 JSON 为准。

## 未运行（不得记通过）

- `scripts/dsh-b0/pipeline.mjs --check`（仍不扫 `src/free-page`）
- P12 真浏览器集成旅程；P13 真实模型
- headed Chrome / D38 宽度矩阵
- Lane C 真实 `data.read`；Lane A SQLite 落盘

## P12 接缝（尚未移植）

1. `pipeline.mjs` 的 competitionTests 加上 `src/free-page`
2. C：`createPageSession({ adapter: { read, cancel } })`
3. A：生成类型替换 `frozen-contract.mjs` 手写常量；破坏性改字段 BLOCKED
4. E：`import { mountPreviewHost } from '.../preview/preview-host.mjs'`
5. 不要扩展 `html-sandbox.mjs`

静态扫描承认拼接 URL 可绕过；运行时 CSP + 代理覆盖。watchdog 不能打断 `while (true)`；终止靠移除 iframe。
