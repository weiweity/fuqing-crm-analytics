# HANDOFF-TO-CODEX-Sprint52.md

> Claude Stage 1 输出 → 交给 Codex Stage 2 实施。
> Codex 只读此 HANDOFF 和项目 `AGENTS.md`（自动注入），**不读 `CLAUDE.md`**。
> 实施完成后回 Claude Stage 3 review + Stage 4 commit/push。

---

## 1. 本次 Sprint 目标

执行 Sprint 52 backlog 中的 **3 项任务**（按优先级排序）：

1. **#1 激活 visitor 路由** — user 已拍板选 A：在 `frontend-vue3/src/router/index.ts` 注册 `/visitor`。
2. **#4 50m scale 测试** — 阶梯验证：1m → 5m → 10m → 50m，生成 synthetic orders 并跑端到端 ETL，输出 scale report。
3. **#5b commit message ↔ diff 一致性 git hook** — 第 1 版 WARN 模式，不 BLOCK。

**当前版本基线**: v0.4.14.137, main HEAD `4f814b1`。

---

## 2. 任务 #1：激活 visitor 路由（user 已选 A）

### 2.1 背景

Sprint 39 已完成 visitor / export / report 三链路的 ground-truth audit：
- backend API 100% 活跃
- frontend API 调用 100% 活跃
- `AudienceView.vue` 在 audience 路由中被真消费
- **唯一缺口**: visitor 路由未在 `frontend-vue3/src/router/index.ts` 注册

### 2.2 实现步骤

1. 读 `frontend-vue3/src/router/index.ts`，确认现有路由注册模式。
2. 确认 `frontend-vue3/src/views/AudienceView.vue` 是否可直接复用为 visitor 页面，还是需要新建 `VisitorView.vue`。
   - 如果 `AudienceView.vue` 标题/内容就是"访客"相关，直接复用。
   - 如果 audience 和 visitor 业务口径不同，新建 `frontend-vue3/src/views/VisitorView.vue`，可从 AudienceView copy 后微调。
3. 新增 `/visitor` 路由：
   ```typescript
   {
     path: '/visitor',
     name: 'Visitor',
     component: () => import('@/views/AudienceView.vue'),
     meta: { title: '访客看板', requiresAuth: true }
   }
   ```
4. 在主导航（`frontend-vue3/src/layouts/MainLayout.vue` 或侧边栏组件）增加 `/visitor` 入口，保持与现有菜单风格一致。
5. 新增 e2e smoke test：`frontend-vue3/e2e/visitor.spec.ts`，复用 `auth.fixture.ts`。
6. 跑 `cd frontend-vue3 && npx vite build` + `npx playwright test e2e/visitor.spec.ts`。

### 2.3 验收标准

- `/visitor` 路由在本地可访问
- 主导航可见"访客看板"入口
- Vite build 0 错误
- e2e smoke test 通过
- 无 console error

---

## 3. 任务 #4：50m scale 测试

### 3.1 目标

验证 fuqing-crm-analytics 在 **5000 万订单** 量级下的 ETL 跑批表现，识别时间/磁盘/内存瓶颈。

### 3.2 实现步骤

1. **创建 synthetic data 生成脚本**
   - 新文件：`scripts/etl/benchmarks/generate_synthetic_orders.py`
   - 参数：`--n_orders`（默认 50_000_000）、`--output_dir`
   - 输出 parquet/csv 文件，字段与 production orders 一致（order_id, pay_time, actual_amount, is_member, channel, etc.）

2. **阶梯验证**
   - 1m → 5m → 10m → 50m
   - 每个量级跑 `scripts/run_etl.py --update` 或等效 ETL 入口
   - 记录：总耗时、W1-W7 各阶段耗时、peak 磁盘、peak 内存、DuckDB 最终大小

3. **输出报告**
   - 新文件：`scripts/etl/benchmarks/scale_report_50m.md`
   - 包含 before/after 指标表和瓶颈分析

4. **回归保护**
   - 新增一个 fast smoke test：`backend/tests/test_scale_smoke.py`
   - 只跑 10k orders，验证 scale 脚本本身不挂

### 3.3 关键约束

- **不要污染 production DuckDB**。scale 测试必须指向独立 benchmark DuckDB 路径（可用 env var `FQ_BENCHMARK_DUCKDB` 覆盖）。
- **不要占用 /tmp 过大**。Sprint 6 P0-3 6 层防护会清理 1GB+/1h+ 的 `/private/tmp/fuqing_*.duckdb`，benchmark 产生的大文件要放 `data/benchmarks/` 或主动清理。
- **跑 50m 前先让我确认**。10m 以内可先跑，50m 量级需确认磁盘空间（当前可用空间需 >200GB）。

