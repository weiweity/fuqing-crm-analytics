# Claude Code Automation (Sprint 22.5+)

> Sprint 22.5+ 用 `claude-automation-recommender` 扫 crm-analytics 项目后
> 落地的 Claude Code 自动化配置. 详细推荐: 见 `docs/claude-automation-recommender-report.md` (本次 ship).

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
