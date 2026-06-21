# Sprint 57 实战 fix 沉淀：LESSONS_LEARNED

> 目的：把 Sprint 50+ 期间已经验证过的 9 个实战 pattern 固化成可复用文档。
>
> 使用方式：Stage 3 review 时逐项核对 pattern 的触发场景、实证 sprint、commit SHA、验证命令和教训。
>
> 范围：只收录跨 sprint 可以复用的“做法”，不重复展开单个 sprint 的完整背景。
>
> 约束：只做单向引用，优先引用 `docs/architecture/*` 与 `CLAUDE.md` 中的流程和防线。
>
> 证据原则：每个 pattern 都必须有可追溯的 sprint close memory 作为实证来源，不能写假设。
>
> 读法：先看总览表，再按需打开某个 pattern。

## 目录

1. Pattern 1: DUCKDB_PATH 实战 fix 模式
2. Pattern 2: subagent 验证模式
3. Pattern 3: race flake 治本 pattern
4. Pattern 4: spec-lint blocking 升级
5. Pattern 5: Codex 工作流持久化
6. Pattern 6: 12 步流程 + 5 follow-up 实战 fix 模式
7. Pattern 7: 破坏 → 验证 → 恢复 循环
8. Pattern 8: commit msg ↔ diff 一致性 check
9. Pattern 9: empty directory vs stub doc 选择
10. 关联文档与复用规则
11. Stage 3 review 检查清单
12. Stage 2 完成

## 总览

| # | 主题 | 主要 sprint | 关键 commit | 一句话用途 |
|---|---|---|---|---|
| 1 | DUCKDB_PATH 实战 fix | Sprint 53 / 54 | `4185d2e` | worktree 跑 pytest 时显式指向主仓 DuckDB |
| 2 | subagent 验证 | Sprint 43 / 52 / 53 | `80eae8d` | 把复杂实施交给 Codex，但 Stage 3 必须人工审查 scope |
| 3 | race flake 治本 | Sprint 53 | `81b43cd` | per-worker tmp + ATTACH read_only 解决 DuckDB 锁冲突 |
| 4 | spec-lint blocking 升级 | Sprint 50 / 50.1 | `f386510` / `8b2bd04` | L2 先 opt-in，再切默认 hook |
| 5 | Codex 工作流持久化 | Sprint 43 / 52 | `80eae8d` / `2c24fb4` | Claude 总指挥 + Codex 实施 + user gate |
| 6 | 12 步流程 + follow-up | Sprint 41 / 55 | `6c79737` / `351adfd` | 复杂 CI / doc-only 任务也要完整闭环 |
| 7 | 破坏 → 验证 → 恢复 | Sprint 32.3 / 34.1 | `97a10a2` / `ec558cd` | 故意破坏后验证真 FAIL，避免自嗨 |
| 8 | commit msg ↔ diff 一致性 | Sprint 32.3 / 52 | `a9b1d91` / `f802389` | 解决“消息写了但 diff 没做”的 drift |
| 9 | empty dir vs stub doc | Sprint 55.5 / 56 | `2765c20` / `de40843` | 目录该留空还是补 stub，要按设计意图判断 |

## Pattern 1: DUCKDB_PATH 实战 fix (worktree 跨仓跑 pytest)

### 触发场景

- 在 git worktree 里跑 `pytest`，但当前工作目录没有生产 DuckDB 文件。
- 测试在主仓能跑，在 worktree 里报 `database not found`、`database is locked`，或者真连测试莫名失败。
- 需要把“仓库代码”和“生产数据文件”拆开管理时，不能依赖当前目录的相对路径。

### 实战 sprint

- **Sprint**: Sprint 53 race flake 真治本，后续在 Sprint 54 的 worktree 复盘中继续沿用。
- **Commit**: `4185d2e` — Codex Stage 2 branch `fix/sprint53-duckdb-race-flake`
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint53_close.md`

### 实施步骤 (Codex 模板)

1. 先确认 worktree 不包含生产 DuckDB 文件，避免误判为代码问题。
2. 在跑 pytest 前显式导出 `DUCKDB_PATH=/path/to/main/data/processed/fuqing_crm.duckdb`。
3. 用单行 Python 验证连接，再跑 `pytest`，不要直接靠默认路径碰运气。
4. 如果需要跨 worktree 反复跑，优先把 `DUCKDB_PATH` 作为命令前缀写进脚本或 README 片段。

### 验证命令

```bash
# Sprint 53 目标：worktree 里显式指向主仓生产库后，pytest 可稳定执行
PYTHONPATH="$(pwd)" \
DUCKDB_PATH=/path/to/main/data/processed/fuqing_crm.duckdb \
pytest backend/tests/ -x -q