### 3.4 验收标准

- `python3 scripts/etl/benchmarks/generate_synthetic_orders.py --n_orders 10000` 10 秒内完成
- `python3 scripts/etl/benchmarks/run_scale_benchmark.py --n_orders 1000000` 可跑通并输出 report
- report 中包含可复现的命令和指标表

---

## 4. 任务 #5b：commit message ↔ diff 一致性 git hook

### 4.1 背景与目标

防止 Sprint 32.3 a9b1d91 类事故：commit message 说“清理业务专名”，实际 diff 误清空整个 `.vue` 文件。新增 hook 检查 commit message 中提到的文件/操作是否与实际 diff 大致匹配。

### 4.2 实现步骤

1. **新建检查脚本**
   - `scripts/git/check_commit_msg_diff_consistency.py`
   - 输入：`COMMIT_MSG_FILE`（git hook 传入）
   - 逻辑：
     - 解析 commit message 中提到的文件路径（如 `SamplingView.vue`）
     - 解析 commit message 中的动作词（fix/feat/chore/docs/ci/test）
     - 与 `git diff --cached --stat` 对比
     - 如果发现 message 提到某文件但 diff 中该文件被大量删除（如删除 >80% 内容），而 message 没提“删除/重构”，则 WARN 或 BLOCK
   - 阈值：第 1 版只 WARN，不 BLOCK。
     - 发现不一致时：向 stderr 打印警告，但 exit code 仍为 0。
     - 这样跑 1-2 sprint 观察 false positive，稳定后再考虑改 BLOCK。

2. **接入 pre-commit hook**
   - 修改 `.githooks/prepare-commit-msg` 或 `.githooks/commit-msg`
   - 调用 `python3 scripts/git/check_commit_msg_diff_consistency.py "$1"`
   - 如 hook 文件不存在，新建 `commit-msg` 并让用户跑 `bash scripts/setup-hooks.sh` 激活

3. **接入 CI（可选，第 2 阶段）**
   - `.github/workflows/lint.yml` 加一步对已提交 message 做 consistency check
   - 先不做，等本地 hook 稳定后再扩。

4. **回归测试**
   - 新文件：`backend/tests/test_commit_msg_diff_consistency.py`
   - 覆盖：正常 message pass / 提到文件但大量删除 warn / 无文件 mention skip

### 4.3 验收标准

- `python3 scripts/git/check_commit_msg_diff_consistency.py /tmp/test_msg.txt` 对样例 message 输出正确 rc
- `bash .githooks/commit-msg /tmp/test_msg.txt` 在测试场景下行为符合预期
- 新增 test 通过

---

## 5. 通用实施规范

### 5.1 分支

- 每个任务独立分支：
  - `feature/sprint52-visitor-router`
  - `feature/sprint52-50m-scale-benchmark`
  - `feature/sprint52-commit-msg-diff-hook`

### 5.2 Commit 规范

- 每个逻辑单元单独 commit
- message 格式：`feat(scope): Sprint 52 — 描述`
- 末尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`

### 5.3 测试要求

- 任何 backend 改动 → `python3 -m pytest backend/tests/ -x -q`
- 任何 frontend/e2e 改动 → `cd frontend-vue3 && npx playwright test`
- 任何 build 相关改动 → `cd frontend-vue3 && npx vite build`

### 5.4 禁止事项

- 禁止在 `main` 直接改代码
- 禁止 `git add -A`
- 禁止一个 commit 混多个不相关功能
- 禁止跳过 pre-commit hook（除非 race flake，需注释说明）

### 5.5 完成后的返回信息

Codex 实施完成后，向 Claude 返回：
- 每个任务的完成状态
- 修改的文件列表
- 测试结果
- 建议的 commit message

---

## 6. 已确认决策

| 决策 | 已选方案 |
|---|---|
| visitor / export / report | **A) 激活 visitor router** |
| 50m scale | **阶梯验证：1m → 5m → 10m → 50m** |
| commit-msg hook 第 1 版 | **WARN 模式，不 BLOCK** |

---

## 7. 参考文件

- `frontend-vue3/src/router/index.ts`
- `frontend-vue3/src/views/AudienceView.vue`
- `scripts/etl/cli.py`
- `scripts/run_etl.py`
- `.githooks/pre-commit`
- `docs/TECH-DEBT.md`
- Sprint 39 close memory（visitor audit 结论）
- Sprint 32.3 close memory（a9b1d91 教训）

---

*Generated by Claude Stage 1 for Codex Stage 2 implementation.*
