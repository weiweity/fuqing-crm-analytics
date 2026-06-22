# PR Checklist

> 提交前请逐项打勾。**任何未完成的项必须说明原因**。

## 必跑（CI 强制）

- [ ] `pytest backend/tests/ -x -q` 全绿（CI 自动跑）
- [ ] `ruff check .` 无错误（CI 自动跑）
- [ ] 已确认在 feature 分支（非 main）

## 必跑（手工）

- [ ] `/review` skill 已跑、已处理高/中风险点
- [ ] 若涉及 schema/契约变更：`contracts/schemas.py` 和前端 `types.ts` 已同步
- [ ] 若涉及 ETL 口径变更：`backend/semantic/` 已更新

## Sprint 收口（merge 到 main 前必跑, 跟 12 步流程 §12 对齐）

- [ ] **12 步流程全跑完**（`docs/operating/ship.md` 第 1-12 步）：branch / code / pytest / review / fix / commit / push / qa / merge / push main / pull / STATUS+CHANGELOG+VERSION
- [ ] **跨文档一致性 check**（4 数字一致）：
  ```
  VERSION: $(cat VERSION)                  ← 实际写入
  CHANGELOG 顶部 entry: [vX.Y.Z]            ← 跟 VERSION 一致
  STATUS.md git HEAD (main): a1b2c3d        ← 跟 git rev-parse HEAD 一致
  CLAUDE.md 行 4 main @: a1b2c3d           ← 跟 STATUS.md 一致
  ```
- [ ] **`/document-release` audit 已跑**（跨 sprint 范围, 不只改本 PR 的 docs）：
  - `STATUS.md` / `CHANGELOG.md` / `docs/TECH-DEBT.md` / `docs/history/SPRINT_INDEX.md` 4 个文档 main HEAD 同步
  - `docs/README.md` 索引完整（新增文档必须加索引）
  - `README.md` 测试行 / ETL 日期 / CHANGELOG 版本引用 同步
- [ ] **`/ship` audit trail 已追**（如果手动 merge 直 main, 必追 `.ship-audit.log` 4-5 行）
- [ ] **`AGENTS.md` 跟 `CLAUDE.md` 同步**（CLAUDE.md 行 4 改完, 跑 `scripts/sync-agents.sh` 重生 AGENTS.md）

## 强烈推荐

- [ ] **已跑 `codegraph affected` 评估影响面**（在 PR 描述里贴结果）

  ```bash
  # 在项目根目录跑一次，把受影响的文件填到下面
  codegraph affected $(git diff --name-only origin/main...HEAD) --quiet
  ```

  受影响测试文件：
  ```
  （粘贴 codegraph affected --quiet 输出）
  ```

  爆炸半径评估：
  - [ ] 影响 ≤ 5 个文件
  - [ ] 影响 6-20 个文件（**说明原因**）
  - [ ] 影响 > 20 个文件（**必须**有充分理由 + reviewer 二次确认）

- [ ] 已用 `codegraph_impact` 查过核心改动的影响面（若 PR > 100 行）

## 描述

### 改了什么
（一两句话讲清）

### 怎么测的
（关键 case 或截图）

### 风险
（可能炸的地方 + 缓解措施）