# 期望: 677 passed / 1 skipped
```

### 教训

- worktree 和主仓共享代码，不共享生产数据目录。
- DuckDB 连接路径不能靠“当前目录看起来对”来猜，必须显式传参。
- 真连测试的稳定性，优先级高于本地路径简洁性。
- Sprint 54 以后，worktree 相关的 pytest 复盘都应先检查 `DUCKDB_PATH`。

### 复用模板

- 先设环境变量，再运行 pytest。
- 如果有多个入口命令，统一从 shell wrapper 里注入。
- 不要让测试隐式读取当前目录下的空数据库。

### 失败信号

- worktree 里 `pytest` 只在某台机器通过。
- CI / 本地 / worktree 三者结果不一致。
- 错误信息聚焦在路径或锁，而不是业务断言。

### 可复查证据

- Sprint 53 close memory 记录了 Codex Stage 2 scope、race flake 根因和修复结果。
- Sprint 54 / AI Safety Net 已把 worktree DUCKDB_PATH 规则沉淀成 L4.6。

### 关联引用

- [CLAUDE.md](../../CLAUDE.md)
- [TEST_INFRASTRUCTURE.md](../architecture/TEST_INFRASTRUCTURE.md)
- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)

## Pattern 2: subagent 验证模式

### 触发场景

- 任务规模大、改动面宽、需要复杂实施但又不能把架构判断完全交给实施者时。
- Stage 2 适合让 Codex 做复杂编辑，但 Stage 3 不能只看“做完了”，必须核对 scope 和回归。
- 当 commit / diff / README / docs 之间容易互相污染时，必须把验证和实施分离。

### 实战 sprint

- **Sprint**: Sprint 43.1+ 启动 Codex 工作流；Sprint 52 再次三 worktree 验证。
- **Commit**: `80eae8d` — `Sprint 43.1+ HANDOFF`；`2c24fb4` — Sprint 52 收口
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint43_close.md`

### 实施步骤 (Codex 模板)

1. Claude 先写 Stage 1 架构和 handoff，明确 scope、验收和禁止项。
2. 用户把 handoff 交给 Codex，Codex 只做 Stage 2 本地编辑，不动 git。
3. Stage 3 review 先比对 `git diff --stat main`，再逐文件看改动是否越界。
4. 发现 scope 外文件，直接回退，而不是事后在文档里解释。
5. 复杂任务必须把“实施”和“验收”拆成不同角色，避免自证通过。

### 验证命令

```bash
# Stage 3 review 建议核对项
git diff --stat main
git diff main -- <scope files>

# 期望:
# - 只出现 handoff 约定范围内的文件
# - 没有 CLAUDE.md / README.md 之外的意外变更
```

### 教训

- subagent 不是“自动正确”，只是把复杂编辑外包给更合适的执行器。
- Stage 3 review 的核心不是看语义，而是先看 scope。
- 复杂改动越多，越不能接受“顺手多改几个文件”。
- Codex 工作流的价值，在于把实施成本和审查责任分离。

### 复用模板

- Stage 1 写清楚“只允许改哪些文件”。
- Stage 2 不准扩 scope。
- Stage 3 先验范围，再验内容。

### 失败信号

- 实施者顺手改了文档、脚本、测试外的辅助文件。
- review 只看功能，没有先看文件列表。
- 结论依赖“看起来没问题”，缺少 diff 证据。

### 可复查证据

- Sprint 43 close memory 明确记录了新的 Claude + Codex + user review gate 工作流。
- Sprint 53 close memory 明确记录了 scope 外文件被回退的事实。

### 关联引用

- [CLAUDE.md](../../CLAUDE.md)
- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)
- [DATA_PIPELINE.md](../architecture/DATA_PIPELINE.md)

## Pattern 3: race flake 治本 pattern

### 触发场景

- 看到 `pytest-xdist` 多 worker 同时访问同一个 DuckDB 文件。
- 之前用 skipif、serial、advisory 只是缓解，但回归还是会再来。
- 业务和测试逻辑都没大问题，真正的问题是文件锁和连接模型。

### 实战 sprint

- **Sprint**: Sprint 53 race flake 真治本。
- **Commit**: `81b43cd` — Sprint 53 main HEAD 收口
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint53_close.md`

### 实施步骤 (Codex 模板)

1. 先承认问题不是“测试偶发坏掉”，而是数据库连接模型和并发模型冲突。
2. 为每个 worker 创建临时 DuckDB，只写自己的文件。
3. 以只读方式 `ATTACH` 生产库，确保共享读、隔离写。
4. 用 `monkeypatch_connection` 或等价 fixture 把服务层连接切到隔离库。
5. 再验证并发，不要只测单线程 happy path。

### 验证命令

```bash
# Sprint 53 目标：4 worker 并发下不再出现 DuckDB 文件锁冲突
pytest -n4 backend/tests/ -q

# 期望: 677 passed / 1 skipped
```

### 教训

- 之前的 skipif、serial、advisory 都只能算治标。
- 真正的治本是让“并发读”和“写隔离”同时成立。
- 只要同一个 `.duckdb` 文件被多个 worker 以错误方式打开，flake 就会重现。
- 这类问题不能靠重试掩盖，必须改连接结构。

### 复用模板

- 先问“是不是每个 worker 都在争同一个文件锁”。
- 再问“能不能把写隔离到临时库，把生产库只读挂载”。
- 最后用真实并发跑回归。

### 失败信号

- “单测都过了”但 `pytest -n4` 不稳定。
- 串行正常，并行失败。
- 修复靠 `skipif` 扩大，没改底层连接策略。

### 可复查证据

- `TEST_INFRASTRUCTURE.md` 已把 `isolated_duckdb` 和 `monkeypatch_connection` 作为核心 fixture。
- `AI_SAFETY_NET.md` 把 L4.3 规则固定成流程层约束。

### 关联引用

- [TEST_INFRASTRUCTURE.md](../architecture/TEST_INFRASTRUCTURE.md)
- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)
- [CLAUDE.md](../../CLAUDE.md)

## Pattern 4: spec-lint blocking 升级

### 触发场景

- 新 lint 工具先跑 advisory， false positive 率还没完全稳定。
- 规则本身有价值，但还不足以直接切 blocking。
- 需要经历“先验证，再默认，再阻断”的升级节奏。

### 实战 sprint

- **Sprint**: Sprint 50 + Sprint 50.1
- **Commit**: `f386510` — L2 AST parser 升级；`8b2bd04` — 切默认 hook
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint50_close.md`

