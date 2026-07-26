# DuckDB 可恢复备份与 1.5.5 升级检查清单

> **硬约束**：本分支只修代码和文档，**不**执行生产备份、升级、依赖同步或服务重启。
> 当前 lock 为 `duckdb==1.5.3`；PyPI 在 2026-07-22 发布稳定版 `1.5.5`。升级有意义，但必须排在“可恢复备份 + 恢复演练”之后，并使用独立 PR 与维护窗口。

官方依据：

- [DuckDB PyPI releases](https://pypi.org/project/duckdb/)
- [COPY FROM DATABASE](https://duckdb.org/docs/current/sql/statements/copy)
- [ATTACH / READ_ONLY](https://duckdb.org/docs/current/sql/statements/attach)
- [Reclaiming Space](https://duckdb.org/docs/current/operations_manual/footprint_of_duckdb/reclaiming_space)

## 0. 范围与当前结论

| 项 | 本分支 | 独立运维窗口 |
|---|---:|---:|
| 修复 checklist / 禁用错误建议 | ✅ | — |
| 生产一致性备份 | ❌ | ✅ |
| 异机或隔离目录恢复演练 | ❌ | ✅ |
| 升级到 1.5.5 | ❌ | ✅（备份演练通过后） |
| 复制生产库到 CI / Docker | ❌ 禁止 | ❌ 禁止 |

当前复核未发现可验证恢复点。旧 `shutil.copy2 + zstd` 实现会额外制造超大文件，且未证明复制时点一致性；`scripts/etl/backup_duckdb.py` 现已移除该执行路径，默认硬拒绝并只保留 `--verify-only`。配套 launchd 仍是 **legacy 模板，不得安装或手工触发**。

## 1. 升级前（T-7 ～ T-1）

- [ ] 记录生产库实际路径、大小、DuckDB/Python 版本、当前 commit SHA
- [ ] 备份介质可用空间 ≥ **2× 数据库体积 + 20%**
- [ ] 确认备份目录不在仓库、Docker build context、`/tmp` 或系统盘临时目录
- [ ] 安排 API、ETL、ad-hoc 写任务全部停写的维护窗口
- [ ] `lsof <db-path>` 确认没有进程持有数据库或 WAL
- [ ] 记录 RPO/RTO、执行人、复核人和回滚判据
- [ ] 在微型夹具上验证备份实现，再接触生产路径

## 2. 一致性备份（生产窗口第一步）

### 2.1 禁止文件级热拷贝

以下方案不得作为新备份实现：

- `cp` / `cp -a` / `shutil.copy2` 直接复制正在使用的 `.duckdb`
- 高频 launchd snapshot
- 把 131GB 生产库复制到 `/tmp`
- 文档中旧的 `VACUUM INTO` 建议（DuckDB 不支持该 SQLite 语法）

### 2.2 推荐：DuckDB 原生数据库复制

停写并确认无持锁进程后，使用 `ATTACH ... (READ_ONLY)` + `COPY FROM DATABASE source TO backup` 创建新数据库。下面是待在升级窗口 PR 中落地并先用微型库验证的参考实现：

```python
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb


def sql_string(path: Path) -> str:
    # ATTACH 不接受 DB-API `?` 参数；路径必须先由程序限定在批准目录，
    # 再按 SQL string literal 规则转义。不得接受 HTTP/CLI 任意输入。
    return "'" + str(path).replace("'", "''") + "'"


source = Path(os.environ["DUCKDB_PATH"]).resolve(strict=True)
backup_root = Path(os.environ["FQ_DUCKDB_BACKUP_DIR"]).resolve(strict=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
destination = backup_root / f"fuqing_crm_{stamp}.duckdb"

if destination.parent != backup_root or destination.exists():
    raise RuntimeError("invalid or existing backup destination")

con = duckdb.connect()
try:
    con.execute(f"ATTACH {sql_string(source)} AS source (READ_ONLY)")
    con.execute(f"ATTACH {sql_string(destination)} AS backup")
    con.execute("COPY FROM DATABASE source TO backup")
finally:
    con.close()
```

实现 PR 还必须具备：

- 目标目录 allowlist、`0700` 目录与 `0600` 文件权限
- 目标文件必须不存在；失败时只清理本次生成且位于批准目录内的文件
- `lsof` 不可用或结果不确定时 fail-closed
- 单实例锁、磁盘容量预检、结构化日志和明确退出码
- 不在同一步做压缩；先验证原生数据库可恢复，再决定是否离线流式压缩

### 2.3 完整性与恢复验证

- [ ] 记录源/备份字节数与 SHA-256（哈希用于传输完整性，不代表逻辑正确）
- [ ] 用**新进程** `read_only=True` 打开备份
- [ ] 比对表清单、关键表行数、关键业务日期范围和 3～5 条看板 SQL
- [ ] 将备份恢复到另一目录或另一台机器，使用实际应用版本启动只读抽检
- [ ] 恢复演练通过后再把该文件标记为“可回滚恢复点”
- [ ] 至少一份加密副本离开生产磁盘

## 3. 1.5.5 升级（独立 PR / 独立窗口）

1. [ ] 在隔离 venv 更新 `requirements.txt`、`requirements-lock.txt`、`requirements-e2e.txt`
2. [ ] 仅用**备份副本**验证 1.5.5 只读打开与关键 SQL
3. [ ] 执行 contracts lint、ruff、全量 backend pytest、frontend build/unit
4. [ ] 模拟生产新连接：Step 8 → 释放 singleton → W3/W4/taoke direct connection
5. [ ] 维护窗口：停服务/ETL → 再做一致性备份 → 升 wheel → 启服务
6. [ ] 抽检 health、登录、关键看板、导出、ETL dry-run
7. [ ] 观察至少 24 小时的 ETL、缓存重建、内存、磁盘与错误日志

## 4. 回滚

- [ ] 停止 API 与 ETL，确认无数据库持锁进程
- [ ] 保存失败版本文件供取证，不覆盖唯一副本
- [ ] 恢复已演练通过的一致性备份
- [ ] 恢复 `duckdb==1.5.3` lock/wheel 与上一版本代码
- [ ] health、登录、关键看板和 ETL 抽检通过后恢复业务
- [ ] 将事故时间线、数据窗口与根因写入 `docs/history/`

## 5. 禁止事项

1. 禁止无已验证恢复点升级
2. 禁止在 GitHub Actions 或 Docker 使用生产库
3. 禁止热拷贝正在写入的 DuckDB
4. 禁止把备份写进仓库、`/tmp` 或系统临时目录
5. 禁止把升级与 API/ETL 业务语义大改放进同一维护窗口
6. 禁止把“备份文件存在”等同于“可恢复”；恢复演练才是完成条件

## 6. 签字栏（人工）

| 角色 | 姓名 | 日期 | 结果 |
|---|---|---|---|
| 执行 | | | backup OK / fail |
| 复核 | | | restore drill OK / fail |
| 升级 | | | upgrade OK / rollback |
| 业务确认 | | | 看板/ETL 抽检 OK |
