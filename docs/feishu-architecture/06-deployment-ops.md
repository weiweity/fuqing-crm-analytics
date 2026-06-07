# 芙清 CRM — 部署与运维文档

**版本**: v3.1（2026-06-06 补 W2 manifest + W4 fact_rfm_long + W5 cache 部署段）
**环境**: macOS 本地运行

---

## 1. 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.14（homebrew） | `/Users/hutou/homebrew/bin/python3`（workbuddy Python 3.13 有代码签名冲突） |
| Node | 22.12（managed） | `~/.workbuddy/binaries/node/versions/22.12.0/bin/node` |
| DuckDB | 内置 Python 包 | `pip install duckdb` |
| npm | 10+ | 用于前端依赖安装 |

---

## 2. 启动命令

### 2.1 后端服务

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"

# 启动后端（端口 8000，uvicorn + 热重载；用 homebrew Python 3.14）
export HEALTH_API_KEY=$(grep '^HEALTH_API_KEY=' .env | cut -d= -f2)
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
  nohup /Users/hutou/homebrew/bin/python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 \
  >> /tmp/fuqin-crm-backend.log 2>&1 &

# 验证启动
curl -s http://localhost:8000/api/v1/health
```

### 2.2 前端服务

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3"

# 安装依赖（首次）
npm install

# 启动 dev server（端口 5173）
npm run dev

# 构建生产版本
npm run build
```

### 2.3 同时启动

```bash
# 后端（端口 8000）
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
  nohup ~/.workbuddy/binaries/python/envs/default/bin/python -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend \
  >> /tmp/fuqin-crm-backend.log 2>&1 &

# 前端（端口 5173）
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics/frontend-vue3"
npm run dev
```

---

## 3. ETL 运维

### 3.1 增量更新（日常）

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
  ~/.workbuddy/binaries/python/envs/default/bin/python scripts/run_etl.py --update
```

### 3.2 全量重建（数据异常时）

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
  ~/.workbuddy/binaries/python/envs/default/bin/python scripts/run_etl.py --full
```

### 3.3 ETL 日志监控

```bash
# 查看后端日志
tail -100 /tmp/fuqin-crm-backend.log
```

### 3.4 手动刷新 RFM 表

```bash
# 刷新 RFM 数据（象限计算）
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
  ~/.workbuddy/binaries/python/envs/default/bin/python -c \
  "from scripts.etl.precompute_fact_rfm import run_mvp_async; run_mvp_async()"
```

---

## 4. 数据健康检查

### 4.1 DuckDB 连接验证

```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
PYTHONPATH="/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics" \
  ~/.workbuddy/binaries/python/envs/default/bin/python -c "
import duckdb
from backend.config import DUCKDB_PATH
conn = duckdb.connect(DUCKDB_PATH, read_only=True)
result = conn.execute('SELECT COUNT(*) FROM orders').fetchone()
print(f'订单总数: {result[0]}')
conn.close()
"
```

### 4.2 关键指标抽检

```python
# GSV vs GMV 一致性抽检（同一区间）
# 预期：GMV >= GSV（差值为退款金额）
import requests
r = requests.get('http://localhost:8000/api/v1/metrics/overview', params={
    'metric_type': 'GSV',
    'start_date': '2026-01-01',
    'end_date': '2026-01-31'
})
print(r.json())
```

### 4.3 ETL 门卫阈值

| 门卫 | 阈值 | 触发动作 |
|------|------|---------|
| 退款率 | < 25% | 收紧 |
| null 占比 | < 5% | 预警 |
| 数据延迟 | < 24h | 正常 |

---

## 5. 常见问题

### 5.1 前端 API 请求失败

```
可能原因：后端未启动 / 端口不对 / CORS 问题
排查：curl http://localhost:8000/api/v1/metrics/overview
```

### 5.2 数据为 0 或异常

```
可能原因：时间范围无数据 / ETL 未运行 / DuckDB 路径错误
排查：直接查询 DuckDB 验证数据
```

### 5.3 TypeScript 类型报错

```
可能原因：后端 OpenAPI 更新后未重新生成类型
解决：npm run generate-types（重新执行 openapi-typescript）
```

### 5.4 ETL 报错

```
可能原因：数据源文件路径变更 / xlsx 格式变化
排查：python scripts/run_etl.py --dry-run
```

---

## 6. 目录结构