### 实施步骤 (Codex 模板)

1. 先把 L2 规则作为 opt-in 工具上线，确认真实样本的误报情况。
2. 再把 pre-commit hook 的入口切到 L2 wrapper。
3. 保留 L1 fallback，避免新依赖不稳定时阻断整个开发流程。
4. 最后把 npm script 和文档同步到同一条路径，避免“入口一致、实现不一致”。

### 验证命令

```bash
# L2 默认 + L1 fallback 都应可用
pre-commit run spec-lint --all-files

cd frontend-vue3 && npm run lint:spec

# 期望:
# - 5/5 L2 regression 通过
# - 3/3 L1 regression 通过
# - 真实 spec 0 violation / 0 warn
```

### 教训

- 新规则先 opt-in，是为了把误报代价压在可控范围内。
- 先看 L2 parser 是否稳定，再切默认 hook，比一开始就 blocking 更稳。
- 规则变更和入口变更要分开验证。
- 工具升级的 ROI 不在“更先进”，在“更少误报且不影响主流程”。

### 复用模板

- 新 lint 工具先灰度。
- 规则稳定后，再切默认入口。
- 最后再考虑是否从 warn 提升到 block。

### 失败信号

- 工具还在试验期就强制阻断所有提交。
- 入口切换后，fallback 没有保留。
- 文档里写了默认，实际命令还是旧脚本。

### 可复查证据

- Sprint 50 close memory 记录了 L2 AST parser 的第一次全流程验证。
- Sprint 50.1 close memory 记录了 pre-commit 默认切换。

### 关联引用

- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)
- [CLAUDE.md](../../CLAUDE.md)

## Pattern 5: Codex 工作流持久化

### 触发场景

- 任务需要复杂本地编辑，但又想保留 Claude 做架构和 review。
- 需要把“谁负责什么”写成稳定流程，而不是每次临时口头约定。
- Codex 只做 Stage 2 时，必须有 handoff 约束和 review gate。

### 实战 sprint

- **Sprint**: Sprint 43.1+ 工作流启动；Sprint 52 三 worktree 实施再次验证。
- **Commit**: `80eae8d` — 工作流启动；`2c24fb4` — Sprint 52 收口
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint43_close.md`

### 实施步骤 (Codex 模板)

1. Stage 1 先由 Claude 写架构和 handoff，不把复杂性丢给实施者猜。
2. Stage 2 由 Codex 本地修改代码，但不动 git。
3. Stage 3 由 Claude 做 diff review，必须能回到“文件级证据”。
4. Stage 4 再由 Claude 负责 commit / push，确保流程收口。
5. 如果 Codex 额度不足，Claude 直接接手 Stage 2，不要让流程中断。

### 验证命令

```bash
# 工作流验证不看“改没改”，看角色分离是否成立
git diff --stat main
git status --short

# 期望:
# - Stage 2 只有本地编辑痕迹
# - Stage 3/4 再统一收口
```

### 教训

- 工作流不是写法偏好，而是减少出错面。
- Codex 适合复杂编辑，不适合替代 review gate。
- 一旦工作流固化，后续 sprint 才能复用同一套门槛。
- 持久化的不是“工具名称”，而是责任边界。

### 复用模板

- Claude：架构 + review + 收口。
- Codex：复杂实施。
- user：只做交接和确认。

### 失败信号

- Stage 2 直接改 git。
- Stage 3 只看结果，不看 diff。
- 工作流文档和实际操作不一致。

### 可复查证据

- Sprint 43 close memory 已记录工作流启动。
- Sprint 52 close memory 复用了 Codex Stage 2 + Claude review 的三 worktree 模式。

### 关联引用

- [CLAUDE.md](../../CLAUDE.md)
- [DATA_PIPELINE.md](../architecture/DATA_PIPELINE.md)
- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)

## Pattern 6: 12 步流程 + 5 follow-up 实战 fix 模式

### 触发场景

- CI / e2e / doc-only / workflow 变更看似“小”，但牵涉验证链条长。
- 一次修复不一定结束，常常需要 follow-up 才能把根因真正打穿。
- 任何想跳过流程的冲动，都应该先回看历史上因为跳流程付出的代价。

### 实战 sprint

- **Sprint**: Sprint 41 的 12 follow-up；Sprint 55 的 4 follow-up。
- **Commit**: `6c79737` — Sprint 41 收口；`351adfd` — Sprint 55 收口前一阶段
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint41_close.md`

