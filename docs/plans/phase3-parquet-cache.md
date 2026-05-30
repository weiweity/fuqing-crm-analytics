# Phase 3: Parquet 缓存填充

> 目标：将 161 个 xlsx 文件全部转换为 Parquet 缓存，让增量 ETL 加速 10-50x

## 执行计划（按 CLAUDE.md 12 步流程）

### ① 创建 feature 分支

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
git checkout -b feature/parquet-cache-fill
```

### ② 写代码（3 个文件）

#### 文件 1: `scripts/etl/ingest.py`（修改 `_save_parquet_cache`）

修改第 233-247 行，支持原子写入：

```python
def _save_parquet_cache(df, xlsx_path, data_type):
    """将 xlsx 读取后的 DataFrame 存为 Parquet，下次 ETL 直接读 Parquet 跳过 openpyxl。

    写入到 PARQUET_DATA_DIR/<data_type>/<filename>.parquet。
    原子写入：先写 .tmp 再 rename，防止中断产生损坏文件。
    失败不阻塞 ETL，仅打印警告。
    """
    pq_dir = PARQUET_DATA_DIR / data_type
    pq_dir.mkdir(parents=True, exist_ok=True)
    pq_path = pq_dir / f"{xlsx_path.stem}.parquet"
    tmp_path = pq_dir / f"{xlsx_path.stem}.parquet.tmp"
    try:
        df.to_parquet(tmp_path, index=False)
        os.rename(tmp_path, pq_path)
        print(f"    [Parquet 写入] {pq_path.name} ({len(df):,} 行)")
    except Exception as e:
        # 清理临时文件
        if tmp_path.exists():
            tmp_path.unlink()
        print(f"    [Parquet 写入失败] {pq_path.name}: {e}")
```

#### 文件 2: `scripts/etl/fill_parquet_cache.py`（新建）

核心逻辑：
- 遍历 SHOP_DATA_SOURCE 和 MEMBER_DATA_SOURCE 下所有 xlsx
- 增量检测：mtime + hash（与 ingest.py `_file_changed()` 逻辑一致）
- 预处理：`rename_columns()` + datetime 解析（与 ingest.py 第 180-200 行一致）
- 原子写入：先写 .tmp 再 rename
- 更新 processed_files JSON（转换成功后记录 mtime + hash）
- 启动时清理残留 .parquet.tmp 文件
- 用 homebrew Python 3.14 运行

```bash
# 用法
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/fill_parquet_cache.py                    # 转换全部
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/fill_parquet_cache.py --data-type shop   # 只转换 shop
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/fill_parquet_cache.py --force             # 强制重新转换
```

#### 文件 3: `backend/tests/test_fill_parquet_cache.py`（新建）

测试用例：
- Parquet 写入逻辑
- 增量检测（mtime + hash）
- 原子写入（中断后重新运行不产生损坏文件）
- processed_files 更新
- 错误处理（无 order_id 列、空 DataFrame）
- 集成测试：fill 脚本产出的 parquet 能被 ingest.py 正确读取

### ③ 跑测试

```bash
PYTHONPATH="$(pwd)" pytest backend/tests/ -x -q
```

### ④ review skill — commit 前自检

### ⑤ 修复 review 发现的问题

### ⑥ git commit

```bash
git add scripts/etl/ingest.py scripts/etl/fill_parquet_cache.py backend/tests/test_fill_parquet_cache.py
git commit -m "feat: add Parquet cache fill script + atomic write for _save_parquet_cache"
```

### ⑦ git push

```bash
git push origin feature/parquet-cache-fill
```

### ⑧ 运行 fill 脚本（实际转换）

```bash
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/etl/fill_parquet_cache.py
```

预计耗时：30-60 分钟
输出：`data/parquet/shop/*.parquet` 和 `data/parquet/member/*.parquet`

### ⑨ 验证

```bash
# 检查 Parquet 文件数量
find data/parquet/ -name "*.parquet" | wc -l   # 应该是 161

# 跑增量 ETL 验证 Parquet 缓存生效
PYTHONPATH="$(pwd)" /Users/hutou/homebrew/bin/python3 scripts/run_etl.py --update
```

### ⑩-⑬ 合并 + 更新 CHANGELOG

按 CLAUDE.md 12 步流程执行。

## 关键约束（来自 CLAUDE.md）

| 约束 | 说明 |
|------|------|
| ETL 用 homebrew Python 3.14 | `/Users/hutou/homebrew/bin/python3`，不用 workbuddy Python 3.13 |
| 语义层唯一真实数据源 | 禁止在 Service 里硬编码口径 |
| Schema 三同步 | Service → schemas.py → types.ts |
| 本地即生产 | merge 后必须 pull + 重启 uvicorn |
| 禁止事项 | ❌ 跳过 review/qa ❌ 直接在 main commit ❌ commit -m "fix" |

## 风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| Parquet 文件损坏 | 原子写入（.tmp → rename），可随时删除 `data/parquet/` 回滚 |
| 大文件 OOM | 逐文件处理 + `del df` + `gc.collect()` |
| processed_files 不一致 | 使用与 ingest.py 相同的 `_save_processed_files()` |
| 磁盘空间不足 | 保守估算 150-300MB，脚本启动时清理 .tmp 残留 |
