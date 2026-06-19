# HANDOFF-TO-CODEX — Sprint 实施 plan doc 模板

> **目标读者**: Codex app (GPT-5.5 实施者)
> **生成者**: Claude Code (架构师)
> **生成时机**: 每个 sprint 开始时 (Stage 1 产物)
> **使用方式**: 你复制本文给 Codex app, Codex 读后本地编辑代码

---

## 模板 (Sprint 实施时填实际内容)

```markdown
# HANDOFF-TO-CODEX — Sprint [XX] [#SXX-X]

> **目标读者**: Codex app (GPT-5.5 实施者)
> **生成者**: Claude Code (架构师)
> **生成时间**: [YYYY-MM-DD]
> **Sprint 类型**: [实施 / 复杂代码 / bug fix / 文档]

---

## TL;DR — 30 秒上手

| 项 | 值 |
|---|---|
| **任务** | [Sprint XX 业务目标, 1-2 句话] |
| **修改文件** | [列出所有要改的文件 + 改动概要] |
| **新增文件** | [列出所有新增文件] |
| **删除文件** | [列出所有删除文件, 或 "无"] |
| **预期工作量** | [Xh / X天] |
| **实施完成后** | Claude Stage 3 review + commit + push |

---

## 1. 任务背景

[2-3 段说明 Sprint 来源 + 业务需求 + 为什么这个 sprint]

例: Sprint 41 e2e CI 0→1 实战失败改 advisory (Sprint 41.12), Sprint 42 spec-lint 预防层 + 3 层防御框架沉淀 (Sprint 42 #S42-1), Sprint 43 spec-lint 改 blocking + 修 7 真违反. 现在 Sprint [XX] [从某 sprint 留尾接过来].

---

## 2. 架构意图 (Claude 设计)

[1-2 段说明 Claude 的关键设计决策, 包括]
- 为什么这样改 (不那样改)
- 跟现有架构兼容点
- 引入的新 pattern (如果引入了, 标记 + 加 review skill 强制)

例:
- **Sprint 43 #S43-2**: 删冗余 waitForTimeout 而不是替换 (后面 expect visible 30s 自己 wait)
- **不引入**新 pattern, 跟 Sprint 32.2 #S32-2 兼容
- **不引入**新 abstract, 改最简版本

---

## 3. 实施步骤 (按文件分)

### 3.1 改文件 1: `[path/to/file.ts]`

```diff
- old code line
+ new code line
```

[说明 +1-2 句]

### 3.2 改文件 2: `[path/to/file.py]`

```diff
- old code line
+ new code line
```

[说明]

### 3.3 新增文件: `[path/to/new-file.sh]`

[完整内容或链接]

### 3.4 删除文件 (如有)

[删除理由 + 影响范围]

---

## 4. 验收标准 (跑完这些算完成)

- [ ] `pytest backend/tests/` (排除 race flake) 通过 0 failed
- [ ] `bash frontend-vue3/e2e/lint/spec-lint.sh` 0 violation
- [ ] `bash frontend-vue3/e2e/lint/__tests__/spec-lint.test.sh` 3/3 case pass
- [ ] `npx playwright test` (本地 uvicorn + Vite preview 已启) 11/11 spec pass
- [ ] `git diff` 跟本 HANDOFF 步骤 3 一致 (无意外改动)
- [ ] 跨 sprint 实战 fix 模式 ROI 重评通过 (引 CLAUDE.md L5.1)
- [ ] 引用的 L4.3/L4.4/L5.1/L5.2 永久规则没破坏

---

## 5. 跨 sprint 实战教训 (Codex 必读)

引自 [CLAUDE.md L4-L5 永久规则](./CLAUDE.md) + [docs/CI-DEFENSE-PLAYBOOK.md](./docs/CI-DEFENSE-PLAYBOOK.md):

### 5.1 实战 fix 模式 ROI 重评 (Q1-Q4)

```
Q1: 本地能跑通吗? → C 类 (环境差异) / A/B 类 (修代码/spec)
Q2: 根因是 spec/代码 还是环境? → 修 vs 治本/治标评估
Q3: 治本 1-2 天能闭环吗? → 治本 vs 治标
Q4: 治标会反复出现吗? → 写 lessons learned + trigger 评估
```

**N > 5 还没闭环 → 改治标/advisory 0→1 是务实选择**。

### 5.2 Sprint 41 实战 fix 12 follow-up 教训

[引 docs/SPRINT-41-CI-LESSONS-LEARNED.md 关键 5 点]
- GH Actions runner 跟本地差异 (14GB disk + headless Linux + 没 DuckDB)
- Playwright 3 个 timeout 区别 (timeout / expect.timeout / navigationTimeout)
- 错误可见性 > 优雅失败 (set -e + redirect log, 别用 || true 吞错)
- spec-lint Rule 2 waitForTimeout 死等 (这次 sprint 改了, 别再回退)
- Sprint 41.11 uvicorn set -e + redirect log (Sprint 41.12 e2e advisory)

### 5.3 Sprint 32-43 lint 防御模式

[如果 sprint 涉及 lint 规则改动, 引 CLAUDE.md L5.1+L5.2]
- **L5.1**: CI 留尾 ROI 重评规则 (review skill 强制)
- **L5.2**: spec 写法"环境无关"原则 (不 hardcode 长度 / 不 waitForTimeout / page.request 加 Authorization)

---

## 6. 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| [Codex 可能引入的新 pattern 跟 L4-L5 永久规则冲突] | 验收标准第 7 条强制 check |
| [Codex 可能 hardcode 数据 / timeout 不 env-driven] | 引 L5.2 spec 写法原则 |
| [Codex 引入新的 lint 误报率] | 起步 advisory 模式 (跟 spec-lint Sprint 42 一致) |
| [Codex 没跑 e2e 就 commit] | 验收标准第 4 条强制 check |

---

## 7. 不在 scope

- ❌ [明确列出 Codex 不要做的]
- ❌ [避免 scope creep]
- ❌ [跟 Sprint 边界明确]

---

## 8. 实施完成后, 你的下一步

1. 跟 user 说: "Codex 完成, 切回 Claude"
2. Claude Stage 3 review + Stage 4 commit + push
3. user 看 push 结果确认

---

## 关联文件

- [CLAUDE.md](./CLAUDE.md) - L4.3/L4.4/L5.1/L5.2 永久规则
- [docs/CI-DEFENSE-PLAYBOOK.md](./docs/CI-DEFENSE-PLAYBOOK.md) - 3 层防御
- [docs/SPRINT-41-CI-LESSONS-LEARNED.md](./docs/SPRINT-41-CI-LESSONS-LEARNED.md) - 12 follow-up
- [HANDOFF.md](./HANDOFF.md) - 工作流文档
- [/Users/hutou/.claude/projects/-Users-hutou/memory/MEMORY.md](../../../../../.claude/projects/-Users-hutou/memory/MEMORY.md) - 全局索引

---

## 模板使用说明

1. 复制本模板
2. 替换方括号 `[...]` 部分为 sprint 实际内容
3. Claude Stage 1 完成时输出这个文件 (`HANDOFF-TO-CODEX-Sprint-[XX].md`)
4. 你复制内容给 Codex app
5. Codex 本地编辑代码
6. Codex 完成后你切回 Claude
7. Claude review + commit + push
```