```
fuqing-crm-analytics/
├── backend/
│   ├── main.py              # FastAPI 入口（端口 8000）
│   ├── config.py            # DUCKDB_PATH 统一配置
│   ├── semantic/            # 语义层（filters/metrics/segments/channels/time/calculations）
│   ├── contracts/           # Pydantic 契约层
│   ├── services/            # 10 个 Service + health 10模块
│   ├── routers/             # API 路由
│   ├── db/                  # 数据库连接管理
│   └── tests/               # 单元测试
├── frontend-vue3/           # Vue3 前端（端口 5173）
├── scripts/
│   ├── run_etl.py          # ETL 脚本（含增量检测/淘客缓存）
│   └── etl/                # ETL 内部模块
│       ├── manifest.py     # W2 原子 manifest 切换 (SnapshotManifest class)
│       ├── precompute_fact_rfm.py # W4 预计算 (v0.4.9 MVP, 1 组合验证)
│       └── assertions.py   # W3 DQ 断言 (v0.4.10)
├── config/
│   ├── health_config.json   # 健康分析配置
│   └── health_config_backups/  # 配置历史备份
├── data/
│   ├── fuqing_crm.duckdb   # DuckDB 数据库
│   ├── manifest.json       # W2 当前 manifest (POSIX atomic rename 写入)
│   ├── .versions/          # W2 历史 manifest 备份 (7 天保留)
│   └── processed/
│   ├── parquet/            # Parquet 缓存文件
│   └── processed/          # 处理后数据（含淘客缓存）
├── exports/                 # 导出文件目录
└── docs/
    └── 飞书版架构文档/       # 本文档集
```

---

## 7. W2/W3/W4/W5 部署与运维（v0.4.10 配套）

### 7.1 W2 manifest.json 原子切换（v0.4.8+）

#### 7.1.1 部署检查清单

```bash
# 1. 确认 manifest.json 已写入
ls -la data/manifest.json
# 应该存在, 内容含 active_view / version / ts

# 2. 验证当前 manifest 加载正常
PYTHONPATH=. python3 -c "
from scripts.etl.manifest import SnapshotManifest
sm = SnapshotManifest('data/processed/manifest.json')
print(f'active_view: {sm.read_active()}')
print(f'full: {sm.read_full()}')
"

# 3. 后端启动时自动加载（loader.py 每次请求新 SnapshotManifest 实例, 多进程/多线程安全）
```

#### 7.1.2 手动切换 manifest（紧急回滚）

```python
# scripts/etl/manifest.py:SnapshotManifest.write_active()
from scripts.etl.manifest import SnapshotManifest

sm = SnapshotManifest('data/processed/manifest.json')
sm.write_active("user_rfm_20260604_021540")  # 回滚到上一个 view 名
# 步骤: 写 tmp + fsync + 复制旧版到 .versions/ + os.rename (POSIX atomic)
```

> 历史版本回滚：直接 `sm.write_active(old_view_name)`，旧版本自动落到 `.versions/{ts}_v{N}.json` 保留 7 天。

#### 7.1.3 监控

```bash
# 监控 manifest 切换事件
tail -f /tmp/fuqin-crm-backend.log | grep "manifest_switched"

# 监控 RFM 服务健康
curl -s http://localhost:8000/api/v1/rfm/version | jq .
# 期望: {"active_view": "user_rfm_...", "version": 42, "ts": "...", "path": "..."}
```

### 7.2 W4 fact_rfm_long 预计算（v0.4.9+）

#### 7.2.1 部署检查清单

```bash
# 1. 确认 fact_rfm_long 表存在
PYTHONPATH=. python3 -c "
import duckdb
from backend.config import DUCKDB_PATH
conn = duckdb.connect(DUCKDB_PATH, read_only=True)
n = conn.execute('SELECT COUNT(*) FROM fact_rfm_long').fetchone()[0]
print(f'fact_rfm_long rows: {n}')  # W4 MVP 期望 ≥1 (1 组合 channel=全店)
"

# 2. 验证 PRIMARY KEY + UNIQUE INDEX 已创建
PYTHONPATH=. python3 -c "
import duckdb
from backend.config import DUCKDB_PATH
conn = duckdb.connect(DUCKDB_PATH, read_only=True)
idx = conn.execute(\"\"\"
  SELECT index_name FROM duckdb_indexes
  WHERE table_name = 'fact_rfm_long'
\"\"\").fetchall()
print(idx)  # 期望含 'idx_fact_rfm_dkv' (UNIQUE INDEX)
"
```

#### 7.2.2 手动跑 W4 预计算（W4 MVP CLI）

```bash
# MVP 同步跑批（setup 16GB override + 建表 + 跑当天 T-1 增量）
PYTHONPATH=. python3 scripts/etl/precompute_fact_rfm.py
# 实际插入行数: 1 行 (channel=全店 当天 T-1)

# W4 full CLI（未实现, NotImplementedError 占位）
# 计划接口: --async / --full / --cleanup 留作 W4 full 工单
```

#### 7.2.3 与 ETL pipeline 集成

> ⚠️ 当前 main 上 `scripts/etl/pipeline.py` **未集成** W4 预计算 step（C-2 留作下次 sprint）。可独立 CLI 调用。W4 full 计划加 step 7b 调 `incremental_load_with_merge(t_minus_days=7)`。

