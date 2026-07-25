# DuckDB 备份与 1.5.5 升级检查清单（仅文档，PR5 不执行生产操作）

> **硬约束**：本 PR / 本文件 **不**在生产执行升级，**不**复制 131GB 库，**不**修改现网 `duckdb` pin 为强制 1.5.5。  
> 当前 lock：`duckdb==1.5.3`（与现网兼容）。升级为**独立变更窗口** + 人工执行。

## 0. 范围

| 项 | 本 PR | 独立运维窗口 |
|----|-------|----------------|
| 文档 checklist | ✅ | — |
| 备份脚本说明 | ✅ | — |
| 生产备份 | ❌ | ✅ |
| 升级到 1.5.5 | ❌ | ✅ |
| 复制 131GB 到 CI / Docker | ❌ 禁止 | ❌ 禁止 |

## 1. 升级前（T-7 ~ T-1）

- [ ] 确认现网 DuckDB 文件路径（`DUCKDB_PATH` / Windows 部署路径）
- [ ] 确认磁盘空间 ≥ **2×** 库体积 + 20%（备份 + 可能 VACUUM）
- [ ] 冻结非必要 ETL / 写操作窗口
- [ ] 阅读 [DISASTER-RECOVERY.md](../DISASTER-RECOVERY.md) P1 节
- [ ] 在**隔离机**用**副本**验证 `1.5.5` 只读打开 + 关键查询（**不要**直接动生产文件）
- [ ] 记录当前 Python / `duckdb` wheel 版本：`python -c "import duckdb; print(duckdb.__version__)"`

## 2. 备份（生产窗口内第一步）

### 2.1 停写

```bash
# macOS launchd / Windows NSSM：先停 API 与定时 ETL
# 确认无 python 进程持有 duckdb 文件锁
```

### 2.2 文件级备份（推荐）

```bash
# 示例：路径按现网改写。禁止把备份打进 git。
SRC="${DUCKDB_PATH:-/path/to/fuqing.duckdb}"
STAMP=$(date +%Y%m%d_%H%M%S)
DEST="/backup/fuqing_duckdb_${STAMP}"
mkdir -p "$DEST"
cp -a "$SRC" "$DEST/"
# 若有 WAL：
[ -f "${SRC}.wal" ] && cp -a "${SRC}.wal" "$DEST/"
# 校验
ls -lh "$DEST"
shasum -a 256 "$DEST"/* | tee "$DEST/SHA256SUMS"
```

### 2.3 逻辑导出（可选，更慢）

```bash
python - <<'PY'
import duckdb, os
src = os.environ["DUCKDB_PATH"]
con = duckdb.connect(src, read_only=True)
# 示例：导出关键表清单到 parquet 目录（路径自定义）
# con.execute("EXPORT DATABASE '/backup/export_xxx' (FORMAT PARQUET)")
con.close()
print("ok")
PY
```

### 2.4 异地

- [ ] 至少一份备份离开生产机（NAS / 对象存储 / 加密移动盘）
- [ ] 抽检：在**另一台机器**只读打开备份文件成功

## 3. 升级步骤（独立窗口，成功备份后）

1. [ ] 在 venv 安装目标版本：`pip install 'duckdb==1.5.5'`
2. [ ] 更新 `requirements.txt` / `requirements-lock.txt` / `requirements-e2e.txt` 的 pin（**单独 PR**）
3. [ ] 只读打开生产库路径的**备份副本**，跑：
   - `SELECT 1`
   - 核心看板 API 对应的 3~5 条只读 SQL
   - `pytest backend/tests/ -q -m "not slow"`（CI 或预发）
4. [ ] 预发通过后，维护窗口：停服务 → 备份 → 换 wheel → 启服务 → `/api/v1/health` + 业务抽检
5. [ ] 观察 24h：ETL、导出、缓存重建

## 4. 回滚

- [ ] 停服务
- [ ] 恢复备份文件 + WAL（若有）
- [ ] 恢复旧 `duckdb` wheel 版本
- [ ] 健康检查与业务抽检
- [ ] 写事故记录到 `docs/history/` 或运维日志

## 5. 禁止事项

1. **禁止**在 GitHub Actions 下载或挂载 131GB 生产库  
2. **禁止**把生产 `.duckdb` 提交进 git 或 Docker 镜像  
3. **禁止**无备份升级  
4. **禁止**与无关大改（API 行为、ETL 语义）同一变更窗口  
5. CI e2e 仅用 `scripts/ci/seed_e2e_duckdb.py` 级夹具

## 6. 脚本指针（已有，不在本 PR 新造重型备份工具）

| 用途 | 位置 |
|------|------|
| 灾难恢复总册 | `docs/DISASTER-RECOVERY.md` |
| e2e 小库 seed | `scripts/ci/seed_e2e_duckdb.py` |
| 健康检查 | `GET /api/v1/health`、`/api/v1/health/db_size` |
| Windows 部署注意 | `docs/WINDOWS-DEPLOY-KNOWN-ISSUES.md` |

如需专用 `scripts/ops/backup_duckdb.sh`，在**升级窗口 PR** 中新增并在预发演练，不要与供应链 CI 改动捆绑。

## 7. 签字栏（人工）

| 角色 | 姓名 | 日期 | 结果 |
|------|------|------|------|
| 执行 | | | backup OK / fail |
| 复核 | | | upgrade OK / rollback |
| 业务确认 | | | 看板抽检 OK |