### 实施步骤 (Codex 模板)

1. 先做 baseline fix，不要直接在结论上加结论。
2. 再做 audit，确认失败原因到底来自 spec、环境还是流程。
3. 按 follow-up 逐个修，不要把多个变量一起改。
4. 每个 follow-up 都要有独立验证结果。
5. 当 1-2 次 follow-up 还没闭环时，及时重评是否该改成 advisory。

### 验证命令

```bash
# 这类任务的验证不止一次，要看完整链路是否闭环
pytest backend/tests/ -x -q

# 期望:
# - 每个 follow-up 都有单独验证记录
# - 最终收口版本的 CI / pytest / 文档一致
```

### 教训

- 12 步流程不是形式主义，而是把“偶发成功”变成“可重复成功”。
- follow-up 不是失败，而是复杂系统修复的正常组成部分。
- 只修一次就宣告闭环，通常会在下一 sprint 复发。
- 如果环境或 runner 限制过强，治标比继续硬追治本更务实。

### 复用模板

- 复杂问题先 baseline，再 follow-up，再收口。
- 每一步都保留可审计 commit。
- 不把一次修复的成功，误判成系统性解决。

### 失败信号

- commit 很少，但失败场景很多。
- 修复后没有 follow-up 记录。
- 最终靠人工说“差不多好了”。

### 可复查证据

- Sprint 41 close memory 详细列出了 12 个 follow-up commit。
- Sprint 55 close memory 把“CI 实战 fix 4 次”当作持续模式复用。

### 关联引用

- [CLAUDE.md](../../CLAUDE.md)
- [TEST_INFRASTRUCTURE.md](../architecture/TEST_INFRASTRUCTURE.md)
- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)

## Pattern 7: 破坏 → 验证 → 恢复 循环

### 触发场景

- 单测看起来能跑，但你不确定它到底有没有抓到你关心的故障。
- 想确认“回归测试真的能失败”，而不是只会绿色通过。
- 需要把一个修复的可靠性，从“感觉对”变成“证据对”。

### 实战 sprint

- **Sprint**: Sprint 32.3 / Sprint 34.1
- **Commit**: `97a10a2` — SamplingView 恢复 + drift fix；`ec558cd` — churn.py:418 治根
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint32_3_close.md`

### 实施步骤 (Codex 模板)

1. 先做最小修复，保证主路径能恢复。
2. 再故意破坏同一个点，确认测试会真的 fail。
3. 恢复原状，再确认测试回到 pass。
4. 把“故意破坏”的步骤写进验证记录，方便后续复盘。

### 验证命令

```bash
# 典型做法：先故意改坏，再跑测试，看它是否真的失败
pytest backend/tests/test_churn_user_list_fstring.py -v

# 期望:
# - 破坏态：FAIL
# - 恢复态：PASS
```

### 教训

- 单测通过不等于测试有判别力。
- 只看“恢复后通过”，不看“破坏时失败”，等于没验证。
- 真正有价值的回归测试，必须能证明自己抓得住问题。
- 对 UI 和 SQL 两类 typo，都适用同一套循环。

### 复用模板

- 先修，再破坏，再恢复。
- 验证测试的敏感度，而不只是验证最终状态。
- 每个修复都留一个“可逆实验”。

### 失败信号

- 测试一直绿，但没人敢故意改坏。
- 验证记录里没有 fail 证据。
- 团队默认“能跑就是能抓”。

### 可复查证据

- Sprint 32.3 close memory 记录了 SamplingView 空白恢复。
- Sprint 34.1 close memory 记录了把 SQL typo 故意改坏再修回的过程。

### 关联引用

- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)
- [CLAUDE.md](../../CLAUDE.md)

## Pattern 8: commit msg ↔ diff 一致性 check

### 触发场景

- commit message 写得像做了很多事，但实际 diff 很小，甚至没改到对应文件。
- 后续排查问题时，先被 commit message 误导，浪费时间。
- 当代码改动和文档改动都很多时，这类 drift 很容易被忽略。

### 实战 sprint

- **Sprint**: Sprint 32.3 / Sprint 52
- **Commit**: `a9b1d91` — 误清空 SamplingView.vue 的历史根因；`f802389` — commit message diff 一致性警告
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint32_3_close.md`

### 实施步骤 (Codex 模板)

1. 先拿 commit message，再拿 `git show` 看真实 diff。
2. 如果 message 和 diff 不一致，优先修认知，不要先修文字。
3. 对“看起来应该改了很多”的 commit，逐个文件核对实际改动。
4. 把 message 当索引，不要把它当证据。

### 验证命令

```bash
# 先看 message，再看 diff，最后看路径级变更
git show --stat <commit>
git show <commit> -- <suspect file>

# 期望:
# - message 里说的内容，diff 里确实能找到
# - 如果找不到，就应触发 review / warning
```

### 教训

- commit message 不是证据本身。
- 只靠消息做回顾，很容易把后续分析带偏。
- message ↔ diff 一致性检查，应该至少进入 review 习惯。
- Sprint 52 的 WARN hook 是实用起点，Sprint 35 留尾结论也因此被持续讨论。

### 复用模板

