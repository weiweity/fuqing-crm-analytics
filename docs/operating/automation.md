# Claude Code Automation (Sprint 22.5+)

> Sprint 22.5+ 用 `claude-automation-recommender` 扫 crm-analytics 项目后
> 落地的 Claude Code 自动化配置. 详细推荐: 见 `CHANGELOG.md` v0.4.14.72 (Sprint 22.5+ ship 收口).

## 3 Hooks (`.claude/settings.json`)

### P0-1: PreToolUse — 禁 .env / .duckdb 编辑
**作用**: Edit|Write 工具调 `.env` / `data/processed/*.duckdb` 时 exit 2 拦截.  
**防**: 100GB DuckDB 文件误删 + secrets 误改.  
**验**: 改 `.env` → 报 "BLOCKED: sensitive file". 改 `backend/main.py` → 放行.

### P0-2: PostToolUse — 改 contract 提醒 regen types
**作用**: 改 `backend/contracts/*.py` 时打印 `[contract 改动] 提醒: 跑 /regen-types 重新生成 frontend types.ts`.  
**防**: Pydantic 字段改了, 前端 types.ts 没 regen → 30+ vue-tsc 错.  
**联**: `.claude/skills/regen-types/SKILL.md` 提供完整 regen 流程.

### P0-3: PostToolUse — .py 自动 ruff lint
**作用**: Edit|Write `.py` 时自动 `ruff check <file>` (30s timeout).  
**防**: commit 前才发现 lint 错. session 内早抓.

## 2 Skills (`.claude/skills/`)

### regen-types (P1-1)
**触发**: 改了 `backend/contracts/*.py`.  
**4 步**: 1) 启 uvicorn 临时 :8001  2) curl /openapi.json  3) `npx openapi-typescript` 生 types  4) `vue-tsc -b` 验 0 错.  
**详**: `.claude/skills/regen-types/SKILL.md`.

### ship-pr (P1-2)
**触发**: 任何代码改动 ship 到 main.  
**6 步**: 1) feat/fix branch  2) commit  3) push  4) `gh pr create`  5) CI 绿  6) `gh pr merge --squash`.  
**替**: P3 session 直接 `git merge --no-ff main` 跳过 PR 流程.  
**优**: CI 检查 + 公开 repo 留 PR review trail.

## 1 MCP Server (`.mcp.json`)

### context7 (P2-1, **待用户授权装**)
**作用**: 实时查 FastAPI / Pydantic v2 / Vue 3.5 / ECharts 6 / Vitest / Playwright / openapi-typescript 文档.  
**装法**: 用户手动跑 (auto mode 要求显式授权外部 npx 包):
```bash
claude mcp add context7 -- npx -y @upstash/context7-mcp
```
或参考官方: https://github.com/upstash/context7  
**启**: 重启 claude code session.

## 跟 CLAUDE.md 12 步流程配合

| 12 步 | 用什么 |
|---|---|
| ① git checkout -b | (shell) |
| ② 写代码 | Edit/Write (被 P0-1 hook 拦敏感文件) |
| ③ pytest | Bash (被 P0-3 hook 提早 ruff) |
| ④ review | (review skill, 当前 session) |
| ⑤ 修 review | Edit/Write |
| ⑥ commit | (shell, pre-commit hook 兜底) |
| ⑦ push | (shell) |
| ⑧ qa | (qa skill, 当前 session) |
| ⑨ merge | **ship-pr skill 推荐** (PR 模式) |
| ⑩ push main | (PR 合并自动) |
| ⑪ pull | (shell) |
| ⑫ restart uvicorn | (shell) |

## 优先级

| P | 名称 | 工作量 | 状态 |
|---|---|---|---|
| 🔴 P0-1 | PreToolUse 禁敏感 | 5 min | ✅ ship |
| 🔴 P0-2 | PostToolUse regen 提醒 | 10 min | ✅ ship |
| 🔴 P0-3 | PostToolUse ruff | 5 min | ✅ ship |
| 🟠 P1-1 | regen-types skill | 30 min | ✅ ship |
| 🟠 P1-2 | ship-pr skill | 1h | ✅ ship |
| 🟡 P2-1 | MCP context7 | 1 min | ⏸ **待用户授权** |
| 🟡 P2-2 | Subagent duckdb-optimizer | 1h | ⏸ Sprint 23+ |
| 🟢 P3-1 | Skill duckdb-stress | 1h | ⏸ Sprint 23+ |
| 🟢 P3-2 | Subagent contract-auditor | 1h | ⏸ Sprint 23+ |