---

## 示例: Sprint 50+ pre-flight check shell script (Sprint 50+ 适合 Codex 实施)

> 完整示例 — 假设要做的 sprint

```markdown
# HANDOFF-TO-CODEX — Sprint 50+ #S43-3 pre-flight check shell script

> **目标读者**: Codex app (GPT-5.5 实施者)
> **生成者**: Claude Code (架构师)
> **生成时间**: 2026-06-19 (示例)
> **Sprint 类型**: bash 实施 + lint 防御

---

## TL;DR

| 项 | 值 |
|---|---|
| **任务** | 写一个 pre-flight check shell script, 在 CI 跑批前自动 check disk / tool / env / data |
| **修改文件** | `.github/workflows/lint.yml` (jobs 头部加 pre-flight 步骤) |
| **新增文件** | `.github/actions/ci-preflight/action.yml` (composite action) |
| **预期工作量** | 半天 |

---

## 1. 任务背景

Sprint 41 e2e CI 0→1 实战 fix 闭环失败改 advisory (Sprint 41.12) 后, 实战教训沉淀. Sprint 42 #S42-1 spec-lint 预防层 + 3 层防御框架. Sprint 43 #S43-1 + #S43-2 spec-lint 改 blocking. 现在 Sprint 50+ #S43-3 加 pre-flight check shell script (跟 spec-lint 配合), 在 CI 跑批前自动 check 4 项:
1. **disk** — 磁盘空间够 (避免 Sprint 41.1 disk full fail)
2. **tool** — 必填工具装好 (避免 Sprint 41.2 npm ci peer dep fail)
3. **env** — 必填 env var 设了 (避免 Sprint 41.5 page.request 401 fail)
4. **data** — 必填数据文件存在 (避免 Sprint 41.4 uvicorn 启失败)

---

## 2. 架构意图

- **composite action 模式**: `.github/actions/ci-preflight/action.yml` 复用 (跟 .github/actions/setup-node 等 GH 官方 action 模式一致)
- **不引入**新 pattern, 跟 Sprint 41.11 `set -e` + redirect log 兼容
- **不引入**新 abstract, 简单 4 项 check

---

## 3. 实施步骤

### 3.1 新增 `.github/actions/ci-preflight/action.yml`

```yaml
name: 'CI Pre-flight Check'
description: 'Pre-flight check: disk / tool / env / data'
runs:
  using: composite
  steps:
    - shell: bash
      run: |
        set -e
        echo "=== Pre-flight Check ==="
        # 1. disk
        df -h / | awk 'NR==2 {print $4}' | grep -E '[0-9]+G' || {
          echo "❌ Disk space check failed"; exit 1;
        }
        # 2. tool
        command -v python3 node npm || {
          echo "❌ Tool missing"; exit 1;
        }
        # 3. env
        [ -n "$FQ_CRM_PASSWORDS" ] || { echo "❌ env missing"; exit 1; }
        # 4. data
        [ -f "$DUCKDB_PATH" ] || { echo "⚠️  DuckDB not found, skip data tests"; }
        echo "✅ Pre-flight check passed"
