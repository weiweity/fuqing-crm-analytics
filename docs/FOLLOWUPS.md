# 后续 Follow-up 清单

> **状态**: 待执行（v0.4.7.3.3 后归档 2026-06-06）
> **触发原因**: GitHub Actions ci/test 30+ runs 100% 红, 4 步修链才绿 (v0.4.7.3 / .3.1 / .3.2 / .3.3). 不做防复发下次还会重演

---

## 根因复盘（避免重复踩）

1. **修 CI ImportError 不能只解 pytest 报告的那一个** — 下一个 import chain 可能撞另一个. 正确做法: AST 扫所有 pytest-walkable 路径的 `import X` / `from X`, 跟 requirements.txt 对账, 缺的批量补
2. **test 断言要顺序无关** — `glob.glob` / `os.walk` / `set` 在不同文件系统 (macOS extfs vs Linux ext4) 迭代顺序不同. 假设 `files[N].exists()` 必 flaky
3. **CI 100% 红了 30+ run 不可接受** — signal 完全失真 + alert fatigue + 真回归也看不见, 比 bug 更危险

---

## 防复发方案 (按 ROI 排)

### P0: pre-commit import 完整性检查 (0.5h) ⭐ 根因预防
- **做什么**: 在现有 `.githooks/pre-commit` 加 1 个 step, 跑 `python3 -c "import X"` over all 3rd-party imports (backend/ + scripts/etl/ + transitive). 缺任意一个 → commit 拒绝
- **收益**: import 缺在本地就拦住, 根本到不了 CI. 这是 v0.4.7.3 → .3.2 链式的根因预防
- **验收**: 故意删 bcrypt 写代码, commit 应被本地 hook 拦

### P1: GitHub Actions 定时 nightly 健康检查 (0.5h)
- **做什么**: 加 `.github/workflows/nightly.yml`, 每天 9 点跑全量 pytest + 单独跑一遍 import 完整性
- **收益**: 周末/夜间回归早 1 天发现. 不会再 30+ run 红了才看到
- **验收**: 故意改坏, 等晚上 9 点, 看 GitHub mail

### P1: workflow 强约束 + 锁文件 (1h)
- **做什么**: `pip freeze > requirements-lock.txt`, workflow 装 `requirements-lock.txt` (pin 死版本). 改 deps 必须走 PR
- **收益**: 杜绝"装包列表跟声明漂移"复发 (v0.4.7.3 根因)
- **验收**: lock 文件入 git, workflow 装它, deps 漂移只能 PR

### P2: test 顺序无关 lint (1h)
- **做什么**: 加个 pre-commit 钩子跑 AST 扫描, 检测 `assert files[N].exists()` 这种 N-index 断言, 警告
- **收益**: 修一个 test 教一个, 攒多了就稳
- **验收**: 故意写 `files[0].exists()` 应被警告

### P2: GitHub Actions 通知收敛 (2 min) ⭐ 立即可做
- **做什么**: GitHub → Settings → Notifications → Actions 调成只对 main 分支失败发邮件, feature branch 静默
- **收益**: 减少 90% feature branch CI 噪音
- **验收**: 提个 feature branch PR, 故意让它 CI 红, 不收到邮件

### P3: 每周 CI 健康报告 (0.5h)
- **做什么**: workflow 跑完后把 `pytest -q` 的 passed/failed 数写进 artifact, 每周一对账
- **收益**: 趋势可见, 回归早 1 周发现
- **验收**: artifact 文件能下载, 看到 pytest pass 数 trend

---

## 立即可做 (5 分钟, 0 风险)

**P2 GitHub 通知收敛** 是唯一的 2 分钟方案. 上 GitHub → Settings → Notifications → Actions → 取消 "Send notifications for failed workflows I trigger" → 勾 "Only notify on failed workflow runs" 反向: 只对 main 发.

其它 5 个 (P0/P1/P1/P2/P3) 都需要写代码 + commit, 进 backlog 等下次 sprint 一起做.

---

## 关联 commit / 文档

- v0.4.7.3 / .3.1 / .3.2 / .3.3 CHANGELOG: 完整 4 步修链记录
- `docs/handoff-2026-06-05-errata.md`: 6/5 治理事件主文档 (349GB /tmp 污染 / 17 issues / 4 层防护)
- `.gstack/qa-reports/qa-report-v0.4.7.3.3-2026-06-06.md`: QA 报告 (8/8 PASS, Health 100)
- main HEAD: `73018af` (CI 绿)