---

## WorkBuddy MCP E2E (Sprint 188+)

> WorkBuddy 通过 `~/.workbuddy/.mcp.json` 注册 `fuqing_adhoc` stdio MCP server
> 调 11 个 ad-hoc-query tool。Sprint 182 落 server 后, Sprint 188 起补 **真端到端
> 验证** 替代纯 mock 测试。

### 工作流

| # | 文件 | 说明 |
|---|---|---|
| 1 | `mcp_servers/fuqing_adhoc/server.py` | 手写 stdio JSON-RPC framings, ~30 行 (无 third-party mcp SDK) |
| 2 | `mcp_servers/fuqing_adhoc/_dispatch.py` | 11 tool TOOL_DEFS SSOT (10 query + 1 ask; Sprint 183 加 daily-gsv-multi-period) |
| 3 | `~/.workbuddy/.mcp.json` | WorkBuddy 注册 `fuqing_adhoc` 用 `${HOME}` env 展开 (L4.34 跨平台) |
| 4 | `~/.workbuddy/skills/ad-hoc-query/SKILL.md` (symlink → `~/.claude/skills/ad-hoc-query/SKILL.md`) | L4.35 跨端 SKILL SSOT |

### 真端到端验证 (Sprint 188 Phase 1 B2)

**目的**: Sprint 182 起的 `backend/tests/test_fuqing_adhoc_mcp_server.py` 部分 case 用
`mock.patch` 替代 subprocess, **看不到真实 stdio 通讯** (L4.32 cwd lock / L4.41
PYTHONPATH 锁回归虽然在 Sprint 187 治根, 但 mock 路径不真打 server, 跨 sprint 容易
漂移)。Sprint 188 起补 **真发 JSON-RPC** 测试:

```bash
# 1. 手跑 e2e 脚本验证 stdio 通讯 (mock backend 替代)
PYTHONPATH="$(pwd)" python3 scripts/e2e_workbuddy_test.py

# 期望输出:
#   - tools/list 返 11 tools (含 daily-gsv-multi-period)
#   - tools/call daily-gsv-multi-period 走通 dispatch (DuckDB 锁冲突时 graceful error)
#   - exit 0 + "Sprint 188 e2e: 全部 PASS"

# 2. 跑 pytest 锁回归 (7 case)
PYTHONPATH="$(pwd)" pytest backend/tests/test_workbuddy_e2e.py -v
# 期望: 7 passed

# 3. (可选) 跑 Codex CLI 真接入, 验证 Codex 也走 MCP
codex ...  # Sprint 188+ 用 Codex 端到端 case
```

**关键 L4 永久规则配套**:
- **L4.32** subprocess cwd lock (server.py:cwd=PROJECT_ROOT)
- **L4.34** Path.resolve() 跨平台 (禁硬编码 `/Users/hutou`)
- **L4.35** SKILL.md symlink SSOT (跨端不复制粘贴)
- **L4.38** DuckDB 跨进程架构 (uvicorn 写锁 + CLI/MCP 读锁 分进程)
- **L4.41** env[PYTHONPATH]=str(PROJECT_ROOT) 强制绝对路径 (Sprint 187 真因)

**已知 blocker**:
- DuckDB 锁冲突 (Sprint 53 race flake 沉底) → MCP server graceful error 返
  `isError=true` + stderr 含 `IO Error: Could not set lock`, pytest 接受
  `isError=true` 当作协议层正确路径
- WorkBuddy LLM 走 MCP tool (无 shell) → Sprint 183 SKILL.md v2.2 "执行路径强制"段
  强制走 MCP, 禁临时 `scripts/adhoc_*.py` (违反 L4.5 复用)

### pytest 标记约定

| 标记 | 例子 | 触发条件 |
|---|---|---|
| `@pytest.mark.e2e` | (建议加给 `test_workbuddy_e2e.py`) | 慢测 / 真启 subprocess / CI runner 可跳过 |
| `@pytest.mark.skipif(not shutil.which("codex"))` | `test_codex_cli_present_acknowledged` | Codex CLI 未装时跳过 |

**实际触发文件**: `backend/tests/test_workbuddy_e2e.py` (Sprint 188 落,
替代 Sprint 182 mock 部分路径)。
