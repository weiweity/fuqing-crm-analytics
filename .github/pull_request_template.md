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