### 7.3 W3 DQ 断言（v0.4.10+）

#### 7.3.1 部署检查清单

```bash
# 1. 确认 rfm_quarantine 表存在
PYTHONPATH=. python3 -c "
import duckdb
from backend.config import DUCKDB_PATH
conn = duckdb.connect(DUCKDB_PATH, read_only=True)
n = conn.execute('SELECT COUNT(*) FROM rfm_quarantine').fetchone()[0]
print(f'quarantine rows: {n}')  # 期望 0（无失败）
"

# 2. 验证 lark 通道（不真发，只检查）
PYTHONPATH=. python3 -c "
from scraper.core.sanity_check import _send_lark_alert
print('lark 通道已就绪')
"
```

#### 7.3.2 手动跑 W3 断言

```bash
# 手动触发（CI/CD 或运维）
python3 scripts/etl/assertions.py --date=2026-06-05

# 不发 lark 告警（本地/CI）
python3 scripts/etl/assertions.py --date=2026-06-05 --no-alert
```

#### 7.3.3 与 ETL pipeline 集成

> ⚠️ 当前 main 上 `scripts/etl/pipeline.py` **未集成** step 8 调 `run_assertions()`（C-1 留作下次 sprint）。W3 走独立 CLI 路径或 ETL 末尾手工触发。

### 7.4 W5 DuckDB-KV cache（设计稿, 未落地）

> ⚠️ **W5 当前状态**: `feat/wo5-cache` 分支，未合 main。`backend/services/rfm/cache.py` / `rfm_query_cache` 表 / `_ManifestTracker` 仅设计稿。

#### 7.4.1 部署检查清单（待 C-3 落地后启用）

```bash
# W5 落地后才有此表 (当前 main 不存在)
# 1. 确认 rfm_query_cache 表存在 (key VARCHAR PK, endpoint, params_hash, value JSON, expire_at, created_at)
PYTHONPATH=. python3 -c "
import duckdb
from backend.config import DUCKDB_PATH
conn = duckdb.connect(DUCKDB_PATH, read_only=True)
n = conn.execute('SELECT COUNT(*) FROM rfm_query_cache').fetchone()[0]
print(f'rfm_query_cache rows: {n}')
"

# 2. 验证 manifest 切换触发整表失效 (W5 用 _ManifestTracker)
# W5 设计: check_and_invalidate(conn) → DELETE FROM rfm_query_cache (整表)
```

#### 7.4.2 与 W2 manifest 集成（W5 设计）

- W2 切快照后 W5 `_ManifestTracker` 读新 version, 跟上次的 `_current_version` 比
- 变化 → `DELETE FROM rfm_query_cache`（整表失效，**不**走 `LIKE ANY (?)` —— DuckDB 不支持）
- 一样 → noop
- 4 个 RFM 端点（r-flow / f-flow / m-flow / segment-orders）下次请求时自动重建缓存

### 7.5 监控告警

#### 7.5.1 关键指标

| 指标 | 阈值 | 告警通道 |
|------|------|---------|
| `fact_rfm_long` 行数暴跌 | < 1 行 (W4 MVP 仅 1 组合, full 后调阈值) | lark |
| `rfm_quarantine.failure_count` | > 0 | lark |
| `manifest.version` 24h 内未变 | — | lark |
| `rfm_query_cache.hit_rate` | < 80% | lark (W5 落地后) |

#### 7.5.2 健康检查 endpoint

```bash
# 运维检查（v0.4.10 main 实际返回）
curl -s http://localhost:8000/api/v1/rfm/version | jq .

# 期望输出 (注意: 实际字段是 active_view/version/ts/path, 非 manifest_version/rfm_table/is_healthy)
{
  "active_view": "user_rfm_20260605_143022",
  "version": 42,
  "ts": "2026-06-05T14:30:22+00:00",
  "path": "data/processed/manifest.json"
}
```

#### 7.5.3 故障排查 SOP

| 症状 | 排查步骤 |
|------|---------|
| RFM 接口返回 500 | 1. `curl /api/v1/rfm/version` 看 manifest 状态<br>2. 查 `/tmp/fuqin-crm-backend.log` |
| fact_rfm_long 暴跌 | 1. `SELECT * FROM rfm_quarantine ORDER BY created_at DESC LIMIT 5`<br>2. 查 W3 告警 lark 消息 |
| manifest 切换后旧数据 | 1. `cat data/manifest.json` 看 active_view<br>2. `python3 -c "from scripts.etl.manifest import SnapshotManifest; print(SnapshotManifest('data/processed/manifest.json').read_full())"` |
| 缓存命中率低（W5 落地后） | 1. `SELECT * FROM rfm_query_cache ORDER BY created_at DESC LIMIT 10`<br>2. 检查 `_ManifestTracker.check_and_invalidate` 是否正常触发 |
    └── 飞书版架构文档/       # 本文档集
```