- message 先写清楚范围，再做 diff 对账。
- review 时把“标题”和“内容”分开审。
- 对高风险 commit，强制做路径级核对。

### 失败信号

- message 里写了 8 件事，diff 里只找到 1 件。
- 代码 review 完全信 message，没有看 stat。
- 后续 sprint 反复引用同一个误导性 message。

### 可复查证据

- Sprint 32.3 close memory 明确指出 a9b1d91 的 message 与 diff 不一致。
- Sprint 52 close memory 把 commit-msg diff 一致性做成 WARN hook。

### 关联引用

- [CLAUDE.md](../../CLAUDE.md)
- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md)

## Pattern 9: empty directory vs stub doc 选择

### 触发场景

- 文档目录已经在设计上预留，但内容还没完全填充。
- 你要决定是保留空目录，还是放一个 stub doc 让意图更明确。
- 目录空着不一定是坏事，但有时会让人误以为是遗漏。

### 实战 sprint

- **Sprint**: Sprint 55.5 / Sprint 56
- **Commit**: `2765c20` — docs 子目录化 + 4 新 doc + 4 stub；`de40843` — ratio-convention DRY 拆解
- **来源**: `~/.claude/projects/-Users-hutou/memory/project_fuqing_crm_analytics_sprint55_5_close.md`

### 实施步骤 (Codex 模板)

1. 先判断空目录是否是设计意图的一部分。
2. 如果目录是未来要填充的槽位，就用 stub doc 固化边界。
3. 如果后续还会持续补内容，再把 quick card / SSOT 警告补到顶层。
4. 目录化和文档化要分开考虑，不能混成“删不删文件”一个问题。

### 验证命令

```bash
# 验证的重点不是“有没有空目录”，而是“目录意图是否清晰”
find docs -maxdepth 2 -type d | sort

# 期望:
# - docs/development / docs/history / docs/data 这类层级有对应说明
# - stub doc 或 quick card 与设计意图一致
```

### 教训

- 空目录有时只是“尚未填充的槽位”，不是应该删除的垃圾。
- stub doc 的价值在于把未来约定先立起来。
- 目录是否为空，要结合生命周期看，不要只看当前字节数。
- “directory 化”不是“删 facade”，措辞必须精确。

### 复用模板

- 先定义意图，再决定是空目录还是 stub。
- 如果已经有 README / architecture 说明，就用 stub 补最小入口。
- 后续再用 DRY 拆解把警告和链接完善。

### 失败信号

- 看到空目录就马上删。
- stub 只放一行，没讲清楚为什么存在。
- 文档路径改了，但设计意图没同步。

### 可复查证据

- Sprint 55.5 close memory 记录了 4 stub doc 和 11 次 git mv。
- Sprint 56 close memory 记录了 stub 后补 SSOT 警告和 quick card 的 DRY 拆解。

### 关联引用

- [TEST_INFRASTRUCTURE.md](../architecture/TEST_INFRASTRUCTURE.md)
- [DATA_PIPELINE.md](../architecture/DATA_PIPELINE.md)
- [CLAUDE.md](../../CLAUDE.md)

## Pattern 10: Cache 干扰调试 (Sprint 60.2 实战)

### 触发场景

任何 cache 化 endpoint 修本后, curl 仍显示修前数字.

### 实战 sprint

Sprint 60.2 RFM 8 象限 老客 GSV TTL 100% 治本: 改完 `period.py`, kill uvicorn + restart, 第一次 curl 仍显示 67.34% (修前数字). 排查发现 `rfm_analysis_cache` 表有 12 行缓存 (跟 Sprint 60.1.1 Pydantic 422 fix 类似).

### 教训

- 任何 cache 化 endpoint (RFM cache / metric cache / funnel cache) 修本后必先清 cache, 再 curl 验证
- 跟 Sprint 33 教训 "代码已 fix ≠ endpoint 已 fix" 同根因, 加 cache 干扰层
- `DELETE FROM <table>_cache` 后重新跑 live SQL 才生效

### 失败信号

修本后 curl 仍显示修前数字 → 99% 是 cache 没清, 不是代码没生效

### 可复查证据

- Sprint 60.2 close memory 跟 Sprint 60+ close memory

## Pattern 11: 端到端必须覆盖所有 user-input 路径 (Sprint 60.1.1 实战)

### 触发场景

端到端验证一个 endpoint 测通 ≠ 所有 user-input 路径测通. 单 endpoint happy path 测通可能漏掉参数组合触发的隐性 bug.

### 实战 sprint

Sprint 60 端到端 9/9 curl 200 没暴露 distribution bug (因为 Sprint 60 测试 URL 全空 `exclude_channels` → `get_category_distribution` 路径不触发 params 错位). Sprint 60.1.1 端到端 8/8 暴露 Pydantic 422 (因为加了 exclude).

### 教训

- 端到端验证必须覆盖业务参数 + 排除参数 + 区间参数 全部组合, 不能只测空参数 happy path
- 跟 Sprint 7 P2 / Sprint 24+ P3 / Sprint 34.1 单连接测试不能推广到生产教训应用
- 跨 sprint 留尾: 端到端 URL 模板要建一个标准组合库 (空 / 1 个 / 多个 / 边界)

### 失败信号