```

### 3.2 改 `.github/workflows/lint.yml`

在每个 job 头部加:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./ .github/actions/ci-preflight  # 新增 pre-flight
      - uses: astral-sh/ruff-action@v3
```

---

## 4. 验收标准

- [ ] `bash .github/actions/ci-preflight/action.yml` 在本地 dev 环境跑 ✅ pass
- [ ] `gh workflow run lint.yml` 触发 CI, pre-flight step ✅ pass
- [ ] 故意 `unset FQ_CRM_PASSWORDS` 跑 pre-flight, 期望 exit 1 + ❌ env missing
- [ ] pytest / spec-lint / e2e 没破

---

## 5. 跨 sprint 实战教训

[同上 5.1-5.3]

特别: Sprint 41.11 set -e + redirect log (本脚本必须用 set -e, 别用 || true 吞错)

---

## 6. 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| composite action 引用路径错 | 引用 `./ .github/actions/ci-preflight` 跟 GH 官方一致 |
| env var 在 GH context 未设 | step 默认 env 设为 GH context 变量 |
| disk check grep 失败 (容器 disk 格式差异) | 多行 fallback |

---

## 7. 不在 scope

- ❌ 不改 lint.yml 已有 jobs (只加 pre-flight step)
- ❌ 不改 spec-lint / ground-truth-lint (跟 pre-flight 独立)

---

## 8. 实施完成后, 你的下一步

1. 跟 user 说: "Codex 完成, 切回 Claude"
2. Claude Stage 3 review + Stage 4 commit + push
3. user 看 push 结果确认
```

---

## 你 (总指挥) 怎么用这个模板

下次做 sprint 时:

```
你: "做 Sprint XX, 主要做 YYY"
   ↓
Claude (Stage 1):
   - 读 sprint plan + memory + 相关 L4-L5 规则
   - 输出 HANDOFF-TO-CODEX-Sprint-XX.md (用本模板填实际内容)
   ↓
你: 复制 HANDOFF 内容给 Codex app (动作 1)
   ↓
Codex (Stage 2): 本地编辑代码
   ↓
你: "Codex 完成, 切回 Claude" (动作 2)
   ↓
Claude (Stage 3+4): review + commit + push
   ↓
你: 看 push 结果确认 (动作 3)
```

---

**HANDOFF-TO-CODEX.md 完。**
**新工作流就绪: Claude Stage 1 输出本模板填好的 HANDOFF, Codex Stage 2 实施, Claude Stage 3+4 review + push。**
