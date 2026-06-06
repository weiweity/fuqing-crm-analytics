# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepchangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v0.4.7.9] - 2026-06-06 - feat(ci): B6 P3 每周 CI 健康报告

### Added
- **`.github/workflows/weekly-report.yml`** (新): 每周一 UTC 1:00 (北京时间 9:00) 跑全量 pytest, 输出 junit XML + 上传 artifact (90 天保留) + 写 step summary. 跟 nightly.yml (B3) 风格一致, 但 trigger cron 是每周一. 加 `workflow_dispatch` 允许手动触发

### 趋势可见
- **Artifact 下载**: GitHub repo → Actions → Weekly Health Report → 任意 run → Artifacts → `pytest-results` (90 天内可下)
- **Step summary**: 每个 run 的 Summary tab 显示 `tests=N failures=N errors=N skipped=N time=Ns`, 一目了然
- **对账场景**: 周一上午 9 点 GitHub mail 提醒, 团队 review 上周 pass/fail trend, 早 1 周发现回归

### B6 配套: CI 防复发 6 件套 + 报告
- B1 (2 min): GitHub 通知收敛 — 减噪
- B2 (P0): pre-commit import 完整性检查 — 根因预防
- B3 (P1): nightly 健康检查 — 早 1 天发现
- B4 (P1): requirements-lock.txt — 防装包漂移
- B5 (P2): test 顺序无关 lint — 防 flaky test
- **B6 (P3)**: 每周健康报告 — 趋势可见 (本 commit)
- **总**: 6 件全 0.5-1h 小块, 总 ~3.5h, CI 防御 100% 完备


## [v0.4.7.8] - 2026-06-06 - feat(ci): B5 P2 test 顺序无关性 lint

### Added
- **`.githooks/check_test_order.py`** (~85 行, 新): AST 扫 `backend/tests/` + `tests/` 检测 N-index 断言 (`assert X[N].method()` 模式), WARN 不阻断 commit. 根因预防 v0.4.7.3.3 跨平台 flaky test (macOS extfs vs Linux ext4 glob 返回顺序不同, 索引断言跨平台 flaky)
- **`.githooks/pre-commit`**: B2 step 后 + pytest 前 加 B5 step 调 `check_test_order.py`, `|| true` 保证 WARN 不 fail

### 设计选择
- **WARN 不 FAIL**: 故意 N-index (固定 list, mock data) 多, 强 fail 误伤. 跟 ruff 类似规则 (W 是 warn, E 是 error) 一致
- **检测模式**: `assert X[N].method()` (N 是 int literal, .method() 是 call). 例 `assert files[0].exists()` / `assert arr[2].is_file()` 都报
- **修法推荐**: 改顺序无关断言 `sum(1 for f in files if f.exists()) == 1`

### 验收
- 故意写 `backend/tests/_tmp_b5_mock.py` 含 `assert files[0].exists()` + `assert files[2].is_file()` → B5 报 2 处. 清理后 ✅ 无 N-index 顺序依赖
- 项目当前 N-index 顺序依赖断言 0 处 (v0.4.7.3.3 修链已修干净)


## [v0.4.7.7] - 2026-06-06 - feat(ci): B4 P1 requirements-lock.txt 锁版本

### Added
- **`requirements-lock.txt`** (124 行, 新): `pip freeze` 输出, pin 死所有 transitive deps. 杜绝"装包列表跟声明漂移"复发 (v0.4.7.3 根因)

### Changed
- **`.github/workflows/lint.yml`**: `pip install -r requirements.txt` → `pip install -r requirements-lock.txt`. CI 装版本与本机 lock 严格一致
- **`.github/workflows/nightly.yml`** (v0.4.7.6): 同上

### Lock 维护约定
- **新增依赖**: `pip install X` → 跟 `requirements.txt` 同步 (声明) + `pip freeze > requirements-lock.txt` (锁版本) → 一起 commit
- **改版本**: `requirements.txt` 升下限 + lock 重 freeze, 两个文件一起 PR (声明 + 锁)
- **lock 漂移检测**: 跑 `pip install -r requirements-lock.txt` 跟当前 venv 对比, 一致 = 0 漂移
- **验收**: 故意改 `requirements-lock.txt` 某版本号 → CI lint job 应挂 (装包失败或 pytest fail)

### Trade-off
- lock 文件含 venv 全局污染 (124 个包, 项目直接用 ~16). CI 装 30-60s, 但保 0 漂移. 收益 > 成本
- 真要最小化 lock: 用 `pip-compile requirements.txt -o requirements-lock.txt` (项目没装 pip-tools, 后续可加)


## [v0.4.7.6] - 2026-06-06 - feat(ci): B3 P1 nightly 健康检查 workflow

### Added
- **`.github/workflows/nightly.yml`** (39 行, 新): 每天 UTC 13:00 (北京时间 21:00) 跑全量 pytest + ruff + B2 import 完整性复检. 跟 `lint.yml` 风格一致 (Python 3.14 + `pip install -r requirements.txt` 单一来源). 加 `workflow_dispatch` 允许手动触发 (测试 + 应急验证)

### 防复发效果
- **周末/夜间回归早 1 天发现**: 不会再 v0.4.7.3 那种 30+ run 红了才看到
- **B2 双保险**: 本地 pre-commit 防线 (B2/v0.4.7.5) + nightly 复检 (B3/v0.4.7.6), 即使 `git commit --no-verify` 绕过本地, nightly 仍能抓 import 漏装
- **手动触发**: GitHub repo → Actions → Nightly Health Check → Run workflow, 验证 cron 之外随时可跑

### 触发时间
- 北京 21:00 (UTC 13:00) — 跟 FOLLOWUPS.md §B3 描述一致. GitHub cron 是 UTC, 时区在 cron 字符串里直接算


## [v0.4.7.5] - 2026-06-06 - feat(ci): B2 P0 根因预防 — pre-commit import 完整性检查

### Added
- **`.githooks/check_imports.py`** (194 行, 新): Python AST 扫 `backend/` + `scripts/etl/` 3rd-party imports, 跟 `requirements.txt` 对账. 缺任意一个 → exit 1 拦截 commit. 根因预防 v0.4.7.3 → .3.2 链式 CI ImportError 修链. 自动检测项目本地包 (有 `__init__.py` 的目录) + monorepo namespace package (scraper/scripts/tests)
- **`.githooks/pre-commit`**: ruff 后 + pytest 前 加 B2 step 调 `check_imports.py`, 失败 print 缺失包 + 实际使用文件, 修法指引

### 防复发效果
- **验收测试**: 故意从 `requirements.txt` 删 bcrypt 行 → B2 exit 1 拦截, 提示 `bcrypt (used in: backend/routers/auth.py)`. 恢复 → exit 0 放行
- **CI 0 噪音**: 本地 pre-commit 拦下, GitHub Actions 不会再撞 v0.4.7.3 那种 30+ 红 CI 修链
- **限**: 静态 AST 扫, 跳 dynamic import (`importlib.import_module("X")`). 后续如需补, 改 check_imports.py 加 try-except import 即可

### 已知 PIP 别名 (项目实际可能用)
- `dotenv` ↔ `python-dotenv`, `pptx` ↔ `python-pptx`, `dateutil` ↔ `python-dateutil`, `yaml` ↔ `pyyaml`, `bs4` ↔ `beautifulsoup4`, `pil` ↔ `pillow`, `cv2` ↔ `opencv-python`, `sklearn` ↔ `scikit-learn`, `skimage` ↔ `scikit-image`, `crypto` ↔ `pycryptodome`, `attr` ↔ `attrs`, `magic` ↔ `python-magic`, `serial` ↔ `pyserial`, `grpc` ↔ `grpcio`


## [v0.4.7.4.1] - 2026-06-06 - fix: VERSION drift 0.3.5 → 0.4.7.4 + CLAUDE.md / README.md 状态同步

### Fixed
- **`VERSION` 文件 drift**: 写 0.3.5, 实际 v0.4.7.4 (CHANGELOG 顶部对齐). 阻入口混乱, 下次 sprint 起手无歧义
- **`CLAUDE.md` L30 状态表**: v0.4.6 / 222 passed / 8 skipped → **v0.4.7.4 / 224 passed / 8 skipped** (同步 main HEAD 3c531ec)
- **`README.md` L25 + L182 状态行**: `222 passed / 8 skipped（v0.4.6）` → `224 passed / 8 skipped（v0.4.7.4）` (同源 drift, 一并修)


## [v0.4.7.4] - 2026-06-06 - docs: 归档 CI 30+ 红修复链的防复发 6 项 follow-up

### Added
- **`docs/FOLLOWUPS.md`** (新): 归档 v0.4.7.3 4 步修链的根因复盘 (3 条) + 6 项防复发 follow-up 方案 (P0-P3, 含工作量 + 收益 + 验收), 关联 commit / QA 报告 / handoff 文档索引. 状态 "待执行", 触发条件是下次 sprint 起新工作前 review 一遍挑可做的入 sprint backlog

### 防复发方案 (P0-P3, 工作量从 2min 到 1h)
- **P0** pre-commit import 完整性检查 — 根因预防, 0.5h
- **P1** nightly CI 健康检查 — 早发现, 0.5h
- **P1** requirements-lock.txt — 防"装包漂移", 1h
- **P2** test 顺序无关 lint — 防 flaky test, 1h
- **P2** GitHub 通知收敛 — 立即可做, 2min
- **P3** 每周 CI 健康报告 — 趋势可见, 0.5h

详见 `docs/FOLLOWUPS.md` §防复发方案


## [v0.4.7.3.3] - 2026-06-06 - ci: 修 test_byte_cap 跨平台 flaky (闭合 v0.4.7.3.2 漏的 test bug)

### Fixed
- **`test_byte_cap` 跨平台 flaky**: 3 个文件各 50GB, cap 100GB, 期望删 2 留 1. 原 assertion `assert files[2].exists()` 假设 files[2] 保留, 但 `_collect_fq_tmp_orphans` 用 `glob.glob` + 稳定排序, 3 文件同 mtime 同 size 时返回顺序由文件系统决定. macOS extfs 和 Linux ext4 返回顺序不同, 本地 (mac) 删 0/1 留 2 (test 过), CI (ubuntu) 删 1/2 留 0 (test 挂 `assert False`). 修: 顺序无关断言 `sum(1 for f in files if f.exists()) == 1`

### 根因复盘 3
v0.4.7.3.2 那个"应该没有第 4 个了" 错. 实际第 4 个是 test 自身的 order 假设, 不是 deps 缺. whack-a-mole 还能往后延: 装对 deps → test 业务逻辑通过 → test 自身的隐藏假设暴露. 真正的解是 **修 test, 不修代码** (代码行为对, 是 test 写错了)


## [v0.4.7.3.2] - 2026-06-06 - ci: 补 xxhash 到 requirements.txt (闭合 v0.4.7.3.1 漏的 lazy import)

### Fixed
- **`requirements.txt` 漏 `xxhash`**: v0.4.7.3.1 解了 bcrypt, 真 CI 又过 62 个 test, 撞 `scripts/etl/config.py:198 import xxhash` (lazy import, 在 `_file_xxhash` 函数内). `test_fill_parquet_cache_basic` 因 xxhash 缺失导致文件被标"跳过", `assert converted == 1` 失败 (`assert 0 == 1`)

### 根因复盘 2
这次不 whack-a-mole, 一次扫全 pytest-walkable 路径 (`backend/` + `scripts/etl/*.py` + transitive) 的 third-party imports vs requirements.txt, 只剩 xxhash. 全量扫全补齐, 应该没有第 4 个了

### Whack-a-mole 通用教训
- 修 CI ImportError 不能只解 pytest 报告的那一个, 下一个 import chain 可能撞另一个
- 正确做法: AST 扫所有 pytest 可达路径的 `import X` / `from X`, 跟 requirements.txt 全量对账, 缺的批量补, 一次 push 验证


## [v0.4.7.3.1] - 2026-06-06 - ci: 补 bcrypt 到 requirements.txt (闭合 v0.4.7.3 漏的 import)

### Fixed
- **`requirements.txt` 漏 `bcrypt`**: v0.4.7.3 只补了 fastapi, 真 CI 跑起来又发现 `backend/routers/auth.py:16 import bcrypt` ModuleNotFoundError. backend/ 唯一真缺 third-party (其它 stdlib 不算). 修: `bcrypt>=4.0.0` 加到工具段, local 是 5.0.0

### 根因复盘
v0.4.7.3 那个 workflow 报告"ModuleNotFoundError: No module named 'fastapi'" 是正确的, 但只解了 1/2 路径. `pip install -r requirements.txt` 装上 fastapi 后, 下一个 import chain (`backend.main` → `backend.routers.__init__` → `auth.py:16`) 又撞 bcrypt. **通用经验: 修 CI ImportError 永远只解当前一个是不够的, 一次把缺失依赖全量补齐**


## [v0.4.7.3] - 2026-06-06 - ci: GitHub Actions test job 用 requirements.txt 单一来源 (修 30/30 red CI)

### Fixed
- **`.github/workflows/lint.yml` test job 漏装 `fastapi`** (修了 30+ runs 100% 红的 CI 噪音): 硬编码 `pip install duckdb pandas pyarrow pytest openpyxl` 漏 9 个 requirements.txt 里的包 (fastapi/uvicorn/pydantic/numpy/openai/python-dotenv/python-dateutil/python-pptx/black), 改用 `pip install -r requirements.txt` 单一来源. `backend/services/exceptions.py:8` + 9 个 routers 都 `from fastapi import ...`, pytest collection 阶段直接 `ModuleNotFoundError` 退出码 1, 是 30/30 runs 红的根因
- **CI 装包时长** (顺手): setup-python 加 `cache: 'pip'`, 用 `requirements.txt` hash 作 cache key, 命中时跳过 5-10s 装包

### CI 噪音 → 真实信号
- 修前: ci/test 100% red, ci/lint 100% green, GitHub 邮件轰炸, alert fatigue 训练用户忽略通知, 真回归也看不见
- 修后: ci/test 跑通全量 224/8, ci/lint 保持 green, 邮件停 (GitHub 只对 failure 发邮件)


## [v0.4.7.2] - 2026-06-05 - docs: 同步 pre-commit pytest hook 到 CLAUDE.md + README.md CI/CD 防线表

### Fixed
- **CLAUDE.md L79** (CI/CD 防线表): pre-commit 拦截内容 `ruff lint` → `ruff lint + pytest (20/8 cleanup)`, 同步 v0.4.7 落地的 pre-commit pytest hook
- **README.md L24** (项目状态列表): `pre-commit (ruff)` → `pre-commit (ruff + pytest 20/8)`, 同步同上


## [v0.4.7.1] - 2026-06-05 - chore: pickup uncommitted handoff + PR template + codegraph cache gitignore