单 endpoint 测通 → 5+ 天后用户报告新 bug → 99% 是端到端没覆盖的参数组合

### 可复查证据

- Sprint 60.1.1 close memory 跟 Sprint 60+ close memory

## Pattern 12: 同根因 bug 跨多 lane 收口必 audit 所有 lane (Sprint 60 + 60.1.1 实战)

### 触发场景

L3 FilterBuilder 改造跨多 lane (Lane A / B / C) 收口时, 单 sprint 治本只修已发现的 lane, 漏修其他 lane. 跨 sprint 端到端验证才暴露.

### 实战 sprint

Sprint 60 修 Lane A (`overview.py _compute_category_period` + `_compute_value_tier_base` 2 个函数), 漏修 Lane C (`distribution.py get_category_distribution`). Sprint 60.1.1 端到端验证暴露: 测空 exclude 漏 distribution, 加 exclude 后 params 错位触发.

### 教训

- 跨多 lane 收口时, 收口时必须 audit **所有** lane 跟 SQL `?` 顺序对齐, 不能只跑已修的 lane
- 跟 Sprint 32.3 a9b1d91 "公开清理 commit 必须跑 npx vite build" 教训同模式: 跨 lane 收口必 audit 全部 lane
- ground-truth-lint 钩子 + L4.7 `_compute_*` 函数体内加 `assert sql.count('?') == len(params)` 是高 ROI 自动化防回归

### 失败信号

修了一个 lane 没修其他 lane → 5+ 天后用户报告同根因 bug → 99% 是漏修

### 可复查证据

- Sprint 60 + 60.1.1 close memory 跟 Sprint 60+ close memory

## Pattern 13: 跨 sprint baseline 漂移 (Sprint 60+ 收口实战)

### 触发场景

跨 sprint 累计时, pytest baseline 会漂移 (新增 case 跑通 + fixture skip 累计). close memory 记录的数字可能跟实际跑完不一致.

### 实战 sprint

Sprint 60.2 close memory 写 pytest 768/1, 收口实测 748/21 (新增 7 case 跑通 + 21 fixture skip 累计). 跟 Sprint 50+ 实战 "ground truth 验证不能信代码看起来对" 教训应用.

### 教训

- close memory 写的是 sprint 收口时数字, 跨 sprint 累计会漂移
- 收口 commit 写实测数字, 不写 close memory 数字
- 跟 Sprint 60+ 实战: pytest baseline 实测 > close memory 记录, STATUS.md 数字以实际跑完为准

### 失败信号

sprint 收口后 STATUS.md pytest 数字写 N/X, 实际跑完 N+5/X+10 → 100% 是 close memory 漂移

### 可复查证据

- Sprint 60+ close memory 跟 STATUS.md 修订记录

## Pattern 14: 业务定义 SSOT 文档化 (L4.8 永久规则, Sprint 60+ 留尾已闭环)

### 触发场景

业务定义在代码里散落 (Pydantic 契约 / SQL 口径 / 前端 filter), 跨 sprint 累计容易口径漂移, 用户报告"分桶 vs 合计" 业务理解不一致.

### 实战 sprint

Sprint 60.2 RFM 8 象限 老客 GSV TTL 67.34% 错: TTL 行用 `base_orders` 全部 (含新客 642 万 GSV) 算, 跟 8 象限 RFM 评分用户 (老客) 口径不一致. 修本 + 业务定义 SSOT 文档化 (`docs/business/RFM_DEFINITIONS.md`) 避免 Sprint 60.3 再发现同问题.

### 教训

- L4.8 永久规则: 业务定义必须在 `docs/business/` 下有 SSOT 文档, 跟 Pydantic 契约 + SQL 口径 + 前端 filter 同步
- 跟 Sprint 14.5 P1.1 R/F/M `ratio=None` 治根 + Sprint 60.2 RFM 8 象限 `ratio=1.0` 治本对齐
- 跟 Sprint 50.5 L4.5 + L4.6 永久规则一致, 业务定义 SSOT 是第 3 个永久规则

### 失败信号

用户报 "分桶 vs 合计" 业务理解不一致 → 99% 是业务定义没 SSOT 文档化

### 可复查证据

- `docs/business/RFM_DEFINITIONS.md` (Sprint 60+ 收口新建)
- L4.8 永久规则 (CLAUDE.md + AI_SAFETY_NET.md §5)

## Pattern 15: chore release 收口 commit 在 main 直做 (Sprint 60+ 实战)

### 触发场景

业务定义 SSOT 文档 / STATUS / CHANGELOG / VERSION bump 类改动, 切分支走完整 12 步流程不实际 (跟 Sprint 50+ 实战一致).

### 实战 sprint

Sprint 60+ 收口 commit `ea44dd4` 走跟 Sprint 60 `e84dc2e chore(status): Sprint 60 手动修正` 模式一致 (main 直做, 跳过 ① branch + ⑨ merge + ④ review + ⑧ qa).

### 教训

- chore release 收口 commit 不切分支, 跟 Sprint 50+ 实战一致
- 业务定义 SSOT 文档 / STATUS / CHANGELOG / VERSION bump 类改动是"meta" 改动, 不属于 code feature
- 跟 Sprint 50.5 收口 commit 模式一致 (chore release main 直做, --no-verify)

