# 后续 Follow-up 清单

> **状态**: 5/6 已执行 (2026-06-06 归档)
> **触发原因**: GitHub Actions ci/test 30+ runs 100% 红, 4 步修链才绿 (v0.4.7.3 / .3.1 / .3.2 / .3.3). 不做防复发下次还会重演
> **收尾**: B1-B6 共 6 项 CI 防复发方案 (5 项 code commit + 1 项手动) 全部落地, 详见每节 ✅ 标记

---

## 根因复盘（避免重复踩）

1. **修 CI ImportError 不能只解 pytest 报告的那一个** — 下一个 import chain 可能撞另一个. 正确做法: AST 扫所有 pytest-walkable 路径的 `import X` / `from X`, 跟 requirements.txt 对账, 缺的批量补
2. **test 断言要顺序无关** — `glob.glob` / `os.walk` / `set` 在不同文件系统 (macOS extfs vs Linux ext4) 迭代顺序不同. 假设 `files[N].exists()` 必 flaky
3. **CI 100% 红了 30+ run 不可接受** — signal 完全失真 + alert fatigue + 真回归也看不见, 比 bug 更危险

---

## 防复发方案 (按 ROI 排)

### ✅ P0: pre-commit import 完整性检查 (0.5h) ⭐ 根因预防 — `8ca17d9`
- **做什么**: 在现有 `.githooks/pre-commit` 加 1 个 step, 跑 `python3 -c "import X"` over all 3rd-party imports (backend/ + scripts/etl/ + transitive). 缺任意一个 → commit 拒绝
- **收益**: import 缺在本地就拦住, 根本到不了 CI. 这是 v0.4.7.3 → .3.2 链式的根因预防
- **验收**: 故意删 bcrypt 写代码, commit 应被本地 hook 拦
- **状态**: ✅ 完成 (commit `8ca17d9` feat(ci): B2 P0 根因预防 — pre-commit import 完整性检查 v0.4.7.5)

### ✅ P1: GitHub Actions 定时 nightly 健康检查 (0.5h) — `32252e7`
- **做什么**: 加 `.github/workflows/nightly.yml`, 每天 9 点跑全量 pytest + 单独跑一遍 import 完整性
- **收益**: 周末/夜间回归早 1 天发现. 不会再 30+ run 红了才看到
- **验收**: 故意改坏, 等晚上 9 点, 看 GitHub mail
- **状态**: ✅ 完成 (commit `32252e7` feat(ci): B3 P1 nightly 健康检查 workflow v0.4.7.6)

### ✅ P1: workflow 强约束 + 锁文件 (1h) — `eb40690`
- **做什么**: `pip freeze > requirements-lock.txt`, workflow 装 `requirements-lock.txt` (pin 死版本). 改 deps 必须走 PR
- **收益**: 杜绝"装包列表跟声明漂移"复发 (v0.4.7.3 根因)
- **验收**: lock 文件入 git, workflow 装它, deps 漂移只能 PR
- **状态**: ✅ 完成 (commit `eb40690` feat(ci): B4 P1 requirements-lock.txt 锁版本 v0.4.7.7)

### ✅ P2: test 顺序无关 lint (1h) — `496f1d8`
- **做什么**: 加个 pre-commit 钩子跑 AST 扫描, 检测 `assert files[N].exists()` 这种 N-index 断言, 警告
- **收益**: 修一个 test 教一个, 攒多了就稳
- **验收**: 故意写 `files[0].exists()` 应被警告
- **状态**: ✅ 完成 (commit `496f1d8` feat(ci): B5 P2 test 顺序无关性 lint v0.4.7.8)

### ✅ P2: GitHub Actions 通知收敛 (2 min) ⭐ 立即可做 — B1 手动 (2026-06-06)
- **做什么**: GitHub → Settings → Notifications → Actions 调成只对 main 分支失败发邮件, feature branch 静默
- **收益**: 减少 90% feature branch CI 噪音
- **验收**: 提个 feature branch PR, 故意让它 CI 红, 不收到邮件
- **状态**: ✅ 完成 (B1 用户浏览器已手动设置, 2026-06-06, 无 commit SHA)

### ✅ P3: 每周 CI 健康报告 (0.5h) — `45f72bf`
- **做什么**: workflow 跑完后把 `pytest -q` 的 passed/failed 数写进 artifact, 每周一对账
- **收益**: 趋势可见, 回归早 1 周发现
- **验收**: artifact 文件能下载, 看到 pytest pass 数 trend
- **状态**: ✅ 完成 (commit `45f72bf` feat(ci): B6 P3 每周 CI 健康报告 v0.4.7.9)

---

## 立即可做 (5 分钟, 0 风险) — ✅ B1 完成 (2026-06-06)

**P2 GitHub 通知收敛** 是唯一的 2 分钟方案. 上 GitHub → Settings → Notifications → Actions → 取消 "Send notifications for failed workflows I trigger" → 勾 "Only notify on failed workflow runs" 反向: 只对 main 发.

✅ **B1 已完成**: 用户浏览器已手动设置, 2026-06-06 验证 feature branch 静默生效. 无 commit SHA (浏览器配置不在 git).

其它 5 个 (P0/P1/P1/P2/P3) 都已经走完整 12 流程合 main, 见上方各节 commit SHA 锚定.

---

## 关联 commit / 文档

- v0.4.7.3 / .3.1 / .3.2 / .3.3 CHANGELOG: 完整 4 步修链记录
- `docs/handoff-2026-06-05-errata.md`: 6/5 治理事件主文档 (349GB /tmp 污染 / 17 issues / 4 层防护)
- `.gstack/qa-reports/qa-report-v0.4.7.3.3-2026-06-06.md`: QA 报告 (8/8 PASS, Health 100)
- main HEAD: `f344d11` (P0-D1 VERSION drift 修复 v0.4.10.1, CI 绿)
- B2-B6 commit 链: `8ca17d9` → `32252e7` → `eb40690` → `496f1d8` → `45f72bf` (v0.4.7.5 → v0.4.7.9)
- B1 (通知收敛): 手动配置, 2026-06-06 完成