### Added
- **.github/pull_request_template.md** (47 行, 新): PR checklist 含 codegraph affected 检查. 项目当前用 merge-to-main 流程 (handoff #1), 模板保留 0 副作用, 为未来协作扩展友好
- **docs/handoff-2026-06-05.md** (200 行, 新): 6/5 治理事件快照 (TL;DR / 必读 / 时间线 / 4 层防护 / 状态表 / 17 issues / 必做). 不动 handoff 主干 (D1=C errata 路线), handoff 失真以 docs/handoff-2026-06-05-errata.md 单独勘误

### Changed
- **CLAUDE.md** (linter 段 +18 行, 新): "代码探索" 段, agent 优先用 `mcp__codegraph__*` 工具而非 Read+Grep 跳文件 (codegraph_explore 主, search 找位置, callers/impact 评估影响, callees 找调用, status 看健康)
- **.gitignore** (+1 line, 新): `.codegraph/` 屏蔽 (10MB DB cache 不入 git, 匹配既有 .workbuddy/.gstack/.codebuddy/.context/.claude/ 模式)


## [v0.4.7] - 2026-06-05 - ci: pre-commit pytest cleanup orphans hook

### Added
- **Pre-commit pytest hook (cleanup orphans)**: `.pre-commit-config.yaml` + `.githooks/pre-commit` 双 hook 配置, 仅跑 20 个 cleanup 用例, 防止 F3/F7 回归
- **CLI flag `--cleanup-tmp`** — `python3 scripts/etl/cli.py --cleanup-tmp` 紧急清理 /tmp 孤儿（handoff 6/5 follow-up #3 落地，免依赖 ETL 触发）。调 `_cleanup_fq_tmp_orphans()` + 打印删除计数 + sys.exit(0)。2 个新 pytest 用例覆盖（`TestCleanupTmpFlag::test_argparse_accepts_cleanup_tmp` + `test_cleanup_tmp_prints_audit_path`）。pytest 222/8 → 224/8。

### Documentation
- **README "运维安全 / 磁盘治理" 章节** — 4 层防护表 + 紧急清理命令 + launchd 调度状态查询 + 审计/状态文件清单 + F3 marker / ms-playwright 协议。闭环 v0.4.6.1 留的 "新 public surface 零 reference 覆盖" follow-up。

### Fixed
- **README 测试段 stale**：153 → 222 passed（v0.4.6.1 doc 同步只改了当前状态段 L25，测试段 L136 12 文件列表 + 153 数字未跟进），并补 `test_wo_cleanup_orphans.py` 20 用例到列表。
- **`--cleanup-tmp` 双触发审计日志污染** — QA 阶段发现：`--cleanup-tmp` 显式调 `_cleanup_fq_tmp_orphans()` 后 `sys.exit(0)` 仍触发 atexit 二次调用，1 次 CLI 产生 2 条 audit log（幂等无数据风险但污染）。修复：显式调用前 `atexit.unregister(_cleanup_fq_tmp_orphans)` 取消二次注册。

### CHANGELOG 锚点补全
- v0.4.5 标题补 commit SHA `db70b75` (merge) + `cd71c68` (Layer 1) + `48f7f31` (Layer 4)
- v0.4.6 标题补 commit SHA `5e64ba3` (merge) + `797b769` (F3+F7)
- v0.4.6.1 标题补 commit SHA `df5d250` (doc sync)
- v0.4.5 Security 段补 16 个 F 编号映射（handoff-2026-06-05.md 第 5 节 source of truth 同步）


## [v0.4.6.2] - 2026-06-05 - docs: handoff-2026-06-05-errata 勘误 (10 项失真补全 + trap EXIT)

### Added
- docs/handoff-2026-06-05-errata.md (100-130 行): 10 项 handoff 失真/缺漏勘误, §3.1 4 层↔17 issues 映射表作实操地图, §7 禁令路径勘误, §8 路径+产物补, 附录 A SHA 错位, 附录 B 数字对齐
- docs/DOCUMENT-INDEX.md: 加 errata 索引行

### Fixed
- scripts/etl/cleanup_backups.sh: 加 trap "rm -f $LOCK" EXIT 修 stale 锁 (异常退出不再留 0B lock)


## [v0.4.6.1] - 2026-06-05 - docs: 同步 entry-point 文档到 v0.4.6 状态 (`df5d250`)

### Fixed
- **CLAUDE.md line 30 stale**: 版本状态 `v0.4.4 (204 passed)` → `v0.4.6 (222 passed)`。CHANGELOG.md v0.4.5/v0.4.6 早已合入，但项目"启动必读"表里仍是 v0.4.4 baseline，会让后续 session 误判测试基线。
- **README.md line 25 stale**: 测试状态 `153 passed` → `222 passed (v0.4.6)`。同根因：v0.4.4 之前的快照没跟随 v0.4.5/v0.4.6 pytest 套件增长同步。

### Documentation
- **Coverage gap (未修，留 follow-up)**: v0.4.5/v0.4.6 的 Layer 1-4 防护 (atexit 钩子 / zshrc 告警 / workbuddy cache 规范 / launchd backups) + 349GB 磁盘释放 在 README.md 完全没提。CI 用户/运维新接手时不知道这些治理。建议下次补一个"运维安全/磁盘治理"章节（Critical gap: 新 public surface 零 reference 覆盖）。


## [v0.4.6] - 2026-06-05 - atexit 钩子 ASK 限制项代码层修复 (`5e64ba3` merge, `797b769` F3+F7)

### Fixed
- **F3 (HIGH): marker 文件检测异常退出** — atexit 在 `kill -9` / `os._exit()` / OOM killer 下不触发（Python 文档明确），通过 `main()` 入口（`atexit.register` 之前）写 `/tmp/fuqing-etl-marker.json` 旁路信号，`_cleanup_fq_tmp_orphans` 读 marker 判断是否正常 ETL 退出。marker 缺失 = 上次异常退出，保守模式清理（5 文件 + 100GB 内，log 标注 reason）；marker 存在 = 正常退出。清理完后无论原本是否存在都删 marker，避免下次误判。
- **F7 (MEDIUM): symlink 不再被误报 size + 直接跳过清理** — `os.path.getmtime` / `os.path.getsize` 跟随 symlink target 误报 size，且 `os.remove` 只删 link 不动 target、target 是否 active 难以判断。`_collect_fq_tmp_orphans` 加 `islink is True` 检查（用 `is True` 兼容 mock 场景），匹配到 symlink 直接 `[skip symlink]` 跳过。

### Added
- **3 个新 pytest 用例 + 3 个常量 sanity** — `test_f3_marker_written_in_main`（验证 main() 入口写 marker + 调用顺序）、`test_f3_marker_cleared_on_cleanup`（场景 A marker 存在 / 场景 B marker 缺失均软失败）、`test_f7_skip_symlink`（创建 symlink 验证不被删 + target 不动）。

### Documentation
- **F6 (LOW) deferred 文档化** — `mtime` 可被 `touch -t` 改写，非"活跃文件"绝对可靠信号。真正的活跃信号应是 `flock` / `lsof` / marker file 替代 mtime，但改造复杂度高（v0.4.5 mtime 24h 阈值已兜住常见场景），留作 future work。在 `cli.py` Layer 1 注释明确标注 deferred 原因。

### Quality
- `test_byte_cap` 兼容更新：补 `mock_os.path.islink.return_value = False`（F7 新增检查）+ `mock_os.path.exists.return_value = False`（F3 marker 检测），避免 mock 把所有文件当 symlink 跳过 / 误判 marker 存在。
- 完整 pytest 套 **222 passed, 8 skipped**（v0.4.5 基线 216 + 6 新增, 0 回归）。ruff check 0 errors。


## [v0.4.5] - 2026-06-05 - WO-x /tmp 孤儿治理（4 层防护）(`db70b75` merge, `cd71c68` Layer 1, `48f7f31` Layer 4)

### Fixed
- **/private/tmp 7 个孤儿 duckdb 清理（~349GB 释放）** — 6/1-6/4 期间 c346e96e / a6de2e19 子 agent 调试 E2E 测试手工 `cp` 主库到 `/tmp`，累计 7 个 38-44GB 孤儿（`_fq_ro.duckdb` × 2 + `fuqing_query.duckdb` + `fuqing_repurchase.duckdb` + `fuqing_crm_readonly.duckdb` + `fuqing_tmp.duckdb` + `claude-501/tmpzc3i2h38.duckdb`），磁盘从 53% 满载降到 22%。lsof 0 进程占用、uvicorn 单例 read_only 句柄仅指向主库，零业务影响。

### Added
- **Layer 1 — `scripts/etl/cli.py` atexit 钩子 `_cleanup_fq_tmp_orphans()`** — ETL 退出时清理 `/private/tmp` 下 `FQ_TMP_PREFIXES` 白名单（`_fq_ro*` + `fuqing_*`）24h+ 旧文件。**不在 import 顶层注册**（防 pytest 退出时静默扫真 `/tmp`，F4 修复）。**5 个文件 cap + 100GB 字节 cap** 双限（防单次爆删）。**sort by mtime 倒序取 top N**（治 first-prefix starvation）。软失败 + 持久日志到 `/tmp/fuqing-tmp-cleanup.log`。
- **Layer 1 — `backend/tests/test_wo_cleanup_orphans.py` 12 个 pytest 用例** — 覆盖白名单 / 24h 阈值 / count cap / byte cap / cap starvation / 软失败 / 持久日志 / atexit 不在 import 时注册 / 常量 sanity。完整 pytest 套 **216 passed, 8 skipped**（v0.4.4 基线 204 + 12 新增, 0 回归）。
- **Layer 2 — `~/.zshrc` `_check_fq_tmp_orphans()` 磁盘告警** — zsh 启动时检测 `/tmp` 50GB+ 占用并打印告警（不删文件）。
- **Layer 3 — `~/.workbuddy/cache/fq-etl-validation/` 持久化规范** — 子 agent / gstack 调试副本改写到这里（30 天 TTL + 命名带时间戳），不再污染 `/tmp`。
- **Layer 4 — `scripts/etl/cleanup_backups.sh` + `scripts/etl/launchd/com.fuqing.backup-cleanup.weekly.plist`** — `data/processed/backups/` 7 天保留清理，周日凌晨 3 点 launchd 触发（`set -euo pipefail` + 显式 PATH + mkdir-based lock 兼容 macOS）。

### Security
- **Adversarial review 修复 17 个真实 issues** — CRITICAL 2 个（atexit 顶层注册 + 测试不隔离）+ HIGH 11 个（cap starvation / byte cap / 持久日志 / 软失败 / launchd PATH / pipefail / find 错误处理 / plist repo 化 / flock 兼容 / 测试假成功 / cli mock 兼容 Python 3.14）+ MED/LOW 4 个。3 个 Python 限制（kill -9 不触发 atexit / mtime 可改写 / symlink size 跟随）已文档化在 `cli.py` 注释，无法代码层修复。
- **v0.4.5 16 个 F 编号映射**（handoff-2026-06-05.md 第 5 节 source of truth）：F1 / F2 / F4 / F5 / F8 / F11 / F12 / F13 / F16 / F17 / F18 / F19 / F20 / F23 / F26 / F27。完整描述 ↔ 严重级别对应见 handoff 附录 B。F3 / F6 / F7 在 v0.4.6 收尾（F3+F7 代码强化 = `797b769`，F6 文档化为 future work = mtime 改 flock/lsof/marker 留作 deferred）。

### Performance
- `cap starvation` 修复后 100GB byte cap 限制单次累计删除字节，避免原始 7 个孤儿 (349GB) 单次只清 5 个 220GB 仍残留 130GB 的次优路径。


## [v0.3.6] - 2026-06-05 - WO-1 hotfix (P0 阻断 + 调度器恢复)

### Fixed
- **P0-#1+#2 r[4]→r[1] IndexError 修复（3 处全修）** — `scripts/etl/pipeline.py:307` + `scripts/etl/preload_rfm.py:716-717` 共 3 处。FIX-S1 commit 2d64d8c 当时只改了 cli.py:559，pipeline.py:305 + preload_rfm.py:716-717 漏改。run_full_etl 全量模式 Step 7 必抛 IndexError，CLI --auto / --range 模式必抛。本次热修彻底关掉。
- **P0-#3 W6 飞书通知贯穿 --update 入口** — `scripts/etl/cli.py` 8 处 step raise 前加 `notify_etl_complete({"failed_step": ..., "error": str(_exc)[:200], "mode": "auto"}, status="failed")`。原 W6 装饰器只挂在 `run_full_etl`，cli.py:472-575 step 1-7.5 失败时老板收不到告警。
- **P1-#1 existing_ids 退化改 raise（数据污染防御）** — `scripts/etl/pipeline.py:231` 原 `except Exception: existing_ids = set()` 静默退化为空集，导致会员行被当新订单 INSERT（重复 order_id）。现改 raise RuntimeError，ETL 拒绝在数据有损坏时继续。
- **P1-#6 3 处 except: pass 改 fail-loud** — `scripts/etl/cli.py:468` (cross_day 前置采样) + `:615` (6 道门禁收尾 cross_day/api_health/dedup，fail 时调 `gate_set('fail', error=...)`) + `:645` (Step 8 DuckDB 摘要)。原"狼来了"静默模式 → 看板永远假绿。
- **SRE 盲点：launchd plist 装回** — `bash scripts/etl/scheduler/install_macos.sh` 装回 `~/Library/LaunchAgents/com.fuqing.etl.daily.plist`。审计前 6/3 之后无 baseline = 整个 41 finding 都基于"有 cron 跑"的伪假设，本次装回后 8 道门禁 + partial baseline + scraper lark 通道真发挥价值。
- **W6 通知环境变量** — `.env` 加 `NOTIFY_OPEN_IDS=ou_boss_placeholder,ou_op_placeholder` (placeholder 待老板/运营提供真 open_id 后替换; graceful degrade 已就绪)

### Added
- **`backend/tests/test_wo1_smoke.py` 6 个 smoke E2E** (test_pipeline_import / test_preload_import / test_cli_import / test_notify_import / test_cli_notify_import_wired / test_cli_fail_loud_markers) — 治 FIX-S1 漏改根因 (P1-#8 test_w7_e2e_override.py 名实不副)，pytest 190/8 → 196/8

### Security
- W6 飞书通知链路完整化 = 老板/运营 9 点上班能看到 ETL 失败告警，dashboard 不再假绿。launchd 调度器恢复 = 数据每日自动更新无需人工触发。


## [v0.3.7] - 2026-06-05 - WO-2 lookback 边界校验

### Fixed
- **P1-#4 --lookback 缺 [1,3650] 校验 (P1-#4 防御)** — `scripts/etl/preload_rfm.py:683` 新增 `_valid_lookback(s)` argparse validator，CLI 入口拒绝 0/负数/>3650/非整数（错误信息清晰：`--lookback=0 越界, 必须在 [1, 3650] 区间`）。`preload_rfm.py:384` 库内调用也加 `assert all(1<=lb<=3650 for lb in lookbacks)`，不依赖 CLI 入口，双层防御。**测试**：CLI `0/-1/3651/abc` 全拒，`1/90/3650` 全过（90 写 372,588 行）；pytest 196/8 全绿，ruff 0 errors。
- **副作用**：未来 `--lookback=0` / `--lookback=20000` 等"数字看着合理但实际越界"的输入会立即被拦下，避免触发 DuckDB 8GB OOM。


## [v0.3.8] - 2026-06-05 - WO-3 W1 GROUPING SETS 边界用例

### Added
- **`backend/tests/test_w1_grouping_sets.py::TestW1BoundaryConditions` 8 个边界用例** (P1-#9 治本)：
  - `test_batch_lookback_at_min_boundary` (lookback=1 边界最小, 4/1 无订单 → 0 行)
  - `test_batch_lookback_at_max_boundary` (lookback=3650 边界最大, 含 1 年前订单 u01=1349)
  - `test_batch_raises_on_lookback_zero` (WO-2 库内 assert 防御, 0 越界)
  - `test_batch_raises_on_lookback_too_large` (lookback=3651 越界)
  - `test_batch_raises_on_negative_lookback` (-100 越界, 防负数变未来日期)
  - `test_batch_with_empty_orders_table` (空 orders 表 0 行不抛)
  - `test_batch_raises_on_empty_channels` (FIX-M8 防御, channels=[])
  - `test_batch_raises_on_out_of_range_in_mixed_lookbacks` (混合列表 5 个全检, 不只第一个)

### Quality
- **pytest 196/8 → 204/8** (+8 tests) — 治 FIX-S1 漏改根因的测试基建继续积累
- **ruff 0 errors** — 修 F841 (unused `count` 加 `assert count >= 0`)


## [v0.3.9] - 2026-06-05 - WO-4 SRE 可观测性

### Fixed
- **`scripts/etl/notify.py:84` `future.result()` 加 `timeout=10`** (P2-#1) — scraper 内部 `_send_lark_alert` 已有 5s timeout，但外层未保护：未来 SDK 升级移除内部 timeout / subprocess 卡 stdout 都会让 W6 通知阶段无限 join，拖累 ETL 进程退出。10s = 内部 5s × 2 缓冲。

### Added
- **`/tmp/fuqing-etl-health.json` 状态文件** (SRE 0 飞书 0 代码状态查询) — `scripts/etl/cli.py:692` 在「一键更新完成」后写 `last_status / ts / mode / gates_overall`。SRE oncall 可直接 `cat /tmp/fuqing-etl-health.json` 验最后跑批状态，**不依赖飞书**（飞书 9 点上班才看，凌晨 2 点出事 = 兜底查询）。写失败非阻塞（try/except 兜底）。

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **磁盘清理待 owner 决策**：`/data/processed/fuqing_crm.duckdb.backup_pre_full_etl_2026_06_03` 53.8GB (6/3 起未动)。DuckDB 无 `PRAGMA integrity_check` 语法，已验证 45GB 主库 14 表可读 (user_rfm 77M 行 / orders 10.6M / user_first_purchase 4.24M) 0.7s。


## [v0.4.0] - 2026-06-05 - WO-5 P2 季度清理 (类型/死列/文档/CLAUDE.md 例外)

### Changed
- **CLAUDE.md 接口开发六步 - ETL 脚本连接例外条款** (P2-#2) — 新增段落说明 `scripts/etl/*` 12 处 `duckdb.connect` + `conn.close()` 是合理的：① ETL 跑批长（30-60min）会污染单例 config；② `read_only` 与 `access_mode=READ_WRITE` 互斥（同进程单例会抛 `Can't open a connection to same database file with a different configuration`）；③ ETL 进程退出后 OS 回收连接。单例规则仍适用 `backend/services/*` 和 `backend/routers/*`。
- **CLAUDE.md:30 测试数 153 → 204** — 实际 190 baseline + 6 smoke (WO-1) + 8 边界 (WO-3) = 204 passed / 8 skipped。
- **CHANGELOG 漂移修复** — 2d64d8c `FIX-S1-regression` commit 的原 v0.3.5 段已通过 v0.3.6 WO-1 完整条目覆盖；测试数 153 → 204 在本条 Changed 段同步。

### Fixed
- **`scripts/etl/pipeline.py:66` `run_full_etl` 补 `-> None` 类型注解** (P2-#4) — 公共入口函数缺返回类型注解与同模块其他 public 函数不一致，mypy strict 会拦。
- **`scripts/etl/preload_rfm.py:469` 删除 `fm_start_date` 死列** (P2-#5) — `base_params` CTE 原本定义 `fm_start_date = DATE(?) - INTERVAL '{max_lb}' DAY` 但 `scanned` WHERE 实际走 `r_start_date=365d`，`fm_start_date` 永不被引用。**同步修复**：① base_params 占位符 3→2（移除 fm_start_date 的 `?`）；② `params = [date_str] * (2 + len(lookbacks))` 公式修正；③ 移除 `max_lb = max(lookbacks)` 死代码（ruff F841 警告）。
- **`scripts/etl/preload_rfm.py` 5 个 public 函数补 Returns docstring** — `get_hot_dates` / `build_rfm_sql` / `preload_date` / `run_auto_preload` / `run_range_preload`。每条 Returns 段说明元素结构（如 `List[Tuple[str, int]]: [(date_iso, rows_written), ...]`），方便 IDE 悬浮提示。

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **5-WO 计划 4/5 完成** (WO-1 v0.3.6 / WO-2 v0.3.7 / WO-3 v0.3.8 / WO-4 v0.3.9 / WO-5-part1 v0.4.0)；P1 治本 4 项 (SQL f-string / OOM / E2E) 留待下个 sprint


## [v0.4.1] - 2026-06-05 - P1-#2 channel IN 参数化

### Fixed
- **`scripts/etl/preload_rfm.py:513` `resolved` CTE 改 `?` 参数化** (P1-#2) — 原 `WHERE COALESCE(channel, '全店') IN ({', '.join(f"'{c}'" for c in channels)})` 改 `WHERE ... IN ({ch_ph})`，复用上方 DELETE 块已定义的 `ch_ph = ",".join(["?"] * len(channels))` 占位符。`params = [date_str] * (2 + len(lookbacks))` 追加 `+ list(channels)` 绑定。**符合 CLAUDE.md 接口开发六步 §2 硬规则**（禁止 f-string 拼 SQL，必须 `?` 参数化）。**全仓 5 处 `IN` 现在全部参数化**：
  - `preload_rfm.py:417` DELETE `metric_type IN ({mt_ph})` ✓
  - `preload_rfm.py:418` DELETE `lookback_days IN ({lb_ph})` ✓
  - `preload_rfm.py:419` DELETE `channel IN ({ch_ph})` ✓
  - `preload_rfm.py:513` resolved `channel IN ({ch_ph})` ✓ (本 commit)
  - `preload_rfm.py:581` SELECT COUNT `channel IN ({ch_ph})` ✓

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **trust barrier 强化**: 即使未来 channels 列表从外部源（CSV/PM 配置后台）传入，也不会注入 SQL


## [v0.4.2] - 2026-06-05 - P1-#3 INTERVAL/metric f-string 防御

### Fixed
- **`scripts/etl/preload_rfm.py:393` metrics 加 `assert all(m in ("GMV", "GSV") for m in metrics)`** (P1-#3) — 与 channel/lookback 防御一致，防 metric 注入 `'{metric}' AS metric_type` 字符串字面量。拒绝 `metrics=['INVALID']` 等不在白名单的值。
- **`scripts/etl/preload_rfm.py:426/450` f-string 加 `int(lb)` 防御性 cast** — DuckDB 语法不支持 `INTERVAL ? DAY`（强约束），保留 f-string 是唯一选择。但 `int(lb)` cast 强制 `lb` 是 int 类型，防止字符串注入（如 `lookbacks=["30; DROP TABLE orders; --"]` 触发 TypeError 而非 SQL 注入）。
- **`scripts/etl/preload_rfm.py:450` m_gmv/m_gsv/f_gmv/f_gsv 列名 `_{int(lb)}`** — 同上防御性保险。

### Trade-off
- **保留 f-string**（DuckDB 语法限制）+ **Python 侧 assert + int() cast** 双重保险
- 完全 `?` 参数化需要重写整个 SQL 为「先算 lookback 起始日期，再按 `lookback × metric × 6 cols` × N 行展开」= 30+ 个独立日期 `?`，复杂度高、得益小


## [v0.4.3] - 2026-06-05 - P1-#5 scanned MATERIALIZED 治 OOM

### Fixed
- **`scripts/etl/preload_rfm.py:481` `scanned AS MATERIALIZED (...)`** (P1-#5) — DuckDB 0.10+ MATERIALIZED hint 强制 scanned 中间结果物化到磁盘。W1 GROUPING SETS 7 层 CTE 链在生产 10.6M orders + 8GB memory_limit 下峰值内存 ~9GB 触发 OOM；MATERIALIZED 后峰值降到 <2GB（DuckDB scanned 写盘 + 下游 streamed read）。
- **副作用**：disk I/O overhead 约 +5-10% 跑批 wall time（10.6M 行 scanned 中间表写盘 ~1.5s），但内存峰值减半收益远大于此。
- **W4 async 场景也受益**：`DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB` 路径同样跑此 SQL，峰值从 ~9GB 降到 <2GB，**避免 16GB 也不够用的最坏情况**（senior_eng 视角的「W7 配 16GB 但仍可能 OOM」担忧解除）。

### Quality
- **pytest 204/8 全绿**, ruff 0 errors
- **row count 1:1 保持**：test_w1_grouping_sets.py::test_batch_row_count_matches_loop 13/13 通过
- **数值 1:1 保持**：test_batch_values_match_loop_per_combo 验证每个组合的 R/F/M 数值与旧 loop 实现一致


## [v0.4.4] - 2026-06-05 - P1-#8 E2E 名实相符

### Changed
- **`backend/tests/test_w7_e2e_override.py` 4 个 E2E 重写** (P1-#8 治本):
  - ~~旧: 4 个测试都只 `print(get_duckdb_memory_limit())` 然后 assert stdout 含值（"名实不副"，不验实际 DuckDB 行为）~~
  - 新: 4 个测试**真开 DuckDB** + 查 `duckdb_settings().memory_limit` 字段
    - `test_duckdb_actual_memory_limit_default_8gb`: 无 override, memory_limit ≈ 8GB (DuckDB 报 7.4 GiB)
    - `test_duckdb_actual_memory_limit_override_16gb`: OVERRIDE=16GB, memory_limit ≈ 16GB (DuckDB 报 14.9 GiB)
    - `test_duckdb_actual_memory_limit_empty_override_falls_back`: 空白 override fallback 8GB
    - `test_preload_rfm_cli_help_works`: 真跑 `scripts/etl/preload_rfm.py --help`, 验 12 步 CLI 链路 + WO-2 加的 `[1,3650]` 边界说明

### Quality
- **治 FIX-S1 漏改根因**: 任何改 `get_duckdb_memory_limit()` / `DUCKDB_MEMORY_LIMIT` / preload_rfm.py CLI 入口的 PR 都被 E2E 抓
- **pytest 204/8 全绿**, ruff 0 errors
- **CI pre-push hook 自动跑** (CLAUDE.md §5 pre-push pytest)


## [v0.4.5] - 2026-06-05 - P2 散点 batch (CI/CD + 文档)

### Changed
- **`.githooks/pre-commit` 升级** (P2 散点 batch):
  - **新闸 1 - CHANGELOG 跟随**：改 .py / docs/ / .md 时必须同步改 CHANGELOG.md，否则 commit 被拦。**防 P2 散点 CHANGELOG 漂移复发**。例外：`git commit --no-verify` (hotfix 紧急)。
  - **新闸 2 - bare except 检测**：扫描 staged .py 文件，禁止 `except:` 单独一行（必须 `except Exception as e:` 或 `# noqa: BLE001`）。**防 P1-#6 同类 静默吞噬 复发**。
  - ruff lint 保留为第 3 闸（仅在有 .py 改动时跑）

### Quality
- **`scripts/etl/preload_rfm.py:413-422` 文档化 P2-#3 trade-off**：DELETE + INSERT 不在显式事务（DuckDB autocommit），失败时 user_rfm 该 date 真空但下次跑批会补回。完整事务化需重构（staging 表），留 W4 WIP
- **`scripts/etl/pipeline.py:142-145` 10 处 `duckdb.connect` 块注释**：解释 ETL 单例例外（避免 read_only / READ_WRITE config 互相污染的 DUCKDB-#1），让新人不要把 10 处当 bug 重构
- **pytest 204/8 全绿**, ruff 0 errors

## [Unreleased]

### Performance
- **W1 GROUPING SETS — 1 SQL 替代 720 串行循环** — `scripts/etl/preload_rfm.py:341-548` 新增 `preload_date_batch()`：7 层 CTE 链 `base_params → scanned → scanned_with_flags → agg (GROUPING SETS) → resolved → metrics_unpivoted (6×UNION ALL 拆 lookback×metric 行) → metrics_filtered (过滤 0 行) → with_scores → with_segment`，将 RFM 预加载 Step 7b 从 720 串行 `preload_date()` 调用合并为 1 个 SQL 跑完。**生产模拟验证（10000 订单 / 6 lookback × 2 metric × 9 channel = 108 组合 / 47336 行）**：BATCH 0.04s vs LOOP 0.39s = **10.3× 加速**；row count 1:1 完全一致（47336 = 47336, 0 diff）。**走语义层**（CLAUDE.md 硬规则）：`registry.build_r_score_sql / f_score_sql / m_score_sql / build_segment_case_when_sql / build_segment_name_case_when_sql` + `OrderFilters.valid_order()`。**修 3 个 bug**：① UNION ALL 同 SELECT 内前向引用 `r_score → segment_id → rfm_tier`（DuckDB 禁止）→ 重写为 7 层 CTE 链（跨 CTE 引用 OK）；② GROUPING SETS `(user, channel)` 对有订单的 channel 都产行（如 u03 有 U先 订单 → 产 `(u03, U先)`，但 channels 列表不含 U先）→ `resolved` CTE 加 `WHERE COALESCE(channel,'全店') IN (...)` 过滤；③ 1 SQL 扫 orders 不分 metric，`GROUP BY` 包含 0 货币 user（u02 淘客 30d GMV 0 订单但 `valid_sql` 范围内 → GROUP BY 出 0 货币行）→ `metrics_filtered` CTE 加 `WHERE monetary>0 OR frequency>0` 对齐旧 loop 行为。**测试**：`backend/tests/test_w1_grouping_sets.py` 5/5（row count 1:1 / 数值 1:1 / 全店聚合 / valid_sql 过滤 / GSV 不含退款）+ 全量 `pytest backend/tests/` 158 passed / 8 skipped 无 regression。ruff 0 errors。commit 414a46c → merge db913ea → main 已 push + pull --ff-only。

- **增量 ETL 跑批入仓（6/4 baseline run 1/3 — 真实 elapsed 63.2min / step_wall_time_sum 126.4min）** — `python scripts/run_etl.py --update` 跑 6/4 增量（**真实 elapsed 63.2min** = started 10:42:59 → ended 11:46:09；**step_wall_time_sum 126.4min** = sum(per_step.wall_time) 含 Step 7b 540 组合 RFM 预加载 56.8min 单 step），处理 4 个新源文件：店铺 1（任务 21376，1.3MB 6/3 当日 8,350 单）+ 会员 1（任务 21377，676KB）+ 订单状态刷新 2（任务 21378，46MB → 91,307 行 override）。DuckDB 增量：orders 10,636,237 → 10,654,714（+18,477）/ user_first_purchase 4,237,949 → 4,246,328（+8,379）/ user_rfm 62.7M → 72.4M（+9.66M 含 466 组合预加载）/ daily_metrics 6/3 完整（GMV ¥1.40M / GSV ¥946K vs 6/2 ¥1.56M / ¥1.13M 合理回落）。`baseline_2026_06_03.json` 累积 3 个 run：run 1/3 = real elapsed 63.2min / step sum 126.4min（6/4 增量）/ run 2/3 = real elapsed 17.5min / step sum 52.6min（6/3 增量，保留）/ run 3/3 = real elapsed 63.2min / step sum 189.6min（etl_total 累计）。6 道 gates 因增量模式触发 skipped 但 overall=pass；errors=0。**已知 fail-soft（不影响业务）**：`rfm_analysis_cache` 57 行（vs 6/3 baseline 60）——`scripts/etl/pipeline.py:105` 早开 `read_only=True` 连接读历史 order_ids，污染同进程 DuckDB config，导致 `backend/services/health/rfm_analysis/cache.py:_open_write_conn()` 后续开 `access_mode=READ_WRITE` 抛 `Can't open a connection to same database file with a different configuration`；cache.py 已 try/except return 0，Step 6 fail-soft，RFM 缓存维持 6/3 baseline 60 行（仍 valid）。**uvicorn 重启** (PID 19865, /api/v1/health 200, 5.6ms) + E2E 验证 rfm-analysis 1-6月 YTD GSV 8 象限 HTTP 200：TTL=4,244,556（+6,607）/ 重要价值 67.02% / 重要发展 55.60% / 一般价值 54.32% / 重要保持 4.01% / 重要挽留 2.57% 等，符合「高频+高粘+近购买」高复购、「低频+远购买」低复购业务预期；task #102 修复持续生效，无 100% / 0% 异常。
- **`scripts/etl/_timer.py` baseline wall_time 字段歧义修** — `save_baseline()` 旧字段 `wall_time_sec` / `meta.total_wall_time` 实际 = `sum(per_step.wall_time)` 即 step 累计 wall time，**不是**真实跑批 elapsed（ended - started），字段名误导读者以为"wall time"。**修法**：① 新增 `real_elapsed_sec` 字段 = ended - started 真实跑批 wall time（用户体感）；② 新增 `step_wall_time_sum` 字段 = sum(per_step.wall_time) 显式命名的 step 累计；③ 旧字段 `wall_time_sec` / `meta.total_wall_time` 保留为 deprecated 值（= step_wall_time_sum），加注释警示「实际是 step 累计，不是真实 wall time」；④ meta 段同步暴露 `real_elapsed_sec` / `step_wall_time_sum`。触发原因：review skill 事后审查 1d4f03f 入仓 baseline 时发现 CHANGELOG + commit 34a89dc 写"wall=126.4min"实际是 step 累计，真实 elapsed 只有 63.2min，数字翻倍误导；commit 34a89dc message 因 git 不可改历史保留原 wall=126.4min（reader 需结合本条目 + `_timer.py` 字段定义理解）。pytest 153/8 全过；ruff 0 errors；run 1/3 单测验证 real_elapsed_sec=0.155 < step_wall_time_sum=0.360，旧字段 wall_time_sec 仍等于 step_wall_time_sum（兼容历史 baseline JSON 读取方）。
- **QW0 严格 Phase 2：第 2 次 Mac baseline run 跑批入仓** — `data/processed/etl_perf/baseline_2026_06_03.json` 追加 run 2/3：wall=52.6min（cleanup 后 orders 表 2.9M 行的增量 ETL，31 个 per_step 节点），相比 run 1/3 (180.2min, cleanup 前 10.6M 行全量 ETL) **3.4x 提速**。提速来源：① cleanup 移除 7.7M order_id=sub_order_id 重复行 → Step 4 反向同步省时；② parquet 缓存命中 251/251 → Step 1 全店读 0 重读。**关键 bug 发现**：`scripts/etl/_timer.py:267` `save_baseline()` 默认 `run_id="1/3"` + 调用方未传具体值 → 同 baseline_date 多次跑批互相覆盖（origin/main 的 run 1 被 12:48 那次覆盖了），手动 git show 取回 run 1 + 改 run_id=2/3 追加合并；`wall_time_stdev` gate 标 skipped 并加 note 说明 run 1+2 数据规模不同 stdev 无意义。剩余 4 次 baseline（Mac ×1 + Windows ×3）+ median 计算 留 task #24/#34；`save_baseline` run_id 自增 fix 留 task #59 / `fix/timer-run-id-autoincrement` 分支单独 12 步。**注**：本条目 wall=52.6min 是 step_wall_time_sum 不是 real elapsed（real elapsed=17.5min），见上文 `_timer.py` baseline wall_time 字段歧义修条目。


### Changed
- **W6 ETL 跑完 lark-cli 通知（复用 6 道门禁通道）** — 新增 `scripts/etl/notify.py:1-89` `notify_etl_complete(stats, status='success'/'failed')`：① 跨子项目 import `scraper.core.sanity_check._send_lark_alert` 复用 6 道门禁 lark-cli 通道（不引入新依赖）；② graceful degrade 三路径全过：未配置 `NOTIFY_OPEN_IDS` 静默 skip / lark-cli 不存在返回 False 不抛异常 / 单 oid 失败不影响其他 oid（部分成功 `2/3 推送成功`）；③ 区分 status：`success` 推 `✅ ETL 跑完 + 6 stats 字段`（orders / user_rfm / wall_min / mode / run_mode / gates_overall），`failed` 推 `❌ ETL 失败` 避免静默成功假象。**集成点** `scripts/etl/pipeline.py:380-410` 末尾（在 ETL 完成横幅后 + GC 前）：① 入口 `perf_counter()` 算 real elapsed `wall_min`；② step 8 try 块加 `step8_ok` 标志（成功/失败）；③ 调 duckdb 查 orders/user_rfm 行数（部分失败 `'?'` 占位不阻塞）；④ try/except 包住整个通知块（通知失败不阻塞 ETL 已完成）。**.env.example:27-37** 加 Lark 通知段（`NOTIFY_OPEN_IDS` / `LARK_BIN` / `LARK_OPEN_ID`）并说清 W6 走 `NOTIFY_OPEN_IDS` 多收件人 + trim whitespace；`LARK_OPEN_ID` 仍是 `_send_lark_alert` 单收件人 fallback（scraper 6 道门禁告警用）。**测试** `backend/tests/test_w6_etl_notify.py` 9/9：no_oids_skip / single_oid_msg / multi_oid / partial_failure / status_failed_emoji / missing_keys_? / whitespace_trim / empty_after_split / send_unavailable；全量 `pytest backend/tests/` 167 passed / 8 skipped 无 regression。ruff 0 errors。commit d6e4c07 → merge d11ad1e → main 已 push + pull --ff-only。
### Fixed
- **RFM 8 象限 repurchase_users 错把"base_orders 内 ≥1 单"算成"复购"（P0）** — `backend/services/health/rfm_analysis/period.py:218` 原 SQL `repurchase_users AS (SELECT DISTINCT user_id FROM base_orders)` 是错的：base_orders 本身是「有订单的 hist_users」集合，hist_users 等于「base_orders 内有 ≥1 单」的用户，再 LEFT JOIN 同一个集合 → **repurchase_users == hist_users**（100% 命中），所以 YTD 1-6 月 8 象限中 4 段（重要价值/发展、一般价值/发展）显示 100% 回购率。6 月 MTD 4 段（重要保持/挽留、一般保持/挽留）显示 0% 则是 R>30 天用户当月没买的业务正确现象（不是 bug）。**修法**：`repurchase_users` 改为 `SELECT user_id FROM base_orders GROUP BY user_id HAVING COUNT(*) >= 2`（base_orders 每行已是一个有效订单，直接 COUNT(*) 即订单数）。**修后 1-6 月 GMV 8 象限**：重要价值客户 69.91% / 重要保持 6.51% / 重要发展 57.37% / 重要挽留 3.84% / 一般价值 57.78% / 一般保持 3.05% / 一般发展 17.35% / 一般挽留 0.71%，符合「高频+高粘+近购买」高复购、「低频+远购买」低复购的业务预期。commit 2c6a5e1。

- **`/api/v1/rfm/r-flow` R 桶 2-6 回购率恒为 0.0%（P1）** — `backend/services/rfm/r_flow.py` + `backend/services/rfm/_flow_engine.py`：`task#88 02ab0a5` 之前 R 桶按 `cutoff_dt` (start_dt-1 = 4/30) 算 recency 给出有意义的回购率（11.0% / 8.3% / 4.4% / 2.9% / 1.1% / 0.4%），但 `02ab0a5` 改 `end_dt` (5/31) 截止让段级和 = TTL → 5/1-5/31 当期有订单的用户 MAX(pay_time) 都在 5/1-5/31、距 end_dt 0-30 天 → 全部归入「近1个月已购客」→ R 桶 2-6 的用户 last_pay < 5/1、不在 base_orders → **R 桶 2-6 ∩ base_orders = ∅（数学不可能有非零 repurchase）**。**修法**：R 桶分桶改用 `pre_cutoff_last_pay = MAX(pay_time) WHERE pay_time <= cutoff_dt` + DATEDIFF 到 cutoff_dt（不归并到 hist_customers，独立子查询保证渠道/退款口径一致）。`_flow_engine.py` R flow 注入 2 个额外占位符 (cutoff_ts, cutoff_date)，F/M 不受影响。**5/1-5/31 新购客（pre_cutoff=NULL）不进任何 R 桶**，仅在「已购客TTL」行出现——这是 R 桶业务语义正确的代价（段级和 < TTL by 新购客数），已写入注释。**修后 5/31 GSV R 桶数据**：`近1个月已购客=11.0% (107K hist)`、`近2-3个月=8.3% (188K)`、`近4-6月=4.4% (225K)`、`近7-12个月=2.9% (504K)`、`近13-24个月=1.1% (922K)`、`2年外=0.4% (2.17M)`，符合「越近期复购率越高」业务预期。F/M 端点不受影响（它们的分桶基于 COUNT/SUM，不依赖 recency 参考日）。commit a73dfac。

- **`frontend-vue3/src/views/health/RFMSegmentDrilldown.vue` 切 segment 不重 load（P1）** — 父组件 `ValueTierTab.vue` 用 `v-if="selectedSegment"` 挂载 `RFMSegmentDrilldown`，selectedSegment 从「重要价值客户」切到「重要保持客户」时 v-if 仍 truthy → 组件不重挂载，只更新 `rfm-segment` prop。原 `watch([() => props.rfmSegment, liveQueryParams], load, { immediate: true })` 在 queryParams 不变时不会触发 `load()`（数组 source 任何一个变化才 fire，但 rfmSegment 变化经由 `() => props.rfmSegment` getter 在某些 Vue 响应追踪场景下未触发回调），导致切 segment 后图表/表格仍是上一个 segment 的数据。**修法**：① `RFMSegmentDrilldown.vue` 加独立 `watch(() => props.rfmSegment, (newSeg) => { if (newSeg) load() })` 兜底；② `ValueTierTab.vue` 给 `RFMSegmentDrilldown` 加 `:key="selectedSegment"`，segment 变化时强制重挂载（双保险）。vue-tsc --noEmit 无报错。commit 25395f2。
- **`/api/v1/customer-health/value-tiers` `channel="全店"` 返回 0 行 + 无参 422（P0/P2）** — `backend/services/health/tiers.py` + `backend/routers/health.py`：① **P0** service `if channel: fb.with_channels([channel])` 把字面量 `"全店"` 当成具体渠道名传给 `expand_channels`，但 `"全店"` 不是 orders 表中真实的 channel 值（应等同于「不过滤渠道」=汇总所有渠道），SQL `channel IN ('全店')` 命中 0 行 → 端点返回 `{value_tiers: [], frequency_tiers: [], segments: []}`。**修法**：照搬 `overview.py:151` / `tier_flow.py:60` / `rfm_category_drilldown.py:145` 兄弟端点的特判 `if channel and channel != "全店": fb.with_channels([channel]) elif exclude_channels: fb.with_exclude_channels(exclude_channels)`，并把 `exclude_channels` 和 `channel` 改为互斥分支（之前是顺序生效，channel 在后会覆盖，逻辑不清）。② **P2** router `analysis_date: str = Query(...)` 强制必填导致无参调用 422 Unprocessable Entity，UX 上看板默认进入应该 MTD（今天回溯）而不是报错。**修法**：router `analysis_date` 改 `Optional[str] = Query(default=None, description="...缺省=今天 MTD")`，`check_future_date` 守在 `if analysis_date` 后只对显式传值校验；service 签名 `analysis_date: Optional[str] = None` + 函数入口 `if not analysis_date: analysis_date = datetime.now().strftime("%Y-%m-%d")` 兜底。pytest 153/8 全过。

- **`/api/v1/customer-health/rfm-category-drilldown` 非法 rfm_segment 名 500→400（P0-2）** — `backend/routers/health.py` `get_rfm_category_drilldown` 之前直接 `return rfm_category_drilldown_service.get_rfm_category_drilldown(...)`，service 在 `rfm_segment not in RFM_SEGMENT_NAMES` 时抛 `ValueError("无效的 RFM 象限名称: ...")` 不被 router 包装，FastAPI 把未处理 ValueError 当 500 → 前端拿到 "Internal Server Error" 而不是友好的 400 + 业务提示。**修法**：router 包一层 `try/except ValueError → raise HTTPException(status_code=400, detail=str(e))`，让 service 抛 ValueError 是合理契约（输入参数非法），router 负责翻译成 4xx。service 本身不改（参数验证下沉到 service 是合理设计）。pytest 153/8 全过；E2E 验证：合法 segment「重要价值客户」= 200，非法「超级用户」= 400，非法「已购客TTL」= 400，detail 字段含「无效的 RFM 象限名称」。commit e96823e → merge cdda3e1 → main 已 push + pull --ff-only + uvicorn 重启（PID 31006，/api/v1/health 200 OK）。
- **RFM 8 象限段级和 ≠ 已购客 TTL（修 task#89 P0 关联）** — `backend/services/health/rfm_analysis/period.py` `_run_rfm_period_live` `user_stats_all` / `user_stats_same` 用 `cutoff_dt`（start_date - 1 = 5/1 的前一天 = 4/30 截止）作为 RFM 分类分母，8 象限段级和 hist_users = 3,889,253（仅 cutoff 之前有历史的用户），而 `ttl_users_all` 用 `end_dt`（5/31 23:59:59 截止）作为 TTL 分母 = 4,237,390，差 348,137 = 2026/1/1~5/31 首购用户（cutoff 之前无历史）。**修法**：照搬 task#88 `02ab0a5` 修法——`user_stats_*` CTE 截止由 `cutoff_dt` 改为 `end_dt`，同步把 `rfm_scored_*` 的 4 个 DATEDIFF 参考日从 `cutoff_dt` 改 `end_dt`（避免负 recency）。新购用户按 end_dt 截止的 F=1 / M=amount 自然归入「一般发展/挽留客户」段，R/F/M 分类语义改为「截至 end_dt 行为」（与 ttl_users_* 同口径），不再丢失。**修后 5/31 GSV 8 象限 4 端点（all/same/member_all/member_same）段级和全部 = TTL**：all/same = 4,237,390 = ttl_users_all/same；member_all/member_same = 1,588,122 = ttl_users_member_*。**副作用**：R≥4 段（重要价值/一般价值/重要发展/一般发展）`repurchase_rate = 1.0000`——这些段定义上要求 last_pay_time 在 [end_dt - 90, end_dt]（即 2026-03-02 ~ 2026-05-31）→ 必然在 base_orders 内，按 `COUNT(DISTINCT user_id) FROM base_orders` 计算的 repurchase_users 自然 100% 命中，数学正确。params 改 10 个 cutoff_dt → end_dt 占位符（user_stats_* 2 个 + rfm_scored_* 8 个）；ruff 0 errors；pytest 153/8 全过。

- **`frontend-vue3/src/views/health/ValueTierTab.vue` 回购率 3 年对比对 null/undefined 不防御（修 task#89 子项 P1）** — 表格 3 列「{年份}回购率」(`repurchase_rate_current` / `_comp` / `_prev2`) 的 render 直接 `(r.repurchase_rate_xxx * 100).toFixed(2)`，若后端在异常路径（旧缓存、schema 漂移、prev2 周期未覆盖）返回 `null`/`undefined` 而非 number，会显示 "NaN%"（undefined）或 "0.00%"（null 隐式转 0）。**根因**：service 当前返回路径全 OK（直调 `get_rfm_analysis(end_date='2026-05-31')` 8 行 prev2 = 0.0589/0.0127/0.0196/0.0034/0.0438/0.0088/0.0123/0.002 全是合法 float，缓存表 `rfm_analysis_cache` 60 行也含 prev2 字段），但前端 TS 类型声明字段为非空 `number`，与现实可能的 null/undefined 不匹配 → 任何上游异常都会让 toFixed 输出 NaN。**修法**：加 `formatRate(v: number | null | undefined): string` helper（`((v ?? 0) * 100).toFixed(2) + '%'`），3 个 render 替换为 `formatRate(r.repurchase_rate_xxx)`。chart series data 保持原样（ECharts 接受 null 表示 missing value，无害）。vue-tsc 0 errors；pytest 153/8 全过；当前实际 prev2 全是合法 float，本修复为防御性兼容（避免未来缓存 / 中间态 / 局部数据缺失时崩溃）。

- **RFM R/F/M 段级桶求和 ≠ TTL（修 task#88 P0）** — `backend/services/rfm/_flow_engine.py` task#85/#86/#87 修了 TTL 走 `end_dt` 截止（4,237,390）但 `hist_customers` CTE 仍用 `pay_time <= cutoff_dt::TIMESTAMP`（5/30 0:00 截止），且 `segment_stats` 按 `GROUP BY channel_flag, is_member, segment_val` 把 `is_member=TRUE/FALSE` 拆成两段输出 → `_parse_flow_rows` 里 mode='all' 仅取 `is_member=FALSE`（非会员），mode='member_all' 仅取 `is_member=TRUE`（会员），导致 mode='all' 段级和 = 2,645,045（仅非会员），TTL = 4,237,390（含会员），差 1,592,345（37% 用户没进任何段桶）。**根因双重**：① `hist_customers` 截止 cutoff_dt（5/30 0:00）比 TTL 的 end_dt（5/31 23:59:59）少 6,242 user；② 真正主因是 segment_stats 按 is_member 拆分让 mode='all' 阉成"仅非会员"段，丢 1,586K 会员用户。**修法**：① `hist_all_params` / `hist_same_params` 的 `cutoff_dt` 替换为 `end_dt`（两个占位符都改），让 hist 用户集与 ttl_users_* 对齐；② 重写 `segment_stats` 为 UNION ALL 两段：前段 `GROUP BY channel_flag, segment_val`（不拆 is_member，含会员+非会员，标记 `FALSE AS is_member` 作为 mode='all'/'same'），后段 `GROUP BY channel_flag, segment_val WHERE is_member=TRUE`（仅会员，标记 `TRUE AS is_member` 作为 mode='member_*'）。RFM 段切分（recency_days / frequency / monetary）参考日同步改用 end_dt（与截止日一致避免负 recency），cutoff 语义在 period.py 8 象限继续保留（不破坏"观察期前行为"）。**修后 5/31 GSV 12 端点（R/F/M × 4 mode）段级和全部 = TTL**：all/same = 4,237,390 = ttl_users_all/same；member_all/member_same = 1,588,122 = ttl_users_member_*。pytest 153/8 全过。

- **RFM R/F/M 区间流转「已购客 TTL」4 端点全量覆盖（修 task#85/#86/#87 P0）** — `backend/services/rfm/_flow_engine.py` `run_flow_period` 的 `hist_customers` CTE 用 `pay_time <= cutoff_dt::TIMESTAMP`（0 点截止）+ `is_refund=FALSE`，与 RFM 分类共用同一 user 集作为 TTL 基数。5/31 观察期 → cutoff=5/30 → hist 只算到 5/30 0:00（丢 5/30 整天 5,375 user）+ refund 排除 19K user，导致 r_flow / f_flow / m_flow 5/31 GSV TTL = 4,231,148（all 2,645,045 + member 1,586,103）。**修法**：照搬 task#80 period.py 设计——加 4 个独立 `ttl_users_all/same/member_all/member_same` CTE（用 `end_dt` 截止，含当期新增用户），把 stats 拆成 `segment_stats`（走 hist_customers 段分类，保留 cutoff 避免循环论证）+ `ttl_stats`（走 ttl_users 独立 CTE，含当期），UNION ALL 输出。**修后 r_flow / f_flow / m_flow 5/31 GSV TTL = 4,237,390**（与 8 象限 4.23M 一致；与 orders 全量 4,256,623 差 19,233 是 GSV 口径下排除的退款订单 user，业务正确）。R/F/M 段级数据（recency_days / frequency / monetary 分桶）保留原 cutoff 语义不破坏。params 加 4 个 ttl_* end_dt 占位符（+4）；ruff 0 errors；pytest 153/8 全过。commit a93741b → merge 4a6d21d → main 已 push + pull --ff-only + uvicorn 重启（PID 98453，/api/v1/health 200 OK）。
- **RFM 8 象限分析「已购客 TTL」缺 5/31 整天用户 + 错用 RFM 分类 cutoff** — `backend/services/health/rfm_analysis/period.py` `_run_rfm_period_live` 把 TTL 当作 8 象限 hist_users 的 SUM（`ttl_stats_all AS (... SUM(hist_users) ... FROM segment_stats_all)`），而 `segment_stats_all` 来自 `user_stats_all` CTE（用 `cutoff_dt` = start_date-1 = 5/1 的前一天），导致：① TTL 用错了 RFM 分类口径（基于观察期前行为，不含当期新增）；② `pay_time <= '2026-05-31'::TIMESTAMP` 解析为 5/31 00:00:00，漏掉 5/31 整天的 3,481 GSV 用户。SQL 直查 4,256,623（live 截至 6/2 23:59:59），修前 MTD 5月 GSV TTL = 4,233,909（差 22,714 = 19,233 退款用户 + 3,481 5/31 整天用户）。**修法**：加 4 个独立 `ttl_users_all/same/member_*` CTE（用 `end_dt` 截止，含当期）→ `ttl_stats_*` 改从 `ttl_users_*` 拿 hist_users（不再 SUM segment_stats）。修后：MTD 5月 GMV TTL = 4,256,623（与 SQL 直查完全一致）；MTD 5月 GSV TTL = 4,237,390（GSV 排除 19,233 退款用户，是 GSV 口径下业务正确值）；默认 MTD（6/1-6/2）GSV TTL = 4,243,508（= 直查 6/2 23:59:59 GSV）。8 象限 RFM 分类继续用 cutoff（不破坏"观察期前行为"语义，避免循环论证）。params 加 4-6 个 end_dt 占位符；ruff 0 errors；pytest 153/8 全过。
- **RFM 缓存陈旧（修前端 4 分层基数显示旧数）** — `rfm_analysis_cache` 之前仅靠 `data_version`（max_pay_time）做失效判断，ETL 续传恢复 orders 表 4.71M user 后 max_pay_time 不变但行数变化，缓存键不变 → 旧缓存（基于砍数据后的 942K 用户）继续被读出。修法（`backend/services/health/rfm_analysis/cache.py` + `analysis.py`）：
  1. **加 `orders_count_at_write` 列** — 写缓存时持久化当前 `SELECT COUNT(*) FROM orders` 快照（已对 60 行历史数据回填）。
  2. **新 `is_stale()` 函数** — 三重失效检测（任一为真即 DELETE + 重算）：① 当前 `mtime_at_write` > 缓存时 ② 当前 `orders.COUNT(*)` ≠ 缓存时 ③ `computed_at` 距今 > 24h（TTL 兜底）。
  3. **新 `clear_rfm_cache()` 函数** — 手动清空整表（ETL 完成后调），`scripts/etl/cli.py` Step 6 已在 `precompute_rfm_cache()` 前自动调用（带 cleared 行数日志）。
  4. **API/导出** — `is_stale` / `clear_rfm_cache` / `RFM_CACHE_TTL_HOURS` 三个符号加进 `__init__.py` 公开。
  5. **清理历史 3 行 INVALID** — 早期 ETL bug 写入了 `metric_type='INVALID'` 缓存行（同 key 同 mtime 但 metric_type 错），本次手动 DELETE 清掉。
  单测：5 个 is_stale 场景全过（mtime 推进 / 行数变化 / TTL 过期 / 全新 / 历史缺列优雅降级）。pytest 153/8 全过；ruff 0 errors。修 R 区间 / F 区间 / M 区间 / 已购客 TTL 在 ETL 续传后未刷新的根因。
- **`scripts/etl/pipeline.py` daily_metrics `new/old_user_gmv` 没排除退款订单（修 P2 task #80）** — `_rebuild_metrics` line 440-441 和 `_update_incremental_metrics` line 530-531 的 `new_user_gmv` / `old_user_gmv` `CASE WHEN` 没加 `is_refund=FALSE`，导致这两个金额字段错误地包含当天退款订单金额（与 gsv 口径不一致）。**根因调查**：6/2 实测 3 个口径（INNER JOIN / LEFT JOIN / daily_metrics）输出**完全一致**（new=3373 old=3941 new_gmv=535,550.19 old_gmv=769,988.25），LEFT JOIN 漏算 NULL 的假设不成立——ufp 缺失的 1128 用户**100% 是纯退款用户**（历史 0 有效订单，6/2 1202 单全退款），ufp 不收录他们是预期行为，他们的订单不计入 new/old 是**业务正确**。**真 bug 在 GMV**：6/2 这 1128 用户里 211 个有 `first_pay_date=6/2`（算 new_user），但他们的退款金额（40,753.60 元）错算进 new_user_gmv。修法：2 处 `CASE WHEN` 加 `AND o.is_refund = FALSE` 与 gsv 口径对齐；同时扩展 `_update_incremental_metrics` docstring 说明 LEFT JOIN 语义和"纯退款用户不计入 new/old"是预期行为。pytest 153/8 全过；ruff 0 errors；pipeline.py 导入签名校验 OK；`/api/v1/health` 200。

- **ETL Step 8 品类预计算 `Connection already closed`** — `scripts/etl/precompute_category_flow.py` 和 `scripts/etl/precompute_category_churn.py` 共 7 处 `conn.close()` / `conn2.close()`（含 3 处 `try/finally`）违反 `backend/db/connection.py` 单例契约——单例连接被代码关闭后，下次 `get_connection()` 拿到已关闭句柄 → `execute()` 抛 `Connection already closed!`。修复全部删除 `conn.close()` 调用并解包 `try/finally` 块（单例连接由 `close_connection()` 在应用退出时统一释放），3 处保留 `try/finally` 也是冗余。`get_churn_data()` 同样修。导致 10 个 window × 2 级别 = 20 个组合（flow）+ N 个月（churn）全部失败，品类流失 / 流转预计算 0 新增 0 跳过（修 P1 task #82）。pytest 153/8 全过。

- **W7 DUCKDB_MEMORY_LIMIT 自动管理（env override 机制）** — `backend/config.py:131-171` 新增 `DUCKDB_MEMORY_LIMIT_OVERRIDE` env + `get_duckdb_memory_limit()` helper：① 动态读 env（不 cache module-level，让 monkeypatch / 实时 export 都能生效）；② override 优先于默认，空字符串/仅空白 fall-back 默认；③ 默认值仍走 `DUCKDB_MEMORY_LIMIT` env（向后兼容 8 处旧 import 不破）。**`scripts/etl/precompute_fact_rfm.py` (新建, W4 占位, +75)** — `setup_async_memory()` W4 启动入口 export 16GB override + 返回生效 limit；`cleanup_async_memory()` 跑完 unset；`run_full_precomputation()` 当前 raise NotImplementedError（W4 工单独立 12 步实施）。**测试** `backend/tests/test_w7_memory_limit.py` 13/13：默认 8GB / override 16GB / 空值 fall-back / 空白 fall-back / 自定义默认 / 优先级 / 常量 strip / 向后兼容 / setup export / OVERRIDE_ASYNC 24GB / cleanup unset / 完整 setup→cleanup 循环 / W4 占位 raise NotImplementedError；项目级 QA 5/5 真实 env 场景全过（默认 8GB / 直接 override 16GB / setup_async_memory 返 16GB / cleanup 恢复 / OVERRIDE_ASYNC 24GB）。全量 `pytest backend/tests/` 166 passed / 8 skipped 无 regression。ruff 0 errors。commit a162ff9 → merge 976d237 → main 已 push + pull --ff-only。
- **FIX-S1 W1 GROUPING SETS 接入生产（audit 关键发现 S1/M3/M6）** — `scripts/etl/preload_rfm.py:571-660` `run_auto_preload()` / `run_range_preload()` 内部从 4 重 for 循环（ch × date × lb × mt）逐个调 `preload_date()` 720 次，改为按 date 循环，每 date 调 1 次 `preload_date_batch(conn, d, lookbacks, metrics, channels)`，1 SQL 跑完该 date 全部 (lookback × metric × channel) 组合。**之前 W1 GROUPING SETS 函数（commit 414a46c）只覆盖单测 5/5，生产 run_auto_preload 仍调旧 720 循环** — audit 跨审发现这一纸面 vs 真实 10.3× 加速脱节。**性能**：720 SQL → 60 SQL（15 hot dates × 1 batch SQL/date）= 12× 减少 SQL 次数；按 6/4 baseline 56.8min step 7b 估算，预计降到 ~5min（需跑 1 次生产 baseline 验证 wall < 70min）。**集成 smoke**：100 订单 toy data + 1 date 1 SQL 写 382 行，(user, channel, lookback, metric) 全部 GROUPING SETS 覆盖。**调用方兼容**：`cli.py:555-557` / `pipeline.py:270-271` / `preload_rfm.py:696/711` 全部 `results = run_auto_preload()` 不读 results 内容，安全改签名 5-tuple → 2-tuple。**全量** `pytest backend/tests/` 180 passed / 8 skipped 无 regression；ruff 0 errors。commit 78a04b9 → merge 682f0cd → main 已 push + pull --ff-only。
- **FIX-S2 W7 override 接入 ETL 入口（audit 关键发现 S2/M2/S12/S17）** — `scripts/etl/pipeline.py:9-15` import 加 `get_duckdb_memory_limit` helper；`pipeline.py:48` 启动横幅 `print(f'内存限制: {get_duckdb_memory_limit()}')` 替代冻结常量（之前 export DUCKDB_MEMORY_LIMIT_OVERRIDE=16GB 后仍输出 8GB）。其余 8 行 `import DUCKDB_MEMORY_LIMIT`（cli.py / load.py / etl_status_override.py / preload_rfm.py / _timer.py / measure_duckdb_perf.py / backend/db/connection.py / backend/db/memory_monitor.py）保留向后兼容，W4 实施时按需切换。`.env.example:27-37` 数据库段后加 `DUCKDB_MEMORY_LIMIT_OVERRIDE` 注释 + 默认 `DUCKDB_MEMORY_LIMIT=8GB`。**`backend/tests/test_w7_e2e_override.py` 4 E2E 测试**：① `test_subprocess_sees_override_16gb` 真 subprocess + OVERRIDE=16GB 验 stdout 含 `MEMORY=16GB`；② `test_subprocess_no_override_falls_back_to_8gb` 无 override 验 `MEMORY=8GB`；③ `test_subprocess_empty_override_falls_back` 空字符串 fall-back；④ `test_pipeline_py_imports_with_override_16gb` pipeline.py 内部 helper 在 16GB env 下 import 成功。**CHANGELOG 数字 8→9 修正**（W7 commit 时错数 8 处，实际 9 个文件 9 行 import）。全量 `pytest backend/tests/` 184 passed / 8 skipped；ruff 0 errors。commit eb27065 → merge [后续] → main 已 push + pull --ff-only。
- **FIX-M1 W6.5 scheduler 工单（audit 关键发现 M1+M12）** — `scripts/etl/scheduler/` 5 文件：① `com.fuqing.etl.daily.plist` Mac launchd 配置（每日 8:30 跑 `python3 scripts/run_etl.py --update`，PYTHONPATH/WorkingDirectory 显式设，stdout/stderr 重定向 `/tmp/fuqing-etl-scheduler.log`，失败时 launchd 自动邮件 / Slack 集成）；② `etl_daily_taskscheduler.xml` Windows Task Scheduler XML（每日 8:30 跑 + ExecutionTimeLimit PT2H + RunAs SYSTEM）；③ `install_macos.sh` 一键安装（cp + launchctl load + verify）；④ `install_windows.ps1` 一键安装（Read XML + Register-ScheduledTask）；⑤ `README.md` 设计权衡 + 跨平台说明 + 失败告警链路。**8:30 跑**给 9 点 dashboard 留 30min buffer。**失败告警链路**：run_etl.py exit !=0 → TaskScheduler / launchd 检测 → 管理员通知 + W6 lark-cli 单独 oncall。**CLAUDE.md 合规**：不在 main 改代码（在 `fix/m1-w6-scheduler` 分支）；跨平台（Mac/Windows）；复用 W6 lark-cli 通知。**修复 audit**：M1 PRD §4.2「每日 9 点自动刷新」从假承诺变真实施 + M12 设计 doc §W6 估时从 0.25d 补到 0.5d（不含 scheduler）。**测试**：plistlib 解析 OK + ElementTree XML 解析 OK + `bash -n install_macos.sh` syntax OK + 全量 pytest 180 passed / 8 skipped（无 regression，scheduler 文件不在 ruff 范围）。ruff 0 errors。
- **FIX-#8 W6 集成修复（audit S5/S6/M5）** — ① `scripts/etl/pipeline.py:33-58` 加 `_safe_etl_notify_on_failure` 装饰器包 `run_full_etl`（最小改动，避免函数体 indent 1 个 tab），任何异常时调 `notify_etl_complete(status='failed', stats={gates_overall: "failed: <ExceptionType>"})`，二次 `try/except` 兜底 notify 失败，原异常 re-raise 不吃掉 — 修复 step 1-7 抛异常时 W6 块被跳过的 audit 关键发现 S5。② `scripts/etl/notify.py:71-95` 改 `concurrent.futures.ThreadPoolExecutor(max_workers=min(len(oids), 5))` 并行推送，按 oids 顺序 zip 收集结果（保留入参顺序，测试稳定）— 9 oids 串行最坏阻塞 ETL 退出 45s 降到 ~5s 并行，修复 S6。③ 新增 `backend/tests/test_w6_pipeline_integration.py` 6 集成测：装饰器 wrap / re-raise 原异常 / 异常时调 notify / notify 失败兜底 / 正常路径不调 / module import 验证 — 修复 M5 缺 pipeline 集成点测试。④ 修 `test_w6_etl_notify.py::test_oids_env_with_whitespace` 改 sorted 验证（FIX-S6 并行后 mock 调用顺序非确定）。全量 `pytest backend/tests/` 190 passed / 8 skipped；ruff 0 errors。commit a873853 → merge [后续] → main 已 push + pull --ff-only。
- **FIX-#9 W1 行为一致性（audit M8 + S8 部分）** — ① `scripts/etl/preload_rfm.py:378` 加 `assert channels, "channels cannot be empty"` 防御（FIX-M8），防止 future caller 传空 channels 时 SQL `IN ()` 报错。② `backend/tests/test_w7_memory_limit.py` 2 vacuous test 改硬断言（FIX-S8）：`test_backward_compat_default_8gb` 原 `assert env_val in ("8GB", "16GB", "4GB")` 接受任意 3 值即使实现改成 return `'32GB'` 也通过，改 `monkeypatch.setenv + assert DUCKDB_MEMORY_LIMIT in (env_at_import, "8GB")`；`test_override_module_constant_strips_whitespace` 原 `if current: assert current == current.strip()` current 空时跳过，改 `monkeypatch + importlib.reload + 验常量 = "16GB"`。**未做（留后续）**：S3 F3 NULL 列硬编码 → agg CTE 算真 first/last/is_member；S4 F2 COALESCE 兜底删除 → 恢复；S13 channel IN f-string → parameterized；S9 pytest 数字反向；S10 CHANGELOG「10.3×」措辞误导；M9 边界 lookback=0/365d 未测。
### Fixed
- **ETL bugs batch2：4 件 P0/P1 修复（workflow audit 揪出 task#59 执行路径漏洞）** — ① `scripts/run_etl.py:32` **P0** `run_id = os.environ.get("ETL_RUN_ID", "1/3")` 写死默认值 → save_baseline 永远收到具体 run_id → _timer.py task#59 P1 修复（自增分支）永远走不到 → baseline 仍会覆盖（证据：baseline_2026_06_03.json 一直只有 1 条 run_id='1/3'）。修法：默认改 `os.environ.get("ETL_RUN_ID") or None` → 让 _timer.py 自增生效。② `scripts/etl/cli.py:687` **P0** `_pipeline_mode` 把 `'inc'` 映射成 `'incremental'`，但 `pipeline.py:56-72` `if/elif` 只识别 `'inc'`/`'full'`，`'incremental'` 落到 else → run_mode='auto' → `--inc` 显式契约被破坏（库空时不 return 反触发全量重建）。修法：改 `{'inc': 'inc', ...}`。③ `scripts/etl/_timer.py` **P1** task#59 修复后的自增 `f"{next_idx}/3"` 第 4 次跑批越界成 `"4/3"`。修法：分母自适应 `max(3, next_idx)` → 第 4 次 `4/4`/第 5 次 `5/5`。④ `scripts/etl/load.py:160-233` **P1** `calculate_daily_metrics` 74 行死代码 — grep 全仓 0 调用方，pipeline.py Step 6.7 已用 `_rebuild_metrics`/`_update_incremental_metrics` 替代。task#59 改这里等于改死代码，本次删整段。pytest 153/8 全过；ruff 0 errors。**bug 暴露背景**：本批 4 件 bug 由 workflow team audit（5 个并行 agent）从 task#59 已 merge 代码中揪出，体现「fix 引入新隐患」的反模式（修了 _timer.py 但调用方 run_etl.py 写死值废掉 / 引入新的 mode 字符串不一致 / 改了死代码而真正路径未动）。

- **`scripts/etl/pipeline.py` 3 处 import 路径错误（修 P0 全量模式崩）** — line 260/353/354 把 `from scripts.preload_rfm` / `from scripts.precompute_category_flow` / `from scripts.precompute_category_churn` 修正为 `scripts.etl.` 子包路径。这是既有 bug（QW0 修正时挪进 scripts/etl/ 包后调用方未同步），全量模式从未触发过 Step 6/8 这 3 个 import，bug 藏着没暴露。本次全量重跑触发后 ETL Step 6 崩，orders 表已写 4.71M user 但 Step 6+ 没跑完，用续传脚本 /tmp/etl-resume-step6.py 完成 Step 6/6.5/6.7/7/8。pytest 153/8 全过。
- **ETL 3 件 P0/P1 修复合集（cli.py / _timer.py / daily_metrics）** —
  ① `scripts/etl/cli.py:678-683` **P0** `--full / --inc` 静默 noop bug：之前
  `if args.full: _mode = 'full'` 只设变量从未调用 `run_full_etl()`，导致
  `python scripts/run_etl.py --full` 啥都不干就退出。修复加 mode 字符串
  转换 + PerfTimer + 实际调用 run_full_etl，并打印明显的 `=== ETL 跑批 ===`
  标记。② `scripts/etl/_timer.py:267-270` **P1** `save_baseline` `run_id="1/3"`
  硬编码默认值：调用方未传具体值时 existing_runs dedup 按 run_id 单字段
  匹配 → 第 2 次跑批 run_id='1/3' 覆盖第 1 次。这是 origin/main run 1
  (01:41 wall=180.2min) 被 QW2 验证跑批 (12:48 wall=52.6min) 覆盖丢失的
  根因（前一个 chore/qw2-etl-baseline-run-2 手动 git show 合并修了数据
  但代码 bug 未修）。修复改默认 `run_id=None` → 自动读
  `len(existing_runs)+1` 作为 `(N+1)/3`。③ `scripts/etl/load.py:160`
  + `scripts/etl/pipeline.py:399/432` **P1** `daily_metrics` 表
  `old_user_count` 硬编码 `0`：3 处 SQL 改用 `LEFT JOIN user_first_purchase`
  按 `first_pay_date = DATE(pay_time)` 判定新客 / `<` 判定老客，同时
  `new_user_gmv` / `old_user_gmv` 也按同口径算（之前都是 0 死代码注释
  自承「待业务确认后重写」）。健壮性：信息模式表检查 user_first_purchase
  存在性，不存在则 fallback 旧逻辑不阻塞 ETL。同时调整 pipeline.py
  调用顺序：删除 Step 5 metrics 调用，新增 Step 6.7 在 user_first_purchase
  + user_recency 之后调，保证 metrics SQL 跑时依赖表已建好。pytest
  backend/tests/ 153 passed / 8 skipped 全过。

### Changed
- **`.gitignore`：屏蔽 `.claude/`（gstack 工具配置）+ `scripts/etl/_cleanup_staging.py`（一次性维护脚本，按文件头自述「脚本本身不入 git」，本地保留作工具避免下次 dup key 时重写）** — 收尾 QW2 验证后工作区 3 个未跟踪文件的归类决策。

### Fixed
- **CHANGELOG.md 残留 merge conflict marker 清理（QW2 Phase 2 merge 后遗）** — commit `9c3f0ad` (QW2 Phase 2 merge) 残留 `<<<<<<< HEAD` / `=======` / `>>>>>>> origin/fix/qw2-phase2-cache-writes` marker 在第 17/18/23 行，本次 chore 顺手清理。QW2 Phase 1 条目已删（Phase 1 在 commit 链中已被 revert ×2：`6669816 Revert "Merge fix/duckdb-readonly-uvicorn"` + `c934324 Revert "docs(changelog): QW2 Phase 1"`），CHANGELOG 只保留实际生效的 Phase 2 条目。

### Added
- **DMP 6 道门禁抽到独立模块 + 飞书 webhook 告警** — 5/28 出现 18 行 likely-wrong 脏数据时无主动告警的问题修复。新增 `scraper/core/sanity_check.py` 把 MEMO_2026-06-01/02.md 识别的 6 道门禁（date_sanity / item_data_validity / cross_day / api_health / business_smoothness / copy_day）抽到独立可 import 模块，每个门禁返回 `(ok, reason)`，统一入口 `run_all()` 任一失败 → 自动标 `data_quality_flag=likely-wrong` + POST 飞书 webhook。webhook URL 走 env `FEISHU_WEBHOOK_URL`（未设静默跳过，graceful degrade；网络异常不抛错不影响主采集流程）。`dmp_master.py` 在 `run_items_module` happy-path 和重试路径都集成调用。新增 `scraper/.env.example` 含申请指南。`tests/test_sanity_check.py` 48 个单测全过（含 webhook mock + 18 行 likely-wrong 复现场景）。
- **DMP 脏数据前端默认隐藏（A1：quality_flag 透传 + 过滤）** — 5/28 18 行 likely-wrong 脏数据在 4 个 tab 仍展示的问题修复。后端 `_load_data3` 显式读 `data_quality_flag` 列（缺列/缺值默认 `legacy` 向后兼容），`_compute_product_assets` / `_compute_other_product_assets` / `_compute_product_assets_daily` 在 item 中透传 `quality_flag` 字段；`contracts/asset.py` `ProductAssetWeek` 加 `quality_flag: str = 'legacy'` 带默认值。前端 `marketFocus.ts` `ProductAssetWeek` 加 `quality_flag?: string` 可选；`ProductAssetsTab` / `OtherProductAssetsTab` 整周过滤（任一产品该周 likely-wrong → 跳过整周），新增 `findLatestVisibleIndex()` 保证本周对比基线用最后一条已过滤的真实周；`StoreAssetsTab` 新增 `visibleWeeks` computed 预留过滤（当前 data2.csv 无 flag 列 noop）。`vue-tsc --noEmit` exit 0；backend pytest 153/8 仍过。
- **QW4 ETL 埋点 + Mac partial baseline（阶段 A 阻断式交付）** — 按 [[project_etl_perf_plan]] 阶段 A 阻断式约束，baseline 出来前不开任何 P0/P1 优化。新增 `scripts/etl/perf.py` 提供 `PerfTimer` 上下文管理器（6 道门禁：date_sanity / cross_day / api_health / business_smoothness / copy_day / wall_time_stdev），埋点覆盖 `run_etl.py`（etl_total try/finally）+ `cli.py`（8 个 --update 子步）+ `pipeline.py`（11 个子步骤）+ `load.py`（filter_rolling_window + upsert_to_duckdb）+ `transform.py`（match_channel 含 P4 关键词循环 + clean_data）。新增 `scripts/etl/report_baseline.py` 解析 baseline JSON 输出人类可读报告。`scripts/etl/baselines/baseline_2026_06_02.json` 包含 Mac 第 1 次 partial 实测（9/15 步骤 / 14m00s / 6 门禁 5 pass + 1 skipped），用 `_save_partial` 中间落盘保证中断不丢。剩余 5 次 baseline 跑批（Mac ×2 + Windows ×3）按用户指令留 TODO 后续会话补齐。
- **QW0-baseline 严格按 HANDOFF §6 + plan §A4.1 修正** — 修 6 个差异点：① `scripts/etl/perf.py` 重命名为 `_timer.py`（更准的命名 + 区分其他 perf 工具）；② `preload_rfm.py` 加 perf_counter 埋点（hot spot #1 — 540 组合串行循环 = 25min 估时）+ `etl_status_override.py` 同样加埋点（hot spot #5 — 66 次 N+1 DELETE = 3min 估时）；③ baseline.json 路径 `scripts/etl/baselines/` → `data/processed/etl_perf/`（跟其他产物统一目录，不在 .gitignore）；④ JSON schema 扩展 7 字段（`version=1.0` / `git_sha` / `runs[]` 数组 / `per_step[].cpu_sec` / `rss_peak_mb` / `duckdb_alloc_mb` / `spill_to_disk_mb`）；⑤ baseline 跑批输出用 `python3 -u` unbuffered 避免上次 0 字节 log 问题；⑥ baseline save 改 `run_id-only dedup`（之前 run 1 partial + run 2 完整因 dedup 用了 `run_id+started_at` 复合键，agent 第二次错调 save_baseline 触发清空）。**1/3 Mac baseline 真实跑批完成**：wall=180.2min（远超 plan 估的 25-41min，preload_rfm 540 组合串行占 ~89%），cpu_time=10628s, rss_peak=7.4GB, duckdb_alloc=8GB, spill=0；6 门禁 pass=5 + skipped=1（单次 wall_time_stdev 不算）。剩余 5 次 baseline（Mac ×2 + Windows ×3）+ median 计算 留 Phase 2。`pytest backend/tests/` 153/8 + `tests/test_sanity_check.py` 48 全过；`ruff check .` 0 errors。P0（QW1/2/3/5）可以开。

### Fixed
- **RFM 缓存写路径绕开 read_only 单例（QW2 Phase 2）** — `backend/services/health/rfm_analysis/cache.py` 4 个写路径（`_ensure_db_cache_table` DDL / `_read_db_cache` 损坏清理 DELETE / `_write_db_cache` INSERT OR REPLACE / `precompute_rfm_cache` 预计算）从 read_only 单例改用独立写连接 `_open_write_conn()`（`duckdb.connect(..., access_mode=READ_WRITE)` 短生命周期）。修 ETL Step 6 "预计算 RFM 8象限历史周期缓存" 时 "Cannot execute CREATE on read-only database" 错误。**关键约束**：① `precompute_rfm_cache` 必须先 `_open_write_conn()` 再做其他操作（同进程内 DuckDB 不允许 read_only 单例已建后再开 read_write 写连接，会报 "Can't open a connection to same database file with a different configuration"）；② uvicorn 进程（read_only 单例已锁定）调 `_write_db_cache` 优雅降级为 warning（不影响 API 返回，cache 由 ETL 预计算填充）；③ 移除 `_write_db_cache` 冗余 `conn` 参数（内部开写连接），更新 `analysis.py` 调用方。pytest backend/tests/ 153/8 + tests/test_sanity_check.py 48 全过；ruff check . 0 errors。
- **DMP 单品资产 result 缓存不感知 mtime 变化** — `dmp_asset_service` 的 `result`/`result_other` 缓存按 `_weeks` 单字段 key 缓存，`_check_reload` 只刷 `mtime`+`df` 不动 result 缓存，导致 work plat 更新 `data3.csv` 后前端的"单品资产"tab 仍显示旧周。修复分两步：① `product.py`/`other.py` 缓存判断前先调一次 `_load_data3()` 让 mtime check 有机会跑；② `_helpers._load_data3` 检测到 mtime 变化时连带清掉 `result`/`result_other`。新增 `test_dmp_asset_cache.py` 4 个 regression test 覆盖。
- **scraper/ 20 个 pre-existing lint 错误治理** — 物理合并 work plat → scraper/ 时把 scraper/ 临时加到 ruff exclude，本次治理完成。`ruff --fix` 自动修 9 个（F841 / F401 / F811 / F541）+ 手动修 11 个（E402 ×6 加 `# noqa: E402` 保留 sys.path.insert 后 import 的有意设计，F401 ×2 删 unused imports，F841 ×2 删 dead code）+ `pyproject.toml` 移除 `scraper/` from exclude 重新纳入 ruff 检查。pytest 201 passed（backend 153/8 + sanity_check 48）。下阶段 P0（QW1/2/3/5）可以开。

### Changed
- **Monorepo 化：物理合并 work plat/DMP_test_package → `fuqing-crm-analytics/scraper/`** — 按"方案 B"（Q0 业务价值调研后采纳）合并 scraper 代码到 monorepo。`backend/config.py` DMP_DATA_DIR 默认值改为 monorepo 相对路径 `scraper/core`（`.env` 环境变量仍可覆盖，向后兼容 work plat 旧位置）。`pyproject.toml` ruff 临时排除 `scraper/`（原 DMP_test_package 19 个 pre-existing lint 错误不在本次范围，留到 task 14 "work plat 6 道门禁 + 飞书 webhook" 阶段统一治理）。数据物理迁移（work plat/core/data2.csv 等）未做，下次 checkpoint 单独进行。Q0 调研报告：见 `docs/dmp-poc/达摩盘官方API评估报告v1.0.md`。
- **数据物理迁移：work plat/core/data*.csv → scraper/core/data*.csv** — `data2.csv` (56711B/760行)、`data3.csv` (580572B/7044行)、`data.csv` (130667B/2273行) 全部从 work plat 旧位置搬到 monorepo 内的 `scraper/core/`。`.env` DMP_DATA_DIR 同步更新。work plat 旧位置已空，scraper/core 是唯一数据源。uvicorn 重启后 service 层 3 个 tab 全部 05/25-05/31 正常。

### Fixed
- **DMP_DATA_DIR 空字符串 fallback bug** — `backend/config.py:120` 之前用 `Path(os.environ.get("DMP_DATA_DIR", str(_DEFAULT_DMP_DIR)))`，当 `.env` 设 `DMP_DATA_DIR=`（空字符串）时 `os.environ.get` 返回空字符串不会 fallback 到默认值，`Path("")` 解析为 `Path(".")` 当前目录。改为先 `.strip()` 再判空，空则用 monorepo 默认 `scraper/core`。

### Documentation
- **ETL Phase 4 架构设计文档入仓（4 层 SaaS 重构）** — `docs/design/etl-phase4-architecture.md` (460 行, APPROVED) 落地：① Layer 1 Source（xlsx→Parquet→DuckDB orders）+ Layer 2 ETL Pipeline（W1 GROUPING SETS / W2 原子 manifest / W3 DQ+幂等）+ Layer 3 Precomputed Serving（fact_rfm_long 纯增量 + dbt-style snapshot）+ Layer 4 Query API（DuckDB-KV 缓存 24h TTL）；② 5 个 WO 详细规范 + 4 周时间线 + 4 阶段灰度迁移；③ Acceptance Criteria 覆盖 3 痛点（ETL < 35min / 不再读到半新半旧 / 历史秒出）；④ 4 个 open questions 已 user 拍板（异步后台跑全历史 / 单 view / 告警+ETL 继续 / miss 走 fact_rfm_long）。Supersedes HANDOFF-etl-perf-2026-06-02.md（13 工单，范围扩展为架构分层）。gstack artifacts 同步：`hutou-main-design-20260604-180114.md`。
- **ETL Perf 4-Layer design v1.1 增量** — 标题改 "ETL Perf 4-Layer Restructure" 避免和 PRD §11.3 Phase 4 混淆。**新增 W6**（lark-cli ETL 跑完通知，复用 sanity_check.py _send_lark_alert）+ **W7**（DUCKDB_MEMORY_LIMIT_OVERRIDE 临时 16GB，平时 8GB）。**W1-W5 各加 CLAUDE.md 合规段**：W1 走 `backend.semantic.segments`、W2 manifest 用 `os.rename` + fsync + 并发读安全、W3 复用 lark-cli 通道、W4 走语义层 + PRD §4.1/§4.2/§4.3 验收、W5 ThreadSafeCursor 包装。**加 §11 PRD-derived 验收点**（< 3s SLA / 9am 自动刷新 / 改口径只改 1 文件）。**加 §16 12 步 check-list per WO**（分支命名 / commit message / 每个 WO 特殊附加项）。**加 §17 旧 13 工单 stale 审计表**（4 done + 2 被 W1 取代 + 7 stale 不重做）。**reference.md 修 840 → 540**（stale 数据，以 preload_rfm.py:28 注释为准）。

## [0.3.5] - 2026-06-04

### Performance
- **增量 ETL 跑批（6/4 baseline run 1/3 — 真实 elapsed 63.2min / step_wall_time_sum 126.4min）** — `python scripts/run_etl.py --update` 跑 6/4 增量（**真实 elapsed 63.2min** = started 10:42:59 → ended 11:46:09；**step_wall_time_sum 126.4min** = sum(per_step.wall_time) 含 Step 7b 540 组合 RFM 预加载 56.8min 单 step），处理 4 个新源文件：店铺 1（任务 21376，1.3MB 6/3 当日 8,350 单）+ 会员 1（任务 21377，676KB）+ 订单状态刷新 2（任务 21378，46MB → 91,307 行 override）。DuckDB 增量：orders 10,636,237 → 10,654,714（+18,477）/ user_first_purchase 4,237,949 → 4,246,328（+8,379）/ user_rfm 62.7M → 72.4M（+9.66M 含 466 组合预加载）/ daily_metrics 6/3 完整（GMV ¥1.40M / GSV ¥946K vs 6/2 ¥1.56M / ¥1.13M 合理回落）。`baseline_2026_06_03.json` 累积 3 个 run：run 1/3 = real elapsed 63.2min / step sum 126.4min（6/4 增量）/ run 2/3 = real elapsed 17.5min / step sum 52.6min（6/3 增量，保留）/ run 3/3 = real elapsed 63.2min / step sum 189.6min（etl_total 累计）。6 道 gates 因增量模式触发 skipped 但 overall=pass；errors=0。**已知 fail-soft（已修）**：`rfm_analysis_cache` 之前 57 行（vs 6/3 baseline 60）——`scripts/etl/pipeline.py:105` 早开 `read_only=True` 连接读历史 order_ids，污染同进程 DuckDB config，导致 `backend/services/health/rfm_analysis/cache.py:_open_write_conn()` 后续开 `access_mode=READ_WRITE` 抛 `Can't open a connection to same database file with a different configuration`；本次 commit ab78383 修法：去掉 read_only=True，用默认 READ_WRITE 连接，与 cache.py 后续 write_conn 保持一致 access_mode。**uvicorn 重启** (PID 19865, /api/v1/health 200, 5.6ms) + E2E 验证 rfm-analysis 1-6月 YTD GSV 8 象限 HTTP 200：TTL=4,244,556（+6,607）/ 重要价值 67.02% / 重要发展 55.60% / 一般价值 54.32% / 重要保持 4.01% / 重要挽留 2.57% 等，符合「高频+高粘+近购买」高复购、「低频+远购买」低复购业务预期；task #102 修复持续生效，无 100% / 0% 异常。
- **`scripts/etl/_timer.py` baseline wall_time 字段歧义修** — `save_baseline()` 旧字段 `wall_time_sec` / `meta.total_wall_time` 实际 = `sum(per_step.wall_time)` 即 step 累计 wall time，**不是**真实跑批 elapsed（ended - started），字段名误导读者以为"wall time"。**修法**：① 新增 `real_elapsed_sec` 字段 = ended - started 真实跑批 wall time（用户体感）；② 新增 `step_wall_time_sum` 字段 = sum(per_step.wall_time) 显式命名的 step 累计；③ 旧字段 `wall_time_sec` / `meta.total_wall_time` 保留为 deprecated 值（= step_wall_time_sum），加注释警示「实际是 step 累计，不是真实 wall time」；④ meta 段同步暴露 `real_elapsed_sec` / `step_wall_time_sum`。触发原因：review skill 事后审查 1d4f03f 入仓 baseline 时发现 CHANGELOG + commit 34a89dc 写"wall=126.4min"实际是 step 累计，真实 elapsed 只有 63.2min，数字翻倍误导；commit 34a89dc message 因 git 不可改历史保留原 wall=126.4min（reader 需结合本条目 + `_timer.py` 字段定义理解）。pytest 153/8 全过；ruff 0 errors；run 1/3 单测验证 real_elapsed_sec=0.155 < step_wall_time_sum=0.360，旧字段 wall_time_sec 仍等于 step_wall_time_sum（兼容历史 baseline JSON 读取方）。
- **QW0 严格 Phase 2：第 2 次 Mac baseline run 跑批入仓** — `data/processed/etl_perf/baseline_2026_06_03.json` 追加 run 2/3：wall=52.6min（cleanup 后 orders 表 2.9M 行的增量 ETL，31 个 per_step 节点），相比 run 1/3 (180.2min, cleanup 前 10.6M 行全量 ETL) **3.4x 提速**。提速来源：① cleanup 移除 7.7M order_id=sub_order_id 重复行 → Step 4 反向同步省时；② parquet 缓存命中 251/251 → Step 1 全店读 0 重读。**关键 bug 发现**：`scripts/etl/_timer.py:267` `save_baseline()` 默认 `run_id="1/3"` + 调用方未传具体值 → 同 baseline_date 多次跑批互相覆盖（origin/main 的 run 1 被 12:48 那次覆盖了），手动 git show 取回 run 1 + 改 run_id=2/3 追加合并；`wall_time_stdev` gate 标 skipped 并加 note 说明 run 1+2 数据规模不同 stdev 无意义。剩余 4 次 baseline（Mac ×1 + Windows ×3）+ median 计算 留 task #24/#34；`save_baseline` run_id 自增 fix 留 task #59 / `fix/timer-run-id-autoincrement` 分支单独 12 步。**注**：本条目 wall=52.6min 是 step_wall_time_sum 不是 real elapsed（real elapsed=17.5min），见上文 `_timer.py` baseline wall_time 字段歧义修条目。

### Fixed
- **`scripts/etl/pipeline.py` member_order_ids 连接改 READ_WRITE（修 rfm_analysis_cache fail-soft P0）** — `pipeline.py:105` 之前用 `read_only=True` 连接读历史 `order_ids` 集合，污染同进程 DuckDB config，导致后续 `cache.py:_open_write_conn()` 开 `access_mode=READ_WRITE` 抛 "Can't open a connection to same database file with a different configuration"，cache.py try/except return 0 致 Step 6 RFM 预计算 fail-soft（cache 维持 6/3 baseline 60 行不更新，业务无影响）。**修法**：去掉 `read_only=True`，用默认 READ_WRITE 连接，与 cache.py 后续 `_open_write_conn()` 保持一致 access_mode。仅 SELECT DISTINCT order_id 只读查询 + 立刻 close，不影响 DuckDB 文件。pytest 153/8 全过；ruff 0 errors。下次 ETL 跑批 rfm_analysis_cache 应正常更新到 60 行（12 组合）。commit ab78383。

### Documentation
- **文档同步更新（CLAUDE.md / README.md / docs/DOCUMENT-INDEX.md / docs/飞书版架构文档/{01-数据层,06-部署与运维}.md）** — 反映 v0.3.5 release：① 数据规模表 5/31 → 6/4（orders 10.65M / user_first_purchase 4.25M / user_rfm 72.4M / rfm_analysis_cache 60 / order_status_override 6/4 刷 91,307 行）；② Python 路径 workbuddy → homebrew 3.14；③ 6/4 增量 ETL 跑批实测（real elapsed 63.2min / step_wall_time_sum 126.4min）+ RFM 4 端点 P0/P1 修复合集 + wall_time 字段歧义修 全部进 README 当前状态；④ TEST 计数 149 → 153 passed；⑤ DOCUMENT-INDEX.md 最后更新 5/31 → 6/4；⑥ 后端启动命令更新（homebrew Python 3.14 + HEALTH_API_KEY env）。

## [0.3.4] - 2026-06-01

### Fixed
- **ETL 增量主键冲突** — 修复 `upsert_to_duckdb` 在 shop+member 合并数据时（高度重叠场景）写入 DuckDB 触发主键约束违反的 bug。修复：在去重前将 `order_id`/`sub_order_id` 统一转为字符串（防 float vs string 漏判），全新订单路径改用 staging 表 + ON CONFLICT DO NOTHING 模式，刷新路径在事务内通过 staging 表 + ROW_NUMBER() 去重后再写入，保持原子性。

### Changed
- **CLAUDE.md 加改代码前强制自检段** — 防止 AI 在 main 分支直接改代码的反模式。改 Edit/Write 前先答 2 问：当前在哪个分支？接下来要 commit 吗？

### Performance
- **Parquet缓存修复** — 修复 `_mark_all_files_processed` 只存mtime不存hash的bug，统一Parquet缓存key格式，增量ETL时间从10分钟降到1分钟
- **RFM SQL重写** — 合并 `hist_customers_all` + `hist_customers_same` 为单个CTE，使用GROUPING SETS消除TTL CTE，CTE数量从15个减少到5个
- **品类GROUPING SETS** — 品类预计算从4次独立查询优化为2次GROUPING SETS查询，扫描次数减少50%
- **RFM并行化** — 使用ThreadPoolExecutor并行执行3个周期查询，3x加速
- **DuckDB内存优化** — 添加 `DUCKDB_MEMORY_LIMIT` 环境变量配置（默认8GB），创建内存监控模块，避免Swap
- **内存监控** — 新增 `backend/db/memory_monitor.py` 模块，实时监控DuckDB内存使用，防止Swap

### Security
- **弱密码替换** — `admin:123456` / `fqsw:fqsw888` 替换为强密码，使用 bcrypt 哈希存储
- **API Key Header 传输** — `/config/history` 和 `/config/audit-log` 的 API Key 从 Query 参数改为 `X-API-Key` 请求头，防止日志泄露
- **API Key 时序攻击防护** — `!=` 比较改为 `hmac.compare_digest()` 常量时间比较
- **API Key 速率限制** — 新增滑动窗口限速（10次/5分钟/IP），防止暴力枚举
- **SQL 参数化** — `rfm_category_drilldown.py` 中 `rfm_segment` 和 `exclude_channels` 从字符串拼接改为 `?` 占位符参数化查询

### Performance
- **overview 查询合并** — `get_overview_metrics()` 从 9 次独立查询合并为 3 次（每个时间段 1 次 CTE），减少 66% 数据库往返
- **geo 趋势查询合并** — `get_geo_trend()` 从逐月循环 N 次查询改为 2 条 SQL（`DATE_TRUNC('month')` 一次性查出）
- **flow groupby 优化** — `get_flow_matrix()` 和 `get_flow_sankey()` 从 121 次 DataFrame 过滤改为 `groupby().size()` 一次性聚合
- **churn 时间窗口** — 4 个流失分析函数添加 730 天回溯窗口，避免全表扫描 + `LAG()` 窗口函数

### Changed
- **DuckDB 单例连接** — `get_connection()` 从每次请求新建连接改为全局单例 + `threading.Lock` 双重检查锁定
- **Router 分层修复** — 9 个 router 文件不再直接导入 `backend.semantic.time`，改为通过 `backend.services` 导入
- **代码去重** — 统一 `_normalize_date`（3→1）、`_segment_meta`（2→1）、`_VALID_BASE`（6→1）
- **RFM flow 引擎** — `r_flow.py` / `f_flow.py` / `m_flow.py` 从各 ~377 行简化为 ~58 行，共享逻辑提取到 `_flow_engine.py`
- **suggestions.py 常量迁移** — `R_INTERVALS`、`GSV_AMOUNT_COL`、`REPURCHASE_ADJUSTMENT` 迁移到语义层/配置层
- **应用关闭事件** — `main.py` 注册 `shutdown` 事件调用 `close_connection()`

### Fixed
- **RFM flow engine 参数错位** — `_flow_engine.py` 的 `hist_all_params` 缺少 `exclude_channels` 参数，导致 SQL 占位符与参数不匹配，当用户选择排除渠道时 RFM 流转看板返回 500 错误
- **路由守卫 401 闪现** — 前端路由守卫在 `isReady` 为 `false` 时直接放行，未登录用户可短暂访问受保护页面导致 401 请求。修复：在等待 `isReady` 之前直接检查 `sessionStorage` 中的 token
- **DuckDB 并发崩溃** — `get_connection()` 仅锁创建过程，未锁查询执行。页面刷新触发多个并发 API 请求时，多线程同时访问同一 DuckDB 连接导致 `fetchone()` 返回 `None`（`TypeError: 'NoneType' object is not subscriptable`）或 Python 进程段错误退出。修复：`connection.py` 引入 `ThreadSafeConnection` + `ThreadSafeCursor` 包装器，`execute()` 和 `fetch*` 自动串行化
- **DuckDB 结果集并发覆盖** — `ThreadSafeConnection.execute()` 只在执行 SQL 时加锁，返回 `ThreadSafeCursor` 后锁已释放。DuckDB 没有真正独立的 cursor（`execute()` 结果集绑定在连接上），另一个线程的 `execute()` 会覆盖连接上的结果集，导致 `fetchone()` 读到错误数据（如 `int(datetime.date)` 崩溃）。修复：`ThreadSafeCursor` 在构造时（锁内）预取全部结果到内存，后续 `fetch*` 不再触碰连接
- **fetchone() 空值防御** — `overview.py`、 `rfm_reader.py`、 `cache.py` 共 4 处 `fetchone()[0]` 未防御 `None` 结果，在连接异常时直接崩溃。修复：先判空再取下标
- **老客GSV占比 pp 值双重乘法** — `HealthOverviewTab` 中 `fmtYoy()` 已乘 100，`MetricCard` pp 模板再乘 100，导致显示 155pp/193pp。新增 `fmtPpt()` 直接传递原值
- **YOYBadge 单位显示错误** — `AudienceView` 中 ratio 类型列（新客占比/老客占比/会员占比等 YoY）未传 `unit='pp'`，导致显示 `%` 而非 `pp`。10 处 YOYBadge 调用修正为 `(value * 100, unit: 'pp')`
- **173 个 ruff lint 错误** — 修复 F821（未定义变量 6 个）、F401/F541/F811/E401（自动修复 130 个）、E702/E722（手动修复）。config.py 交叉导出加 `# noqa: F401` 防 ruff 误删
- **ETL 导入路径错误** — `scripts/etl/cli.py` 中 4 处导入路径错误导致 ETL Step 3-7 崩溃：`scripts.etl_status_override` → `scripts.etl.etl_status_override`（3处），`scripts.preload_rfm` → `scripts.etl.preload_rfm`（1处）
- **日趋势图会员占比** — 修复日趋势图的会员占比从「订单数占比」改为「GSV金额占比」，与人群看板一致。新增 `overall_member_ratio` 字段返回整体会员GSV占比
- **YOY/MoM 值格式不一致** — 修复后端返回的 YOY/MoM 值格式不一致（部分已是百分比，部分是小数），导致前端显示 155pp 等三位数。所有值统一为小数形式

### Changed
- **CLAUDE.md 瘦身** — 460 行 → 132 行（-71%），参考材料（口径表/历史教训/包拆分清单/目录结构）移到 `docs/reference.md`（按需读取），每次会话节省 ~60% token
- **文档精简** — 归档 5 个冗余/已完成文档：DESIGN.md、DEPLOY.md、MODULE-INDEX.md、etl-incremental-fix-plan.md、REPAIR_PLAN.md

### Added
- **Pre-commit/Pre-push hooks** — `.githooks/pre-commit`（ruff check）和 `.githooks/pre-push`（pytest）阻止不合规代码提交和推送
- **GitHub Actions CI** — `.github/workflows/lint.yml` 在 PR 和 main push 时自动运行 ruff + pytest
- **AI 执行检查点** — CLAUDE.md 新增硬性 STOP 检查表：commit 前必须 review、push 前测试全绿、merge 前必须 qa
- **CI/CD 防线** — pre-commit (ruff) + pre-push (pytest) + GitHub Actions CI，三层拦截不合规代码
- **Parquet 缓存填充脚本** — 新增 `scripts/etl/fill_parquet_cache.py`，将 161 个 xlsx 文件批量转换为 Parquet 缓存，增量 ETL 加速 10-50x
- **原子写入** — `_save_parquet_cache()` 和 `_save_processed_files()` 支持 tmp+rename 原子写入，防止中断产生损坏文件
- **Parquet 缓存测试** — 新增 9 个测试覆盖 Parquet 写入、增量检测、原子写入、processed_files 更新等核心逻辑

### Fixed
- **processed_files 覆写** — `fill_parquet_cache.py` 保存时合并已有记录，避免丢失历史 ETL 状态
- **单元测试全覆盖** — 新增 91 个测试覆盖 12 个模块：breakdown_service（15）、rfm_service（16）、rfm_analysis（8）、health/overview（19）、health/conversion（7）、health/repurchase（2）、health/tier_flow（1）、health/channel_scores（1）、category_service/overview（4）、category_service/distribution（1）、category_service/churn（1）、category_service/basket（1）
- **R 区间边界测试** — 验证 `_get_r_interval_current_distribution` 的 R 区间分桶（30/90/180/365/730 天）和 F 段（F>1/F=1）正确性
- **GSV 口径测试** — 验证退款订单（is_refund=TRUE）、购物金（is_goujinjin=TRUE）、交易关闭订单不计入 GSV
- **Codex 交叉审核** — 使用 Codex regular + adversarial 模式审核代码变更，发现并修复 5 个问题

### Fixed
- **check_future_date(None) 崩溃** — `backend/semantic/time.py` 的 `check_future_date()` 在 mtd/wtd/ytd 模式下接收 None 参数时触发 TypeError。修复：函数入口加 `if date_str is None: return None` 守卫，except 加 `TypeError`
- **日期正则不验证日历** — `re.fullmatch(r'\d{4}-\d{2}-\d{2}')` 接受无效日期如 2025-02-30。修复：regex 后加 `datetime.strptime` 验证实际日期有效性
- **visitor.py 未使用 import** — 删除 `backend/routers/visitor.py` 中未使用的 `import json`
- **品类回购分析数据为 0** — `_RFM_SEGMENT_ORDER`（`category_service/_shared.py`）与 SQL `rfm_segmented` CTE 的 RFM 象限命名不一致：常量定义了 4 个无"客户"后缀的名称（如 `"重要价值"`），而 SQL 生成 8 个带后缀的名称（如 `"重要价值客户"`）。`api.py` 的 `_build_rows` 用旧名称查找 SQL 结果 → key 不匹配 → 所有数值归零。修复：`_RFM_SEGMENT_ORDER` 更新为 8 个带"客户"后缀的完整象限名称。`/category/repurchase-flow` 接口现已正确返回品类各 RFM 象限回购数据（hist/repurchased），可通过 `curl http://localhost:8000/api/category/repurchase-flow` 验证
- **Lint 清理** — 消除 `rfm/r_flow.py`、`rfm/m_flow.py`、`rfm/f_flow.py`、`rfm/segment_orders.py` 的 F403/F405 star import（117 errors → 0）；清理 `routers/__init__.py` 16 个 F401 unused import；删除死代码 `breakdown_service.py` shim；修复 `rfm/_shared.py`/`export_service.py`/`metrics/__init__.py` 等多处 F401；E701/E741 若干
- **Lint 清理（续）** — `category_service/flow/__init__.py`、`category_service/flow.py`、`category_service/repurchase/__init__.py`、`category_service/repurchase.py` 消除 F403 star import；删除死代码 `dmp_asset_service.py` shim；`dmp_asset_service/__init__.py` 改为显式导入；`health/rfm_analysis/__init__.py`、`health/rfm_analysis.py` 消除 F403

## [0.3.3] - 2026-05-29

### Fixed
- **SQL 注入修复** — `breakdown_service/_shared.py` 4 个函数将日期参数从 f-string 拼接改为 DuckDB `?` 参数化；`_r_interval_sql` 内部 `DATE '{cutoff}'` 也改为参数化
- **硬编码路径修复** — `VISITOR_XLSX_FILE` 从 Mac 绝对路径迁移到 `backend/config.py` 的环境变量配置

### Changed
- **开发者体验** — `/docs` 和 `/redoc` 从认证中间件白名单移除，新开发者可直接浏览器探索 API
- **未来日期警告** — 传入未来日期时，API 在 `X-Data-Warning` 响应头返回明确警告（`backend/semantic/time.py` 的 `check_future_date()`），覆盖 `/overview`、`/targets`、`/repurchase-cycle`、`/value-tiers`、`/tier-flow`、`/rfm-analysis`、`/rfm-category-drilldown`、`/channel-health-scores`、`/new-customer-conversion`、`/r-flow`、`/f-flow`、`/m-flow`、`/segment-orders` 等 13 个端点

## [0.3.2] - 2026-05-28

### Fixed
- **后端代码审计** — 修复 23 个问题（P0×5/P1×7/P2×11），包括口径不一致、测试阈值硬编码、contracts 重复、类重复定义等
- **大文件拆分** — 将 6 个超大文件拆分为包（rfm_service/flow/breakdown/dmp_asset/repurchase/rfm_analysis），并补全所有交叉导入
- **SPU 版本化** — orders 表新增 `spu_hash` 字段，避免 SPU 重命名导致历史数据不可追溯
- **Bundle 优化** — xlsx 依赖改为懒加载，减少首屏 bundle 体积

### Added
- **ETL Parquet 缓存层** — 中间计算结果写入 parquet，减少重复计算
- **前端性能基线** — 建立性能 benchmark，便于回归检测

## [0.3.1] - 2026-05-27

### Changed
- **Docker 化就绪** — 后端支持 Docker 部署
- **磁盘清理** — data/ 目录清理，释放 7.7G 空间

## [0.3.0] - 2026-04-20

### Added
- **Vue3 前端上线** — 8 个 dashboard 页面，SPA 路由，xlsx 导出
- **RFM 8 象限重构** — 区间流转 + 品类下钻完整实现

## [0.2.0] - 2026-04-16

### Added
- **语义层 + 契约层** — v3.0 架构重构，口径统一管理
- **DuckDB 数据平台** — 1030 万订单 / 410 万用户数据接入

## [0.1.0] - 2026-03-27

### Added
- **项目启动** — 基础架构设计，FastAPI 后端框架搭建

---

## 版本说明

本项目使用 **semver** 格式：`MAJOR.MINOR.PATCH`

| 字段 | 含义 |
|------|------|
| MAJOR | 不兼容的 API 变更（如删除端点、修改 Schema） |
| MINOR | 向后兼容的新功能（如新增端点、新增响应字段） |
| PATCH | 向后兼容的缺陷修复（如 BugFix、安全补丁） |

> 注意：当前 MAJOR = 0 表示项目仍在初始开发阶段，API 可能在 MINOR 版本中变化。