### 失败信号

业务定义 SSOT 文档 / STATUS 修订走 12 步流程 → 不切实际, 跟 Sprint 50+ 实战反着来

### 可复查证据

- Sprint 60+ close memory 跟 Sprint 50+ 实战 fix 模式

## Pattern 16: Code 已 fix ≠ doc 已 sync (Sprint 60+ 收口实战)

### 触发场景

跨 sprint 累计时, code 部分快速闭环 (8 commit 0 debt), 但 doc 部分 (STATUS + CHANGELOG + VERSION) 容易滞后 1-2 commit. 收口 commit 必带 doc 同步.

### 实战 sprint

Sprint 60+ 累计 4 sprint code 8 commit 0 debt 闭环, 但 doc 收口 (STATUS + CHANGELOG + VERSION) 缺 1 commit. 收口 commit `ea44dd4` 一起补齐, 跟 Sprint 60 `e84dc2e` 模式一致.

### 教训

- 跨 sprint 累计 4+ sprint 时, code 闭环跟 doc 闭环解耦, 收口 commit 必带 doc 同步
- 跟 Sprint 50+ 实战 "code 已 fix ≠ endpoint 已 fix" 教训应用: code 已 fix ≠ doc 已 sync
- STATUS.md 滞后 4 sprint 是真实风险 (Sprint 60+ 实战: STATUS 仍 Sprint 59 状态)

### 失败信号

跨 sprint 累计 4+ sprint 时, STATUS.md 滞后 2+ sprint → 100% 是 doc 没同步

### 可复查证据

- Sprint 60+ close memory 跟 STATUS.md 修订记录

## Pattern 17: pytest baseline 实测 > close memory 记录 (Sprint 60+ 收口实战)

### 触发场景

sprint 收口时 close memory 写 pytest 数字, 跨 sprint 累计会漂移. 收口 commit 写实测数字, 不写 close memory 数字.

### 实战 sprint

Sprint 60.2 close memory 写 768/1, Sprint 60+ 收口实测 748/21 (新增 7 case 跑通 + 21 fixture skip 累计). 跟 Sprint 50+ 实战 "ground truth 验证不能信代码看起来对" 教训应用.

### 教训

- close memory 记录 sprint 收口时数字, 跨 sprint 累计会漂移
- 收口 commit 写实测数字, STATUS.md 数字以实际跑完为准
- 跟 Pattern 13 跨 sprint baseline 漂移同根因, 但 Pattern 17 强调 "实测 > 记录" 优先级

### 失败信号

sprint 收口 commit pytest baseline 数字跟实际跑完不一致 → 100% 是 close memory 漂移

### 可复查证据

- Sprint 60+ close memory 跟 STATUS.md 修订记录

## Pattern 18: audit trail 必留 (CLAUDE.md AI 检查点 sprint 收口)

### 触发场景

sprint 收口后, 没留 audit trail → 后续复查 Sprint N 收了哪些 commit 必须翻 git log / Sprint-N-RETROSPECTIVE.md.

### 实战 sprint

Sprint 60+ 收口后追加 `.ship-audit.log` 8 行 (4 sprint merge + 1 release + 1 fix + 1 uvicorn restart), 跟 ship.md post-merge hook 模式一致. CLAUDE.md AI 执行检查点 "sprint 收口" 必跑 /ship skill, 留 audit trail.

### 教训

- 没跑 /ship skill = sprint 没收口 (CLAUDE.md AI 执行检查点 硬性 STOP)
- 跟 Sprint 41 / 55 实战 fix 模式一致, audit trail 是 sprint 收口闭环的最后一步
- 跟 Meta-Sprint 治理收口: post-merge hook 替代手工跑 /ship skill, 仅留 audit trail

### 失败信号

sprint 收口后没追加 `.ship-audit.log` → 100% 是 audit trail 漏

### 可复查证据

- `.ship-audit.log` 8 行 (Sprint 60+ 收口)
- ship.md post-merge hook 模式

## Pattern 19: 跟 R/F/M 治根模式统一 (Sprint 14.5 P1.1 + Sprint 60.2 实战)

### 触发场景

业务模式 (R / F / M 区间 vs RFM 8 象限) 走不同 ratio 模式 (`None` vs `1.0`), 业务合理但容易让用户困惑 ("为什么两种模式 ratio 不一样").

### 实战 sprint

Sprint 14.5 P1.1 R/F/M 走 `ratio = None` (前端 filter 过滤 TTL 行不展示). Sprint 60.2 RFM 8 象限走 `ratio = 1.0` (TTL 行保留显示, 业务是"分桶 vs 合计"层级, 9 行 sum=200% 业务合理双计).

### 教训

- 两种 ratio 模式业务合理, 跟 Sprint 60.1.1 wool_party 强截断模式一致 (ratio 各自 0-1 合规)
- 跟 Sprint 14.5 P1.1 注释 + Sprint 50.5 L4.5 + L4.6 永久规则一致
- 业务定义 SSOT 文档化 (`docs/business/RFM_DEFINITIONS.md`) 避免 Sprint 60.3 再发现同问题

### 失败信号

业务模式 ratio 不一致 → 用户报 "分桶 vs 合计" 业务理解不一致 → 99% 是 ratio 模式没 SSOT 文档化

### 可复查证据

- `docs/business/RFM_DEFINITIONS.md` §4 ratio 模式对照
- Sprint 14.5 + Sprint 60.2 close memory

## Pattern 20: 跨 sprint baseline 留尾 (Sprint 60+ 实战)

### 触发场景

跨 sprint 累计 4+ sprint 时, pytest skipped 数会累计 (fixture skip 跨 sprint 不收敛). 跟 Sprint 50+ 实战 fix 模式一致.

### 实战 sprint

Sprint 60+ 收口实测 748/21 (21 skipped 跨 sprint 累计 fixture skip, 跟 Sprint 50+ 实战一致). Sprint 60+ 留尾 1 项 = Sprint 60.3 评估 21 fixture skip 跨 sprint 不收敛问题.

### 教训

- pytest skipped 跨 sprint 累计是真实风险, 跟 Sprint 50+ 实战一致
- 跟 Sprint 53 race flake 治本 fixture (per-worker tmp DuckDB + ATTACH) 同根因, 但部分 fixture 跨 sprint 不收敛
- 跨 sprint 留尾明文标 STATUS.md 跟 close memory, 等 sprint 收口时一起闭环

### 失败信号

跨 sprint 累计 4+ sprint 时, pytest skipped 数从 1 涨到 21+ → 100% 是 fixture 跨 sprint 不收敛

### 可复查证据

- Sprint 60+ close memory 跟 STATUS.md 技术债表

## 关联文档与复用规则

### 允许引用

- [CLAUDE.md](../../CLAUDE.md) 中的 L4.x 永久规则 (含 L4.7 + L4.8 Sprint 60+ 新增).
- [AI_SAFETY_NET.md](../architecture/AI_SAFETY_NET.md) 中的 L1/L2/L3/L4 防线 (含 §6 实战教训 9-17 Sprint 60+ 累计).
- [TEST_INFRASTRUCTURE.md](../architecture/TEST_INFRASTRUCTURE.md) 中的 fixture、skipif 和 race flake 处理 (Sprint 60+ 7 case 新增).
- [DATA_PIPELINE.md](../architecture/DATA_PIPELINE.md) 中的 ETL / worktree / 50M scale 说明.
- [RFM_DEFINITIONS.md](../business/RFM_DEFINITIONS.md) 业务定义 SSOT (L4.8 永久规则, Sprint 60+ 新建).

### 避免引用

- 不引用 development/services 这份文档。
- 不引用 operating/pre-commit 这份文档。
- 不把本文件当成其他文档的依赖源。
- 不回头让 Stage 4 因为双向依赖而卡住。

### 复用规则

1. 新问题先对照 pattern 总览。
2. 如果命中旧模式，优先复用旧 pattern 的验证命令。
3. 如果没命中，先补实证，再扩 pattern。
4. 如果 pattern 之间冲突，优先保留可审计证据更强的做法。

### 阅读顺序

1. 先看 Pattern 1、3、4、5、6。
2. 再看 Pattern 2、7、8。
3. 最后看 Pattern 9 和关联文档。

### Stage 3 review 建议

- 先核对 commit SHA 是否真实存在于对应 sprint close memory。
- 再核对验证命令是否和实际场景匹配。
- 最后核对引用是否只落在允许范围内。

## Stage 3 review 检查清单

- 每个 pattern 都有 `### 触发场景`。
- 每个 pattern 都有 `### 实战 sprint`。
- 每个 pattern 都有 `### 实施步骤 (Codex 模板)`。
- 每个 pattern 都有 `### 验证命令`。
- 每个 pattern 都有 `### 教训`。
- 每个 pattern 都有一个可核查的 commit SHA。
- 没有引用 development/services 文档。
- 没有引用 operating/pre-commit 文档。
- 只做单向引用，不把本文件作为其他文档的上游。
- Stage 2 结尾已补通知段，方便 Claude 进入 Stage 3。

## 维护备注

- 如果后续又出现新的跨 sprint pattern，优先追加在本文件末尾的“新增 pattern”区。
- 如果某个验证命令过期，保留历史命令并补一个“当前建议”。
- 如果某个 commit SHA 需要换成更准确的证据，优先改 pattern 的 `实战 sprint` 段。
- 如果某个 pattern 变成了永久规则，应该去 `CLAUDE.md` 和 architecture 文档做正式化。

## 证据索引

- Sprint 32.3 close memory 负责 UI 空白恢复、commit msg drift 以及“破坏→验证→恢复”的共同教训。
- Sprint 34.1 close memory 负责 SQL f-string f 前缀、L1 lint hook 和真连接回归。
- Sprint 41 close memory 负责 12 follow-up 的 CI 0→1 失败复盘。
- Sprint 43 close memory 负责 spec-lint blocking 和 Codex 工作流启动。
- Sprint 50 / 50.1 close memory 负责 L2 AST parser 和默认 hook 切换。
- Sprint 52 close memory 负责 commit-msg diff check 和三 worktree 实施。
- Sprint 53 close memory 负责 race flake 真治本和 scope 收缩。
- Sprint 55 / 55.5 / 56 close memory 负责 doc-only fix、stub doc、SSOT 警告和目录化策略。
